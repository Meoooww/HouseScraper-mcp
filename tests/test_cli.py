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
