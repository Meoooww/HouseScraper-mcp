import asyncio

import pytest

import housescraper_mcp.server as server
from housescraper_mcp.server import search_listings


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
