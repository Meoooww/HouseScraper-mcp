import pytest

from housescraper_mcp.cli import main


def test_search_cli_no_longer_accepts_sort_by() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["search", "--sort-by", "price"])

    assert exc_info.value.code == 2
