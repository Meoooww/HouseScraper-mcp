import asyncio

import pytest

import housescraper_mcp.server as server
from housescraper_mcp.server import get_listing_detail, search_listings


def test_search_listings_does_not_accept_sort_by() -> None:
    with pytest.raises(TypeError, match="sort_by"):
        search_listings(sort_by="price")


def test_search_listings_accepts_keyword_and_passes_it_to_search_filter(monkeypatch) -> None:
    captured = {}

    class FakeService:
        async def search(self, filters, *, platforms=None, limit=20):
            captured["keywords"] = filters.keywords
            captured["platforms"] = platforms
            captured["limit"] = limit
            return {"status": "success", "meta": {}, "data": []}

    monkeypatch.setattr(server, "service", FakeService())

    response = asyncio.run(
        search_listings(
            city="上海",
            platforms=["beike"],
            keyword="世茂滨江花园",
            limit=5,
        )
    )

    assert response["status"] == "success"
    assert captured["keywords"] == "世茂滨江花园"
    assert captured["platforms"] == ["beike"]
    assert captured["limit"] == 5


def test_get_listing_detail_accepts_listing_ref_and_passes_it_to_service(monkeypatch) -> None:
    captured = {}

    class FakeService:
        async def detail(self, listing_ref):
            captured["listing_ref"] = listing_ref
            return {"status": "success", "meta": {}, "data": {"listing_ref": listing_ref}}

    monkeypatch.setattr(server, "service", FakeService())

    response = asyncio.run(get_listing_detail(listing_ref="beike:107114117310"))

    assert response["status"] == "success"
    assert captured["listing_ref"] == "beike:107114117310"
    assert response["data"]["listing_ref"] == "beike:107114117310"
