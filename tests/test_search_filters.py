from click.testing import CliRunner

from house_cli.commands.search import search
from house_cli.models.house import House


def test_search_applies_hard_filters_including_max_unit_price(monkeypatch):
    async def fake_search_all(adapters, filters):
        return [
            House(
                id="ok-1",
                platform="anjuke",
                title="标准一居",
                price=180.0,
                price_unit="万",
                area=45.0,
                unit_price=40000.0,
                layout="1室1厅",
                district="浦东",
                city="上海",
                url="https://example.com/ok-1",
            ),
            House(
                id="bad-unit-price",
                platform="anjuke",
                title="单价超标",
                price=180.0,
                price_unit="万",
                area=45.0,
                unit_price=55000.0,
                layout="1室1厅",
                district="浦东",
                city="上海",
                url="https://example.com/bad-unit-price",
            ),
            House(
                id="bad-layout",
                platform="anjuke",
                title="三居",
                price=300.0,
                price_unit="万",
                area=100.0,
                unit_price=30000.0,
                layout="3室2厅",
                district="浦东",
                city="上海",
                url="https://example.com/bad-layout",
            ),
        ]

    monkeypatch.setattr("house_cli.commands.search._search_all", fake_search_all)
    monkeypatch.setattr("house_cli.commands.search.get_adapters", lambda platform, listing_type: [object()])

    runner = CliRunner()
    result = runner.invoke(
        search,
        [
            "--platform",
            "anjuke",
            "--city",
            "上海",
            "--district",
            "浦东",
            "--max-unit-price",
            "45000",
            "--layout",
            "1室",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": "ok-1"' in result.output
    assert '"id": "bad-unit-price"' not in result.output
    assert '"id": "bad-layout"' not in result.output


def test_search_filters_out_anjuke_recommendation_flow_results(monkeypatch):
    async def fake_search_all(adapters, filters):
        return [
            House(
                id="recommend-flow",
                platform="anjuke",
                title="推荐流房源",
                price=200.0,
                price_unit="万",
                area=50.0,
                unit_price=40000.0,
                layout="1室1厅",
                district="浦东",
                city="上海",
                url="https://shanghai.anjuke.com/prop/view/abc?from=HomePage_RecommendHouse",
            ),
            House(
                id="normal-flow",
                platform="anjuke",
                title="筛选流房源",
                price=210.0,
                price_unit="万",
                area=50.0,
                unit_price=41000.0,
                layout="1室1厅",
                district="浦东",
                city="上海",
                url="https://shanghai.anjuke.com/prop/view/def?from=HomePage_Search",
            ),
        ]

    monkeypatch.setattr("house_cli.commands.search._search_all", fake_search_all)
    monkeypatch.setattr("house_cli.commands.search.get_adapters", lambda platform, listing_type: [object()])

    runner = CliRunner()
    result = runner.invoke(
        search,
        [
            "--platform",
            "anjuke",
            "--city",
            "上海",
            "--district",
            "浦东",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": "normal-flow"' in result.output
    assert '"id": "recommend-flow"' not in result.output


def test_search_keeps_anjuke_recommendation_flow_when_it_is_the_only_source(monkeypatch):
    async def fake_search_all(adapters, filters):
        return [
            House(
                id="recommend-only",
                platform="anjuke",
                title="推荐流兜底房源",
                price=200.0,
                price_unit="万",
                area=50.0,
                unit_price=40000.0,
                layout="1室1厅",
                district="浦东",
                city="上海",
                url="https://shanghai.anjuke.com/prop/view/abc?from=HomePage_RecommendHouse",
            ),
        ]

    monkeypatch.setattr("house_cli.commands.search._search_all", fake_search_all)
    monkeypatch.setattr("house_cli.commands.search.get_adapters", lambda platform, listing_type: [object()])

    runner = CliRunner()
    result = runner.invoke(
        search,
        [
            "--platform",
            "anjuke",
            "--city",
            "上海",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": "recommend-only"' in result.output


def test_search_can_force_anjuke_recommend_flow(monkeypatch):
    async def fake_search_all(adapters, filters):
        return [
            House(
                id="recommend-flow",
                platform="anjuke",
                title="推荐流房源",
                price=200.0,
                price_unit="万",
                area=50.0,
                unit_price=40000.0,
                layout="1室1厅",
                district="浦东",
                city="上海",
                url="https://shanghai.anjuke.com/prop/view/abc?from=HomePage_RecommendHouse",
            ),
            House(
                id="normal-flow",
                platform="anjuke",
                title="筛选流房源",
                price=210.0,
                price_unit="万",
                area=50.0,
                unit_price=41000.0,
                layout="1室1厅",
                district="浦东",
                city="上海",
                url="https://shanghai.anjuke.com/prop/view/def?from=HomePage_Search",
            ),
        ]

    monkeypatch.setattr("house_cli.commands.search._search_all", fake_search_all)
    monkeypatch.setattr("house_cli.commands.search.get_adapters", lambda platform, listing_type: [object()])

    runner = CliRunner()
    result = runner.invoke(
        search,
        [
            "--platform",
            "anjuke",
            "--city",
            "上海",
            "--anjuke-flow",
            "recommend",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": "recommend-flow"' in result.output
    assert '"id": "normal-flow"' not in result.output
