import asyncio
from pathlib import Path

from house_cli.models.filter import SearchFilter
from house_cli.models.house import House

from housescraper_mcp.artifacts import ArtifactStore
from housescraper_mcp.service import HouseScraperService, prepare_cookies


class FakeAdapter:
    def __init__(self, houses=None, error: Exception | None = None) -> None:
        self._houses = houses or []
        self._error = error
        self.last_filters: SearchFilter | None = None

    async def search(self, filters: SearchFilter) -> list[House]:
        self.last_filters = filters
        if self._error is not None:
            raise self._error
        return self._houses


def test_probe_returns_status_and_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("housescraper_mcp.service.prepare_cookies", lambda domain: {})

    service = HouseScraperService(
        adapter_factories={
            "beike": lambda: FakeAdapter(
                [
                    House(
                        id="1",
                        platform="beike",
                        title="测试房源",
                        price=500.0,
                        price_unit="万",
                        area=89.0,
                        url="https://example.com/1",
                    )
                ]
            ),
            "anjuke": lambda: FakeAdapter(error=RuntimeError("captcha required")),
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(service.probe(SearchFilter(city="上海"), platforms=["lianjia", "anjuke"]))

    assert response["ok"] is True
    assert response["results"][0]["requested_platform"] == "lianjia"
    assert response["results"][0]["platform"] == "beike"
    assert response["results"][0]["result_count"] == 1
    assert response["results"][1]["error_type"] == "captcha"
    assert Path(response["results"][0]["debug_artifact_path"]).exists()


def test_search_returns_partial_results_when_one_platform_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("housescraper_mcp.service.prepare_cookies", lambda domain: {"session": "ok"})

    service = HouseScraperService(
        adapter_factories={
            "beike": lambda: FakeAdapter(
                [
                    House(
                        id="1",
                        platform="beike",
                        title="测试房源A",
                        price=500.0,
                        price_unit="万",
                        area=89.0,
                        url="https://example.com/1",
                    )
                ]
            ),
            "anjuke": lambda: FakeAdapter(error=RuntimeError("cookie missing")),
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(service.search(SearchFilter(city="上海"), platforms=["beike", "anjuke"], limit=10))

    assert response["ok"] is True
    assert response["result_count"] == 1
    assert response["results"][0]["platform"] == "beike"
    assert response["platform_status"][1]["error_type"] == "missing_cookies"


def test_search_applies_client_side_filters(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("housescraper_mcp.service.prepare_cookies", lambda domain: {"session": "ok"})

    service = HouseScraperService(
        adapter_factories={
            "beike": lambda: FakeAdapter(
                [
                    House(
                        id="1",
                        platform="beike",
                        title="符合条件",
                        price=480.0,
                        price_unit="万",
                        area=88.0,
                        layout="2室1厅",
                        district="浦东",
                        url="https://example.com/1",
                    ),
                    House(
                        id="2",
                        platform="beike",
                        title="超预算",
                        price=620.0,
                        price_unit="万",
                        area=96.0,
                        layout="2室2厅",
                        district="浦东",
                        url="https://example.com/2",
                    ),
                ]
            ),
            "anjuke": lambda: FakeAdapter(),
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(
        service.search(
            SearchFilter(city="上海", max_price=500, layout="2室", district="浦东"),
            platforms=["beike"],
            limit=10,
        )
    )

    assert response["client_side_filtering"] is True
    assert response["result_count"] == 1
    assert response["results"][0]["title"] == "符合条件"
    assert response["platform_status"][0]["raw_result_count"] == 2


def test_prepare_cookies_merges_browser_values_into_cached_file(monkeypatch) -> None:
    saved: dict[str, dict[str, str]] = {}

    monkeypatch.setattr("housescraper_mcp.service.get_cookies", lambda domain: {"lianjia_ssid": "old"})
    monkeypatch.setattr(
        "housescraper_mcp.service._try_browser_cookie3",
        lambda domain: {"lianjia_ssid": "new", "hip": "ok", "srcid": "1"},
    )
    monkeypatch.setattr(
        "housescraper_mcp.service.save_cookies",
        lambda domain, cookies: saved.setdefault(domain, cookies),
    )

    cookies = prepare_cookies("ke.com")

    assert cookies["lianjia_ssid"] == "new"
    assert cookies["hip"] == "ok"
    assert saved["ke.com"]["srcid"] == "1"


def test_search_relaxes_beike_server_filters_before_client_filtering(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("housescraper_mcp.service.prepare_cookies", lambda domain: {"session": "ok"})

    adapter = FakeAdapter(
        [
            House(
                id="1",
                platform="beike",
                title="符合条件",
                price=480.0,
                price_unit="万",
                area=88.0,
                layout="2室1厅",
                district="浦东",
                url="https://example.com/1",
            ),
            House(
                id="2",
                platform="beike",
                title="超预算",
                price=620.0,
                price_unit="万",
                area=96.0,
                layout="2室2厅",
                district="浦东",
                url="https://example.com/2",
            ),
        ]
    )

    service = HouseScraperService(
        adapter_factories={"beike": lambda: adapter},
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(
        service.search(
            SearchFilter(city="上海", max_price=500, layout="2室", district="浦东"),
            platforms=["beike"],
            limit=10,
        )
    )

    assert adapter.last_filters is not None
    assert adapter.last_filters.max_price is None
    assert adapter.last_filters.layout == ""
    assert adapter.last_filters.district == ""
    assert response["result_count"] == 1
    assert response["results"][0]["title"] == "符合条件"
