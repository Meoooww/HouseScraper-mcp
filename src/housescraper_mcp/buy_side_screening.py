"""Buy-side screening helpers for Listing Search."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from house_cli.models.filter import SearchFilter

from housescraper_mcp.keyword_matching import normalize_text

UNCERTAIN_OWNERSHIP = "ownership_missing"
UNCERTAIN_RESIDENTIAL_USE = "residential_use_missing"
UNCERTAIN_UNIT_PRICE = "unit_price_missing"
UNCERTAIN_DETAIL_NOT_VERIFIED = "detail_not_verified"
UNCERTAIN_DETAIL_FAILED = "detail_verification_failed"

NON_RESIDENTIAL_PATTERNS = (
    "公寓",
    "商住",
    "商办",
    "办公",
    "写字楼",
    "soho",
    "loft",
    "小产权",
)
OWNERSHIP_70_PATTERNS = (
    "70年产权",
    "70年大产权",
    "70年住宅",
)
PURE_RESIDENTIAL_PATTERNS = (
    "纯住宅",
    "商品住宅",
    "住宅",
)


def buy_side_screening_requested(filters: SearchFilter) -> bool:
    """Whether the current Listing Search should emit buy-side eligibility metadata."""

    return bool(
        getattr(filters, "layouts", [])
        or getattr(filters, "max_unit_price", None) is not None
        or filters.min_area is not None
        or filters.max_area is not None
    )


def apply_buy_side_screening(
    listings: Iterable[Mapping[str, Any]],
    filters: SearchFilter,
) -> list[dict[str, Any]]:
    """Exclude explicit failures and annotate returned listings with A/B buy-side eligibility."""

    if not buy_side_screening_requested(filters):
        return [dict(listing) for listing in listings]

    annotated: list[dict[str, Any]] = []
    for index, listing in enumerate(listings):
        projected = dict(listing)
        projected["unit_price_effective"] = effective_unit_price(projected)

        if _explicitly_non_residential(projected):
            continue

        uncertain_reasons = _uncertain_reasons(projected, filters)
        projected["uncertain_reasons"] = uncertain_reasons
        projected["ownership_status"] = (
            "explicit_70_year" if _has_explicit_70_year_ownership(projected) else "missing"
        )
        projected["residential_use_status"] = (
            "explicit_pure_residential" if _has_explicit_pure_residential_use(projected) else "missing"
        )
        projected["eligibility_tier"] = "A" if not uncertain_reasons else "B"
        projected["_screening_order"] = index
        annotated.append(projected)

    annotated.sort(key=_screening_sort_key)
    for listing in annotated:
        listing.pop("_screening_order", None)
    return annotated


def effective_unit_price(listing: Mapping[str, Any]) -> float | None:
    """Return raw or derived unit price for the public listing payload."""

    unit_price = listing.get("unit_price")
    if unit_price is not None:
        return float(unit_price)

    area = float(listing.get("area", 0.0) or 0.0)
    price = float(listing.get("price", 0.0) or 0.0)
    if area <= 0 or price <= 0:
        return None
    return price * 10000.0 / area


def _uncertain_reasons(listing: Mapping[str, Any], filters: SearchFilter) -> list[str]:
    reasons: list[str] = []

    if getattr(filters, "max_unit_price", None) is not None and effective_unit_price(listing) is None:
        reasons.append(UNCERTAIN_UNIT_PRICE)

    if not _has_explicit_70_year_ownership(listing):
        reasons.append(UNCERTAIN_OWNERSHIP)

    if not _has_explicit_pure_residential_use(listing):
        reasons.append(UNCERTAIN_RESIDENTIAL_USE)

    detail_status = str(listing.get("detail_verification_status", "") or "")
    if detail_status == "not_requested":
        reasons.append(UNCERTAIN_DETAIL_NOT_VERIFIED)
    elif detail_status == "error":
        reasons.append(UNCERTAIN_DETAIL_FAILED)

    return reasons


def _screening_sort_key(listing: Mapping[str, Any]) -> tuple[int, int, float, int]:
    unit_price = listing.get("unit_price_effective")
    if unit_price is None:
        unit_price_value = float("inf")
    else:
        unit_price_value = float(unit_price)

    return (
        0 if listing.get("eligibility_tier") == "A" else 1,
        1 if listing.get("duplicate_id") else 0,
        unit_price_value,
        int(listing.get("_screening_order", 0)),
    )


def _has_explicit_70_year_ownership(listing: Mapping[str, Any]) -> bool:
    blob = _listing_text_blob(listing)
    return any(pattern in blob for pattern in OWNERSHIP_70_PATTERNS)


def _has_explicit_pure_residential_use(listing: Mapping[str, Any]) -> bool:
    blob = _listing_text_blob(listing)
    if any(pattern in blob for pattern in NON_RESIDENTIAL_PATTERNS):
        return False
    return any(pattern in blob for pattern in PURE_RESIDENTIAL_PATTERNS)


def _explicitly_non_residential(listing: Mapping[str, Any]) -> bool:
    return any(pattern in _listing_text_blob(listing) for pattern in NON_RESIDENTIAL_PATTERNS)


def _listing_text_blob(listing: Mapping[str, Any]) -> str:
    values = [
        str(listing.get("title", "") or ""),
        str(listing.get("community", "") or ""),
        str(listing.get("address", "") or ""),
        str(listing.get("district", "") or ""),
        str(listing.get("description", "") or ""),
    ]
    values.extend(str(tag or "") for tag in listing.get("tags", []))
    return normalize_text(" ".join(values))
