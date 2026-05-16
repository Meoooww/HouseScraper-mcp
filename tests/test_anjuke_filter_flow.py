from house_cli.client.adapters.anjuke import AnjukeClient
from house_cli.models.filter import SearchFilter


def test_anjuke_filter_flow_contract_exposes_input_and_output_schema():
    client = AnjukeClient()

    contract = client.filter_flow_contract()

    assert contract["flow_name"] == "anjuke_sale_filter_flow"
    assert contract["entry_url_template"] == "https://{city}.anjuke.com/sale/?from=HomePage_Search"

    accepted = contract["accepted_params"]
    assert accepted["city"]["required"] is True
    assert accepted["district"]["required"] is False
    assert accepted["min_price"]["type"] == "number"
    assert accepted["max_price"]["type"] == "number"
    assert accepted["page"]["type"] == "integer"
    assert accepted["keywords"]["type"] == "string"

    returned = contract["response_fields"]
    assert "id" in returned
    assert "platform" in returned
    assert "title" in returned
    assert "price" in returned
    assert "area" in returned
    assert "unit_price" in returned
    assert "url" in returned


def test_anjuke_filter_flow_entry_normalizes_non_empty_filter_values():
    client = AnjukeClient()
    filters = SearchFilter(
        city="上海",
        district="浦东",
        min_price=200.0,
        max_price=500.0,
        min_area=60.0,
        max_area=120.0,
        layout="2室",
        sort_by="price_desc",
        page=3,
        keywords="近地铁",
        listing_type="buy",
    )

    entry = client.build_filter_flow_entry(filters)

    assert entry["url_template"] == "https://{resolved_city_slug}.anjuke.com/sale/?from=HomePage_Search"
    assert entry["source"] == "HomePage_Search"
    assert entry["platform"] == "anjuke"

    request_params = entry["request_params"]
    assert request_params == {
        "city": "上海",
        "district": "浦东",
        "min_price": 200.0,
        "max_price": 500.0,
        "min_area": 60.0,
        "max_area": 120.0,
        "layout": "2室",
        "sort_by": "price_desc",
        "page": 3,
        "keywords": "近地铁",
        "listing_type": "buy",
    }
