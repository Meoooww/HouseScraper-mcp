"""Service layer that wraps house-cli adapters for MCP exposure."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from time import monotonic
from typing import Any, Protocol

from house_cli.client.adapters import ADAPTER_REGISTRY
from house_cli.client.auth import (
    _try_browser_cookie3,
    get_cookies,
    load_or_extract_cookies,
    save_cookies,
)
from house_cli.models.filter import SearchFilter
from house_cli.models.house import House

from housescraper_mcp.artifacts import ArtifactStore
from housescraper_mcp.platforms import RequestedPlatform, group_by_canonical, resolve_platforms


class SearchAdapter(Protocol):
    """The slice of the upstream adapter API that this service relies on."""

    async def search(self, filters: SearchFilter) -> list[House]:
        """Return a unified set of house results for the given filter."""


AdapterFactory = Callable[[], SearchAdapter]


@dataclass(slots=True)
class PlatformExecution:
    """Search execution data for one canonical adapter run."""

    canonical: str
    houses: list[House]
    cookies_detected: bool
    elapsed_ms: int
    raw_result_count: int = 0
    error_type: str | None = None
    error_message: str | None = None
    captcha_suspected: bool = False

    @property
    def ok(self) -> bool:
        return self.error_type is None

    def to_status(self, target: RequestedPlatform, sample_limit: int = 3) -> dict[str, Any]:
        status = {
            "requested_platform": target.requested,
            "platform": self.canonical,
            "ok": self.ok,
            "result_count": len(self.houses),
            "raw_result_count": self.raw_result_count,
            "elapsed_ms": self.elapsed_ms,
            "cookies_detected": self.cookies_detected,
            "captcha_suspected": self.captcha_suspected,
            "sample_titles": [house.title for house in self.houses[:sample_limit]],
            "sample_urls": [house.url for house in self.houses[:sample_limit]],
            "error_type": self.error_type,
            "error_message": self.error_message,
        }
        return status


def default_adapter_factories() -> dict[str, AdapterFactory]:
    """Return the upstream adapters used in the first MVP."""

    return {
        "beike": ADAPTER_REGISTRY["beike"],
        "anjuke": ADAPTER_REGISTRY["anjuke"],
    }


def build_search_filter(
    *,
    city: str,
    district: str = "",
    min_price: float | None = None,
    max_price: float | None = None,
    min_area: float | None = None,
    max_area: float | None = None,
    layout: str = "",
    listing_type: str = "buy",
    page: int = 1,
    sort_by: str = "default",
) -> SearchFilter:
    """Build the shared upstream filter model."""

    if page < 1:
        raise ValueError("page must be >= 1")
    if listing_type not in {"buy", "rent"}:
        raise ValueError("listing_type must be 'buy' or 'rent'")

    return SearchFilter(
        city=city,
        district=district,
        min_price=min_price,
        max_price=max_price,
        min_area=min_area,
        max_area=max_area,
        layout=layout,
        listing_type=listing_type,
        page=page,
        sort_by=sort_by,
    )


def upstream_filters_for_platform(canonical: str, filters: SearchFilter) -> SearchFilter:
    """Relax server-side filters for platforms that trigger anti-bot on deep URLs.

    Beike's filtered list URLs are much more likely to hit CAPTCHA than the base
    city list page. For the MVP we prefer a stable first-page fetch plus client-side
    filtering over a brittle server-side query that often fails entirely.
    """

    if canonical != "beike" or not client_side_filtering_applied(filters):
        return filters

    return SearchFilter(
        city=filters.city,
        listing_type=filters.listing_type,
        page=filters.page,
        sort_by="default",
    )


def classify_error(exc: Exception) -> tuple[str, bool]:
    """Classify adapter failures into coarse-grained MCP-safe categories."""

    message = str(exc).lower()
    if "captcha" in message or "verify" in message:
        return "captcha", True
    if "cookie" in message:
        return "missing_cookies", False
    if "403" in message or "forbidden" in message:
        return "http_forbidden", False
    if "429" in message or "rate" in message:
        return "rate_limited", False
    return "adapter_error", False


def prepare_cookies(domain: str) -> dict[str, str]:
    """Refresh cached cookies from the browser when a partial file entry exists.

    `house-cli` stops at the cookie file as soon as it finds any non-expired entry.
    That is a problem for ke.com because one stale session cookie can block the
    fallback browser extraction path forever. We merge cached cookies with the
    browser view first, then persist the richer set for the upstream adapter.
    """

    file_cookies = get_cookies(domain)
    browser_cookies = _try_browser_cookie3(domain)

    if browser_cookies:
        merged = {**file_cookies, **browser_cookies}
        if merged != file_cookies:
            save_cookies(domain, merged)
        return merged

    if file_cookies:
        return file_cookies

    return load_or_extract_cookies(domain)


def filter_houses(houses: list[House], filters: SearchFilter) -> list[House]:
    """Apply client-side filters when upstream fallback pages ignore constraints."""

    return [house for house in houses if _matches_filters(house, filters)]


def client_side_filtering_applied(filters: SearchFilter) -> bool:
    """Whether the current query relies on post-filtering for accuracy."""

    return any(
        value not in (None, "")
        for value in (
            filters.district,
            filters.min_price,
            filters.max_price,
            filters.min_area,
            filters.max_area,
            filters.layout,
        )
    )


def _matches_filters(house: House, filters: SearchFilter) -> bool:
    if filters.district:
        if not house.district or filters.district not in house.district:
            return False

    if filters.min_price is not None and house.price < filters.min_price:
        return False
    if filters.max_price is not None and house.price > filters.max_price:
        return False

    if filters.min_area is not None and house.area < filters.min_area:
        return False
    if filters.max_area is not None and house.area > filters.max_area:
        return False

    if filters.layout:
        expected_rooms = _extract_room_count(filters.layout)
        actual_rooms = _extract_room_count(house.layout)
        if actual_rooms is None:
            return False
        if expected_rooms is not None and actual_rooms != expected_rooms:
            return False
        if expected_rooms is None and filters.layout not in house.layout:
            return False

    return True


def _extract_room_count(layout: str) -> int | None:
    match = re.search(r"(\d+)\s*室", layout)
    if match is None:
        return None
    return int(match.group(1))


class HouseScraperService:
    """Thin orchestrator around upstream house search adapters."""

    def __init__(
        self,
        *,
        adapter_factories: Mapping[str, AdapterFactory] | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        self.adapter_factories = dict(adapter_factories or default_adapter_factories())
        self.artifact_store = artifact_store or ArtifactStore()

    async def probe(
        self,
        filters: SearchFilter,
        *,
        platforms: Iterable[str] | None = None,
        sample_limit: int = 3,
    ) -> dict[str, Any]:
        """Run lightweight searches and return platform-by-platform health data."""

        targets = resolve_platforms(platforms)
        executions = await self._run_platforms(filters, targets)

        results: list[dict[str, Any]] = []
        for target in targets:
            status = executions[target.canonical].to_status(target, sample_limit=sample_limit)
            status["debug_artifact_path"] = self.artifact_store.write_probe_snapshot(
                target.requested,
                status,
            )
            results.append(status)

        return {
            "ok": any(result["ok"] for result in results),
            "query": asdict(filters),
            "client_side_filtering": client_side_filtering_applied(filters),
            "requested_platforms": [target.requested for target in targets],
            "resolved_platforms": [target.canonical for target in targets],
            "results": results,
        }

    async def search(
        self,
        filters: SearchFilter,
        *,
        platforms: Iterable[str] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Run a merged search and return normalized listings plus platform status."""

        if limit < 1:
            raise ValueError("limit must be >= 1")

        targets = resolve_platforms(platforms)
        executions = await self._run_platforms(filters, targets)

        platform_status = [executions[target.canonical].to_status(target) for target in targets]
        houses: list[dict[str, Any]] = []
        for canonical in self._requested_order(targets):
            houses.extend(asdict(house) for house in executions[canonical].houses)

        return {
            "ok": any(status["ok"] for status in platform_status),
            "query": asdict(filters),
            "client_side_filtering": client_side_filtering_applied(filters),
            "requested_platforms": [target.requested for target in targets],
            "resolved_platforms": [target.canonical for target in targets],
            "platform_status": platform_status,
            "result_count": len(houses),
            "results_truncated": len(houses) > limit,
            "results": houses[:limit],
        }

    async def _run_platforms(
        self,
        filters: SearchFilter,
        targets: Iterable[RequestedPlatform],
    ) -> dict[str, PlatformExecution]:
        grouped = group_by_canonical(targets)
        tasks = {
            canonical: self._execute_search(canonical, filters, requested_targets[0].cookie_domain)
            for canonical, requested_targets in grouped.items()
        }
        outcomes = await asyncio.gather(*tasks.values())
        return dict(zip(tasks.keys(), outcomes, strict=True))

    async def _execute_search(
        self,
        canonical: str,
        filters: SearchFilter,
        cookie_domain: str,
    ) -> PlatformExecution:
        factory = self.adapter_factories.get(canonical)
        if factory is None:
            raise ValueError(f"No adapter configured for platform: {canonical}")

        cookies_detected = bool(prepare_cookies(cookie_domain))
        start = monotonic()
        adapter = factory()
        upstream_filters = upstream_filters_for_platform(canonical, filters)
        try:
            raw_houses = await adapter.search(upstream_filters)
            houses = filter_houses(raw_houses, filters)
            return PlatformExecution(
                canonical=canonical,
                houses=houses,
                cookies_detected=cookies_detected,
                elapsed_ms=int((monotonic() - start) * 1000),
                raw_result_count=len(raw_houses),
            )
        except Exception as exc:
            error_type, captcha_suspected = classify_error(exc)
            return PlatformExecution(
                canonical=canonical,
                houses=[],
                cookies_detected=cookies_detected,
                elapsed_ms=int((monotonic() - start) * 1000),
                raw_result_count=0,
                error_type=error_type,
                error_message=str(exc),
                captcha_suspected=captcha_suspected,
            )

    @staticmethod
    def _requested_order(targets: Iterable[RequestedPlatform]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for target in targets:
            if target.canonical in seen:
                continue
            seen.add(target.canonical)
            ordered.append(target.canonical)
        return ordered
