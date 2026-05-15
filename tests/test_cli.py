import pytest

from housescraper_mcp.cli import build_parser, main


def test_search_cli_no_longer_accepts_sort_by() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["search", "--sort-by", "price"])

    assert exc_info.value.code == 2


def test_search_cli_accepts_keyword_argument() -> None:
    args = build_parser().parse_args(["search", "--keyword", "世茂滨江花园"])

    assert args.command == "search"
    assert args.keyword == "世茂滨江花园"


def test_detail_cli_accepts_listing_ref_argument() -> None:
    args = build_parser().parse_args(["detail", "--listing-ref", "beike:107114117310"])

    assert args.command == "detail"
    assert args.listing_ref == "beike:107114117310"


def test_search_cli_accepts_buy_side_summary_arguments() -> None:
    args = build_parser().parse_args(
        ["search", "--city", "珠海", "--layouts", "1室", "2室", "--max-unit-price", "5000"]
    )

    assert args.command == "search"
    assert args.layouts == ["1室", "2室"]
    assert args.max_unit_price == 5000


def test_search_cli_accepts_detail_verify_limit_argument() -> None:
    args = build_parser().parse_args(["search", "--detail-verify-limit", "1"])

    assert args.command == "search"
    assert args.detail_verify_limit == 1


def test_baseline_cli_accepts_single_city_argument() -> None:
    args = build_parser().parse_args(["baseline", "--city", "珠海"])

    assert args.command == "baseline"
    assert args.city == "珠海"
