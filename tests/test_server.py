import pytest

from housescraper_mcp.server import search_listings


def test_search_listings_does_not_accept_sort_by() -> None:
    with pytest.raises(TypeError, match="sort_by"):
        search_listings(sort_by="price")
