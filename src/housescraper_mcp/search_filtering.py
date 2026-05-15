"""Search filter construction and local post-filtering rules."""

from __future__ import annotations

import re

from house_cli.models.filter import SearchFilter
from house_cli.models.house import House

from housescraper_mcp.keyword_matching import keyword_match_fields


def build_search_filter(
    *,
    city: str,
    district: str = "",
    min_price: float | None = None,
    max_price: float | None = None,
    min_area: float | None = None,
    max_area: float | None = None,
    layout: str = "",
    layouts: list[str] | None = None,
    max_unit_price: float | None = None,
    detail_verify_limit: int | None = None,
    listing_type: str = "buy",
    page: int = 1,
    sort_by: str = "default",
    keywords: str = "",
) -> SearchFilter:
    """Build the shared upstream filter model."""

    if page < 1:
        raise ValueError("page must be >= 1")
    if listing_type not in {"buy", "rent"}:
        raise ValueError("listing_type must be 'buy' or 'rent'")

    filters = SearchFilter(
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
    filters.layouts = list(layouts or ([] if not layout else [layout]))
    filters.max_unit_price = max_unit_price
    filters.detail_verify_limit = detail_verify_limit if detail_verify_limit is not None else 0
    return filters


def upstream_filters_for_platform(canonical: str, filters: SearchFilter) -> SearchFilter:
    """Relax server-side filters for platforms that trigger anti-bot on deep URLs."""

    if canonical not in {"beike", "lianjia"} or not client_side_filtering_applied(filters):
        return filters

    return SearchFilter(
        city=filters.city,
        listing_type=filters.listing_type,
        page=filters.page,
        sort_by="default",
    )


def client_side_filtering_applied(filters: SearchFilter) -> bool:
    """Whether the current query relies on local post-filtering for accuracy."""

    return any(
        value not in (None, "")
        for value in (
            filters.district,
            filters.min_price,
            filters.max_price,
            filters.min_area,
            filters.max_area,
            filters.layout,
            filters.keywords,
            getattr(filters, "max_unit_price", None),
        )
    ) or bool(getattr(filters, "layouts", []))


def filter_houses(houses: list[House], filters: SearchFilter) -> list[House]:
    """Apply local filtering rules after upstream retrieval."""

    return [house for house in houses if _matches_filters(house, filters)]


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

    layouts = getattr(filters, "layouts", [])
    if layouts:
        actual_rooms = _extract_room_count(house.layout)
        expected_rooms = {count for count in (_extract_room_count(layout) for layout in layouts) if count is not None}
        if actual_rooms is not None and expected_rooms and actual_rooms not in expected_rooms:
            return False
    elif filters.layout:
        expected_rooms = _extract_room_count(filters.layout)
        actual_rooms = _extract_room_count(house.layout)
        if actual_rooms is None:
            return False
        if expected_rooms is not None and actual_rooms != expected_rooms:
            return False
        if expected_rooms is None and filters.layout not in house.layout:
            return False

    max_unit_price = getattr(filters, "max_unit_price", None)
    if max_unit_price is not None:
        effective_unit_price = _effective_unit_price(house)
        if effective_unit_price is not None and effective_unit_price > max_unit_price:
            return False

    if filters.keywords and not keyword_match_fields(
        {
            "title": house.title,
            "community": house.community,
            "address": house.address,
            "district": house.district,
            "tags": house.tags,
        },
        filters.keywords,
    ):
        return False

    return True


def _extract_room_count(layout: str) -> int | None:
    match = re.search(r"(\d+)\s*室", layout)
    if match is None:
        return None
    return int(match.group(1))


def _effective_unit_price(house: House) -> float | None:
    if house.unit_price is not None:
        return float(house.unit_price)
    if house.area <= 0 or house.price <= 0:
        return None
    return float(house.price) * 10000.0 / float(house.area)
