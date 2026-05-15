"""Service layer that wraps house-cli adapters for MCP exposure."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Protocol

from house_cli.client.adapters import ADAPTER_REGISTRY
from house_cli.models.filter import SearchFilter
from house_cli.models.house import House

from housescraper_mcp.adapters import BeikeClient, LianjiaClient
from housescraper_mcp.artifacts import ArtifactStore
from housescraper_mcp.cookies import prepare_cookies
from housescraper_mcp.platforms import RequestedPlatform, group_by_canonical, resolve_platforms


class SearchAdapter(Protocol):
    """The slice of the upstream adapter API that this service relies on."""

    async def search(self, filters: SearchFilter) -> list[House]:
        """Return a unified set of house results for the given filter."""


AdapterFactory = Callable[[], SearchAdapter]
DEFAULT_BASELINE_PLATFORMS = ["beike", "lianjia", "anjuke"]


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
        "beike": BeikeClient,
        "lianjia": LianjiaClient,
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

    if canonical not in {"beike", "lianjia"} or not client_side_filtering_applied(filters):
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


def build_baseline_summary(
    probe_response: Mapping[str, Any],
    search_response: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Flatten probe/search responses into a stable per-platform health summary."""

    probe_by_requested = {
        result["requested_platform"]: result for result in probe_response.get("results", [])
    }
    search_by_requested = {
        result["requested_platform"]: result
        for result in search_response.get("meta", {}).get("platforms", [])
    }

    summary: list[dict[str, Any]] = []
    for requested_platform in probe_response.get("requested_platforms", []):
        probe_status = probe_by_requested[requested_platform]
        search_status = search_by_requested.get(requested_platform, {})
        summary.append(
            {
                "requested_platform": requested_platform,
                "platform": probe_status["platform"],
                "probe_ok": probe_status["ok"],
                "probe_raw_result_count": probe_status["raw_result_count"],
                "probe_error_type": probe_status["error_type"],
                "probe_captcha_suspected": probe_status["captcha_suspected"],
                "search_ok": search_status.get("status") == "success",
                "search_result_count": search_status.get("result_count", 0),
                "search_raw_result_count": search_status.get("raw_result_count", 0),
                "search_error_type": search_status.get("error_type"),
                "search_captcha_suspected": search_status.get("captcha_suspected", False),
            }
        )
    return summary


def platform_search_status(status: Mapping[str, Any]) -> str:
    """Translate legacy per-platform execution data into contract status enums."""

    if not status.get("ok", False):
        return "error"
    if status.get("result_count", 0) == 0:
        return "no_results"
    return "success"


def top_level_search_status(
    platform_statuses: Iterable[Mapping[str, Any]],
) -> str:
    """Derive the agent-facing search status from per-platform outcomes."""

    normalized = [platform_search_status(status) for status in platform_statuses]
    if any(status == "success" for status in normalized):
        if any(status == "error" for status in normalized):
            return "partial_success"
        return "success"
    if any(status == "error" for status in normalized):
        return "error"
    return "no_results"


def platform_filter_mode(canonical: str, filters: SearchFilter) -> str:
    """Describe whether a platform used default, native, or post-filtered search."""

    if not client_side_filtering_applied(filters):
        return "default"
    if canonical in {"beike", "lianjia"}:
        return "post_filtered"
    return "native"


def search_platform_meta(status: Mapping[str, Any], filters: SearchFilter) -> dict[str, Any]:
    """Project execution status into the public search-platform contract."""

    return {
        "requested_platform": status["requested_platform"],
        "platform": status["platform"],
        "status": platform_search_status(status),
        "result_count": status["result_count"],
        "raw_result_count": status["raw_result_count"],
        "elapsed_ms": status["elapsed_ms"],
        "cookies_detected": status["cookies_detected"],
        "captcha_suspected": status["captcha_suspected"],
        "error_type": status["error_type"],
        "error_message": status["error_message"],
        "filter_mode": platform_filter_mode(status["platform"], filters),
    }


def listing_ref(listing: Mapping[str, Any]) -> str:
    """Build a stable agent-facing listing reference."""

    return f"{listing['platform']}:{listing['id']}"


def annotate_duplicates(listings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Mark likely duplicates and move them behind retained primary results."""

    primary_results: list[dict[str, Any]] = []
    duplicate_results: list[dict[str, Any]] = []
    possible_duplicate_count = 0

    for listing in listings:
        annotated = dict(listing)
        annotated["listing_ref"] = listing_ref(annotated)

        duplicate_of = next(
            (
                primary["listing_ref"]
                for primary in primary_results
                if is_possible_duplicate(annotated, primary)
            ),
            None,
        )

        annotated["duplicate_id"] = duplicate_of
        if duplicate_of is None:
            primary_results.append(annotated)
            continue

        possible_duplicate_count += 1
        duplicate_results.append(annotated)

    return primary_results + duplicate_results, possible_duplicate_count


def is_possible_duplicate(candidate: Mapping[str, Any], primary: Mapping[str, Any]) -> bool:
    """Use cautious first-wave heuristics to flag likely duplicate listings."""

    if candidate["platform"] == primary["platform"]:
        return False

    candidate_community = normalize_text(candidate.get("community", ""))
    primary_community = normalize_text(primary.get("community", ""))
    if not candidate_community or candidate_community != primary_community:
        return False

    candidate_district = normalize_text(candidate.get("district", ""))
    primary_district = normalize_text(primary.get("district", ""))
    if candidate_district and primary_district and candidate_district != primary_district:
        return False

    return abs(float(candidate.get("area", 0.0)) - float(primary.get("area", 0.0))) <= 5.0


def normalize_text(value: str) -> str:
    """Normalize text for fuzzy identity comparisons."""

    return re.sub(r"\s+", "", value).lower()


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
        if limit > 30:
            raise ValueError("limit must be <= 30")
        if filters.page > 3:
            raise ValueError("page must be <= 3")

        targets = resolve_platforms(platforms)
        executions = await self._run_platforms(filters, targets)

        platform_status = [executions[target.canonical].to_status(target) for target in targets]
        houses: list[dict[str, Any]] = []
        for canonical in self._requested_order(targets):
            houses.extend(asdict(house) for house in executions[canonical].houses)

        annotated_houses, possible_duplicate_count = annotate_duplicates(houses)
        returned_houses = annotated_houses[:limit]
        meta_platforms = [search_platform_meta(status, filters) for status in platform_status]
        status = top_level_search_status(platform_status)

        return {
            "status": status,
            "meta": {
                "query": asdict(filters),
                "client_side_filtering": client_side_filtering_applied(filters),
                "requested_platforms": [target.requested for target in targets],
                "resolved_platforms": [target.canonical for target in targets],
                "platforms": meta_platforms,
                "raw_count": len(annotated_houses),
                "possible_duplicate_count": possible_duplicate_count,
                "returned_count": len(returned_houses),
                "truncated": len(annotated_houses) > limit,
            },
            "data": returned_houses,
        }

    async def baseline(
        self,
        *,
        city: str = "上海",
        platforms: Iterable[str] | None = None,
        max_price: float = 500.0,
        layout: str = "2室",
        listing_type: str = "buy",
        page: int = 1,
        sample_limit: int = 3,
        search_limit: int = 5,
    ) -> dict[str, Any]:
        """Run a repeatable live baseline for all supported platforms."""

        requested_platforms = list(platforms or DEFAULT_BASELINE_PLATFORMS)
        probe_filters = build_search_filter(
            city=city,
            listing_type=listing_type,
            page=page,
        )
        search_filters = build_search_filter(
            city=city,
            max_price=max_price,
            layout=layout,
            listing_type=listing_type,
            page=page,
        )

        probe_response = await self.probe(
            probe_filters,
            platforms=requested_platforms,
            sample_limit=sample_limit,
        )
        search_response = await self.search(
            search_filters,
            platforms=requested_platforms,
            limit=search_limit,
        )
        platform_summary = build_baseline_summary(probe_response, search_response)

        payload = {
            "ok": bool(platform_summary)
            and all(item["probe_ok"] and item["search_ok"] for item in platform_summary),
            "generated_at": datetime.now(UTC).isoformat(),
            "city": city,
            "requested_platforms": requested_platforms,
            "search_scenario": {
                "max_price": max_price,
                "layout": layout,
                "listing_type": listing_type,
                "page": page,
                "search_limit": search_limit,
            },
            "platform_summary": platform_summary,
            "checks": {
                "probe": probe_response,
                "filtered_search": search_response,
            },
        }
        payload["report_artifact_path"] = self.artifact_store.write_baseline_report(city, payload)
        return payload

    async def _run_platforms(
        self,
        filters: SearchFilter,
        targets: Iterable[RequestedPlatform],
    ) -> dict[str, PlatformExecution]:
        grouped = group_by_canonical(targets)
        tasks = {
            canonical: self._execute_search(canonical, filters, requested_targets[0])
            for canonical, requested_targets in grouped.items()
        }
        outcomes = await asyncio.gather(*tasks.values())
        return dict(zip(tasks.keys(), outcomes, strict=True))

    async def _execute_search(
        self,
        canonical: str,
        filters: SearchFilter,
        target: RequestedPlatform,
    ) -> PlatformExecution:
        factory = self.adapter_factories.get(canonical)
        if factory is None:
            raise ValueError(f"No adapter configured for platform: {canonical}")

        cookies_detected = bool(
            prepare_cookies(
                target.cookie_domain,
                fallback_domains=target.fallback_cookie_domains,
            )
        )
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
