"""Real-world probing helpers for Anjuke accepted inputs and output fields."""

import re
from dataclasses import asdict

from house_cli.client.adapters.anjuke import AnjukeClient
from house_cli.client.auth import load_or_extract_cookies
from house_cli.client.http import HttpClient
from house_cli.models.filter import SearchFilter


def _classify_token(token: str) -> str:
    if re.fullmatch(r"m\d+", token):
        return "price_bucket"
    if re.fullmatch(r"a\d+", token):
        return "area_bucket"
    if re.fullmatch(r"b\d+", token):
        return "layout_bucket"
    if re.fullmatch(r"l\d+", token):
        return "orientation_bucket"
    if re.fullmatch(r"fl\d+", token):
        return "floor_bucket"
    if re.fullmatch(r"y\d+", token):
        return "building_age_bucket"
    if re.fullmatch(r"t\d+", token):
        return "property_type_bucket"
    if re.fullmatch(r"z\d+", token):
        return "property_nature_bucket"
    if re.fullmatch(r"d\d+", token):
        return "renovation_bucket"
    if re.fullmatch(r"dt\d+", token):
        return "feature_near_subway"
    if re.fullmatch(r"fv\d+", token):
        return "feature_verified"
    if re.fullmatch(r"v\d+", token):
        return "feature_vr"
    if re.fullmatch(r"ls\d+", token):
        return "feature_urgent"
    if re.fullmatch(r"o\d+", token):
        return "sort_token"
    if re.fullmatch(r"p\d+", token):
        return "page_token"
    if re.fullmatch(r"[a-z]+", token):
        return "district_slug"
    if re.fullmatch(r"[a-z]+-q-[a-z0-9]+", token):
        return "bizcircle_slug"
    return "other"


async def discover_real_filter_inputs(city: str = "上海") -> dict:
    """Discover accepted filter tokens from real homepage sale links."""
    cookies = load_or_extract_cookies("anjuke.com")
    referer = "https://www.anjuke.com/sy-city.html"

    async with HttpClient(referer=referer) as client:
        city_slug = await AnjukeClient()._resolve_city_slug(city, client, cookies)
        url = f"https://{city_slug}.anjuke.com/?from=AJK_Web_City"
        resp = await client.get(url, cookies=cookies)
        html = resp.text

    pattern = re.compile(
        rf'<a[^>]+href="(https?://{re.escape(city_slug)}\.anjuke\.com/sale/[^"]*)"[^>]*>(.*?)</a>',
        re.DOTALL,
    )

    tokens: dict[str, dict] = {}
    for href, text_html in pattern.findall(html):
        text = re.sub(r"<[^>]+>", "", text_html)
        text = " ".join(text.split()).strip()
        if not text:
            continue

        m = re.search(r"/sale/([^/?#]+)/?", href)
        if not m:
            continue
        token = m.group(1).strip("/")
        if not token:
            continue

        if token not in tokens:
            tokens[token] = {
                "label": text,
                "kind": _classify_token(token),
                "example_url": href,
            }

    return {
        "city": city,
        "city_slug": city_slug,
        "source": "homepage_sale_links",
        "source_url": url,
        "token_count": len(tokens),
        "accepted_tokens": dict(sorted(tokens.items())),
    }


async def discover_real_response_fields(city: str = "上海") -> dict:
    """Discover actually returned fields from real Anjuke search output."""
    client = AnjukeClient()
    houses = await client.search(SearchFilter(city=city))

    non_empty: set[str] = set()
    for house in houses:
        row = asdict(house)
        for key, value in row.items():
            if value not in (None, "", [], {}):
                non_empty.add(key)

    return {
        "city": city,
        "sample_size": len(houses),
        "non_empty_fields": sorted(non_empty),
    }
