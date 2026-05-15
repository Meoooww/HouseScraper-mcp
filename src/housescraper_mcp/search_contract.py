"""Search/detail contract helpers for MCP-facing payloads."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict
from typing import Any

from house_cli.models.filter import SearchFilter
from house_cli.models.house import HouseDetail

from housescraper_mcp.keyword_matching import keyword_match_fields, normalize_district, normalize_text
from housescraper_mcp.search_filtering import client_side_filtering_applied


def platform_search_status(status: Mapping[str, Any]) -> str:
    """Translate per-platform execution data into contract status enums."""

    if not status.get("ok", False):
        return "error"
    if status.get("result_count", 0) == 0:
        return "no_results"
    return "success"


def top_level_search_status(platform_statuses: Iterable[Mapping[str, Any]]) -> str:
    """Derive top-level search status from per-platform outcomes."""

    normalized = [platform_search_status(status) for status in platform_statuses]
    if any(status == "success" for status in normalized):
        if any(status == "error" for status in normalized):
            return "partial_success"
        return "success"
    if any(status == "error" for status in normalized):
        return "error"
    return "no_results"


def platform_filter_mode(canonical: str, filters: SearchFilter) -> str:
    """Describe whether a platform used default, native, or post-filtered mode."""

    if not client_side_filtering_applied(filters):
        return "default"
    if filters.keywords:
        return "post_filtered"
    if canonical in {"beike", "lianjia"}:
        return "post_filtered"
    return "native"


def search_platform_meta(status: Mapping[str, Any], filters: SearchFilter) -> dict[str, Any]:
    """Project execution status into the public platform-level search contract."""

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


def parse_listing_ref(value: str) -> tuple[str, str]:
    """Parse a stable agent-facing listing reference."""

    platform, separator, house_id = value.partition(":")
    if not separator or not platform or not house_id:
        raise ValueError("listing_ref must look like '<platform>:<id>'")
    return platform, house_id


def serialize_detail(detail: HouseDetail) -> dict[str, Any]:
    """Project HouseDetail into the public detail contract."""

    payload = asdict(detail)
    payload["listing_ref"] = listing_ref(payload)
    return payload


def attach_keyword_match(listing: dict[str, Any], keyword: str) -> dict[str, Any]:
    """Attach keyword match visibility for search results."""

    if not keyword:
        return listing

    matched_fields = keyword_match_fields(listing, keyword)
    if matched_fields:
        listing["keyword_match"] = {
            "keyword": keyword,
            "matched_fields": matched_fields,
        }
    return listing


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

    candidate_district = normalize_district(candidate.get("district", ""))
    primary_district = normalize_district(primary.get("district", ""))
    if candidate_district and primary_district and candidate_district != primary_district:
        return False

    return abs(float(candidate.get("area", 0.0)) - float(primary.get("area", 0.0))) <= 5.0
