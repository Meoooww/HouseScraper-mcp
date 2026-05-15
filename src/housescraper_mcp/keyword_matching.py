"""Keyword and text normalization helpers shared by search modules."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


def normalize_text(value: str) -> str:
    """Normalize text for fuzzy matching across platform payloads."""

    return re.sub(r"\s+", "", value).lower()


def normalize_district(value: str) -> str:
    """Normalize small district naming variants such as `浦东` vs `浦东新区`."""

    normalized = normalize_text(value)
    if normalized.endswith("新区"):
        return normalized[:-2]
    if normalized.endswith("区"):
        return normalized[:-1]
    return normalized


def keyword_match_fields(listing: Mapping[str, Any], keyword: str) -> list[str]:
    """Return which public listing fields matched the requested keyword."""

    normalized_keyword = normalize_text(keyword)
    if not normalized_keyword:
        return []

    matches: list[str] = []
    for field in ("title", "community", "address", "district"):
        value = str(listing.get(field, "") or "")
        if normalized_keyword in normalize_text(value):
            matches.append(field)

    tags = listing.get("tags", [])
    if any(normalized_keyword in normalize_text(str(tag)) for tag in tags):
        matches.append("tags")

    return matches
