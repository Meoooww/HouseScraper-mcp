import asyncio

from house_cli.client.adapters.anjuke_probe import (
    discover_real_filter_inputs,
    discover_real_response_fields,
)


def test_discover_real_filter_inputs_from_homepage_links():
    result = asyncio.run(discover_real_filter_inputs("上海"))

    assert result["city"] == "上海"
    assert result["source"] == "homepage_sale_links"
    assert result["token_count"] > 0

    tokens = result["accepted_tokens"]
    assert "pudong" in tokens
    assert tokens["pudong"]["label"] == "浦东"

    assert "m13471" in tokens
    assert tokens["m13471"]["label"] == "100-200万"


def test_discover_real_response_fields_from_search_results():
    result = asyncio.run(discover_real_response_fields("上海"))

    assert result["city"] == "上海"
    assert result["sample_size"] > 0

    non_empty = set(result["non_empty_fields"])
    for required in ["id", "platform", "title", "price", "area", "layout", "district", "city", "url"]:
        assert required in non_empty
