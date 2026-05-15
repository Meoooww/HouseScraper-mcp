"""Service layer that wraps house-cli adapters for MCP exposure."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Protocol, cast

from house_cli.client.adapters import ADAPTER_REGISTRY
from house_cli.models.filter import SearchFilter
from house_cli.models.house import House
from house_cli.models.house import HouseDetail

from housescraper_mcp.adapters import BeikeClient, LianjiaClient
from housescraper_mcp.artifacts import ArtifactStore
from housescraper_mcp.cookies import prepare_cookies
from housescraper_mcp.platforms import RequestedPlatform, group_by_canonical, resolve_platforms
from housescraper_mcp.search_contract import annotate_duplicates as annotate_duplicates_module
from housescraper_mcp.search_contract import attach_keyword_match as attach_keyword_match_module
from housescraper_mcp.search_contract import is_possible_duplicate as is_possible_duplicate_module
from housescraper_mcp.search_contract import keyword_match_fields as keyword_match_fields_module
from housescraper_mcp.search_contract import listing_ref as listing_ref_module
from housescraper_mcp.search_contract import parse_listing_ref as parse_listing_ref_module
from housescraper_mcp.search_contract import platform_filter_mode as platform_filter_mode_module
from housescraper_mcp.search_contract import platform_search_status as platform_search_status_module
from housescraper_mcp.search_contract import search_platform_meta as search_platform_meta_module
from housescraper_mcp.search_contract import serialize_detail as serialize_detail_module
from housescraper_mcp.search_contract import top_level_search_status as top_level_search_status_module
from housescraper_mcp.search_filtering import build_search_filter as build_search_filter_module
from housescraper_mcp.search_filtering import client_side_filtering_applied as client_side_filtering_applied_module
from housescraper_mcp.search_filtering import filter_houses as filter_houses_module
from housescraper_mcp.search_filtering import upstream_filters_for_platform as upstream_filters_for_platform_module


class SearchAdapter(Protocol):
    """The slice of the upstream adapter API that this service relies on."""

    async def search(self, filters: SearchFilter) -> list[House]:
        """Return a unified set of house results for the given filter."""


class DetailAdapter(Protocol):
    """The slice of the upstream adapter detail API used by this service."""

    async def detail(self, house_id: str) -> HouseDetail:
        """Return a structured detail payload for the given listing ID."""


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
    keywords: str = "",
) -> SearchFilter:
    """Compatibility wrapper around the SearchFiltering module."""

    return build_search_filter_module(
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
        keywords=keywords,
    )


def upstream_filters_for_platform(canonical: str, filters: SearchFilter) -> SearchFilter:
    """Compatibility wrapper around the SearchFiltering module."""

    return upstream_filters_for_platform_module(canonical, filters)


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
    """Compatibility wrapper around the SearchFiltering module."""

    return filter_houses_module(houses, filters)


def client_side_filtering_applied(filters: SearchFilter) -> bool:
    """Compatibility wrapper around the SearchFiltering module."""

    return client_side_filtering_applied_module(filters)


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
    """Compatibility wrapper around the SearchResultEnvelope module."""

    return platform_search_status_module(status)


def top_level_search_status(
    platform_statuses: Iterable[Mapping[str, Any]],
) -> str:
    """Compatibility wrapper around the SearchResultEnvelope module."""

    return top_level_search_status_module(platform_statuses)


def platform_filter_mode(canonical: str, filters: SearchFilter) -> str:
    """Compatibility wrapper around the SearchResultEnvelope module."""

    return platform_filter_mode_module(canonical, filters)


def search_platform_meta(status: Mapping[str, Any], filters: SearchFilter) -> dict[str, Any]:
    """Compatibility wrapper around the SearchResultEnvelope module."""

    return search_platform_meta_module(status, filters)


def listing_ref(listing: Mapping[str, Any]) -> str:
    """Compatibility wrapper around the SearchResultEnvelope module."""

    return listing_ref_module(listing)


def parse_listing_ref(value: str) -> tuple[str, str]:
    """Compatibility wrapper around the SearchResultEnvelope module."""

    return parse_listing_ref_module(value)


def serialize_detail(detail: HouseDetail) -> dict[str, Any]:
    """Compatibility wrapper around the SearchResultEnvelope module."""

    return serialize_detail_module(detail)


def attach_keyword_match(listing: dict[str, Any], keyword: str) -> dict[str, Any]:
    """Compatibility wrapper around the SearchResultEnvelope module."""

    return attach_keyword_match_module(listing, keyword)


def annotate_duplicates(listings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Compatibility wrapper around the SearchResultEnvelope module."""

    return annotate_duplicates_module(listings)


def is_possible_duplicate(candidate: Mapping[str, Any], primary: Mapping[str, Any]) -> bool:
    """Compatibility wrapper around the SearchResultEnvelope module."""

    return is_possible_duplicate_module(candidate, primary)


def keyword_match_fields(listing: Mapping[str, Any], keyword: str) -> list[str]:
    """Compatibility wrapper around the SearchResultEnvelope module."""

    return keyword_match_fields_module(listing, keyword)


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
            houses.extend(
                attach_keyword_match(asdict(house), filters.keywords)
                for house in executions[canonical].houses
            )

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

    async def detail(self, listing_ref: str) -> dict[str, Any]:
        """Fetch structured detail for a selected listing."""
        platform, house_id = parse_listing_ref(listing_ref)
        target = resolve_platforms([platform])[0]
        factory = self.adapter_factories.get(target.canonical)
        if factory is None:
            raise ValueError(f"No adapter configured for platform: {target.canonical}")

        adapter = factory()
        if not hasattr(adapter, "detail"):
            raise ValueError(f"Detail lookup is not supported for platform: {target.canonical}")

        try:
            detail = await cast(DetailAdapter, adapter).detail(house_id)
            serialized = serialize_detail(detail)
            return {
                "status": "success",
                "meta": {
                    "listing_ref": listing_ref,
                    "platform": target.canonical,
                },
                "data": serialized,
            }
        except Exception as exc:
            error_type, _captcha_suspected = classify_error(exc)
            return {
                "status": "error",
                "meta": {
                    "listing_ref": listing_ref,
                    "platform": target.canonical,
                    "error_type": error_type,
                    "error_message": str(exc),
                },
                "data": None,
            }

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
