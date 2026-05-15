from house_cli.models.filter import SearchFilter

from housescraper_mcp.buy_side_screening import (
    UNCERTAIN_OWNERSHIP,
    UNCERTAIN_RESIDENTIAL_USE,
    UNCERTAIN_UNIT_PRICE,
    apply_buy_side_screening,
    buy_side_screening_requested,
)


def test_buy_side_screening_requested_for_summary_inputs() -> None:
    filters = SearchFilter(city="珠海")
    filters.layouts = ["1室", "2室"]
    filters.max_unit_price = 5000.0

    assert buy_side_screening_requested(filters) is True


def test_apply_buy_side_screening_marks_missing_effective_unit_price_as_b() -> None:
    filters = SearchFilter(city="珠海", min_area=40, max_area=70)
    filters.layouts = ["1室", "2室"]
    filters.max_unit_price = 5000.0

    results = apply_buy_side_screening(
        [
            {
                "id": "needs-review",
                "platform": "lianjia",
                "title": "低总价一居室",
                "price": 0.0,
                "area": 50.0,
                "unit_price": None,
                "layout": "1室1厅",
                "tags": [],
            }
        ],
        filters,
    )

    assert results[0]["eligibility_tier"] == "B"
    assert results[0]["uncertain_reasons"] == [
        UNCERTAIN_UNIT_PRICE,
        UNCERTAIN_OWNERSHIP,
        UNCERTAIN_RESIDENTIAL_USE,
    ]
