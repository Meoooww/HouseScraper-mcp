import asyncio
from pathlib import Path

import pytest
from house_cli.models.filter import SearchFilter
from house_cli.models.house import House

from housescraper_mcp.artifacts import ArtifactStore
from housescraper_mcp.service import (
    HouseScraperService,
    build_baseline_summary,
    default_adapter_factories,
)


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


def test_search_rejects_page_above_3(tmp_path: Path) -> None:
    service = HouseScraperService(
        adapter_factories={"beike": lambda: FakeAdapter()},
        artifact_store=ArtifactStore(root=tmp_path),
    )

    with pytest.raises(ValueError, match="page must be <= 3"):
        asyncio.run(service.search(SearchFilter(city="上海", page=4), platforms=["beike"]))


def test_search_rejects_limit_above_30(tmp_path: Path) -> None:
    service = HouseScraperService(
        adapter_factories={"beike": lambda: FakeAdapter()},
        artifact_store=ArtifactStore(root=tmp_path),
    )

    with pytest.raises(ValueError, match="limit must be <= 30"):
        asyncio.run(service.search(SearchFilter(city="上海"), platforms=["beike"], limit=31))


def test_probe_returns_status_and_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("housescraper_mcp.service.prepare_cookies", lambda domain, fallback_domains=(): {})

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
            "lianjia": lambda: FakeAdapter(
                [
                    House(
                        id="3",
                        platform="lianjia",
                        title="链家测试房源",
                        price=510.0,
                        price_unit="万",
                        area=92.0,
                        url="https://example.com/3",
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
    assert response["results"][0]["platform"] == "lianjia"
    assert response["results"][0]["result_count"] == 1
    assert response["results"][1]["error_type"] == "captcha"
    assert Path(response["results"][0]["debug_artifact_path"]).exists()


def test_search_returns_partial_results_when_one_platform_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "housescraper_mcp.service.prepare_cookies",
        lambda domain, fallback_domains=(): {"session": "ok"},
    )

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

    assert response["status"] == "partial_success"
    assert response["meta"]["raw_count"] == 1
    assert response["meta"]["returned_count"] == 1
    assert response["meta"]["possible_duplicate_count"] == 0
    assert response["meta"]["truncated"] is False
    assert response["meta"]["platforms"][0]["status"] == "success"
    assert response["meta"]["platforms"][0]["filter_mode"] == "default"
    assert response["meta"]["platforms"][1]["status"] == "error"
    assert response["meta"]["platforms"][1]["filter_mode"] == "default"
    assert response["meta"]["platforms"][1]["error_type"] == "missing_cookies"
    assert response["meta"]["platforms"][1]["error_message"] == "cookie missing"
    assert response["data"][0]["platform"] == "beike"


def test_search_defaults_to_all_supported_platforms_with_agent_friendly_envelope(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "housescraper_mcp.service.prepare_cookies",
        lambda domain, fallback_domains=(): {"session": "ok"},
    )

    service = HouseScraperService(
        adapter_factories={
            "beike": lambda: FakeAdapter(
                [
                    House(
                        id="1",
                        platform="beike",
                        title="贝壳测试房源",
                        price=500.0,
                        price_unit="万",
                        area=89.0,
                        url="https://example.com/1",
                    )
                ]
            ),
            "lianjia": lambda: FakeAdapter(
                [
                    House(
                        id="2",
                        platform="lianjia",
                        title="链家测试房源",
                        price=520.0,
                        price_unit="万",
                        area=91.0,
                        url="https://example.com/2",
                    )
                ]
            ),
            "anjuke": lambda: FakeAdapter(),
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(service.search(SearchFilter(city="上海")))

    assert set(response) == {"status", "meta", "data"}
    assert response["status"] == "success"
    assert response["meta"]["requested_platforms"] == ["beike", "lianjia", "anjuke"]
    assert response["meta"]["resolved_platforms"] == ["beike", "lianjia", "anjuke"]
    assert response["meta"]["raw_count"] == 2
    assert response["meta"]["returned_count"] == 2
    assert response["meta"]["truncated"] is False
    assert response["meta"]["platforms"][0]["status"] == "success"
    assert "ok" not in response["meta"]["platforms"][0]
    assert response["meta"]["platforms"][1]["status"] == "success"
    assert response["meta"]["platforms"][2]["status"] == "no_results"
    assert response["data"][0]["platform"] == "beike"
    assert response["data"][1]["platform"] == "lianjia"


def test_search_returns_no_results_when_filters_eliminate_all_matches(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "housescraper_mcp.service.prepare_cookies",
        lambda domain, fallback_domains=(): {"session": "ok"},
    )

    service = HouseScraperService(
        adapter_factories={
            "beike": lambda: FakeAdapter(
                [
                    House(
                        id="1",
                        platform="beike",
                        title="超预算",
                        price=620.0,
                        price_unit="万",
                        area=96.0,
                        layout="2室2厅",
                        district="浦东",
                        url="https://example.com/1",
                    )
                ]
            )
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

    assert response["status"] == "no_results"
    assert response["meta"]["raw_count"] == 0
    assert response["meta"]["returned_count"] == 0
    assert response["meta"]["truncated"] is False
    assert response["meta"]["platforms"][0]["status"] == "no_results"
    assert response["meta"]["platforms"][0]["filter_mode"] == "post_filtered"
    assert response["meta"]["platforms"][0]["raw_result_count"] == 1
    assert response["data"] == []


def test_search_marks_possible_duplicates_and_moves_them_after_primary_results(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "housescraper_mcp.service.prepare_cookies",
        lambda domain, fallback_domains=(): {"session": "ok"},
    )

    service = HouseScraperService(
        adapter_factories={
            "beike": lambda: FakeAdapter(
                [
                    House(
                        id="1",
                        platform="beike",
                        title="世茂滨江花园南向两房",
                        price=500.0,
                        price_unit="万",
                        area=89.0,
                        layout="2室1厅",
                        community="世茂滨江花园",
                        district="浦东",
                        url="https://example.com/beike/1",
                    )
                ]
            ),
            "lianjia": lambda: FakeAdapter(
                [
                    House(
                        id="2",
                        platform="lianjia",
                        title="世茂滨江花园景观两房",
                        price=520.0,
                        price_unit="万",
                        area=90.5,
                        layout="2室1厅",
                        community="世茂滨江花园",
                        district="浦东",
                        url="https://example.com/lianjia/2",
                    )
                ]
            ),
            "anjuke": lambda: FakeAdapter(
                [
                    House(
                        id="3",
                        platform="anjuke",
                        title="张江独立次新房",
                        price=430.0,
                        price_unit="万",
                        area=78.0,
                        layout="2室1厅",
                        community="张江花园",
                        district="浦东",
                        url="https://example.com/anjuke/3",
                    )
                ]
            ),
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(
        service.search(
            SearchFilter(city="上海"),
            platforms=["beike", "lianjia", "anjuke"],
            limit=10,
        )
    )

    assert response["status"] == "success"
    assert response["meta"]["raw_count"] == 3
    assert response["meta"]["possible_duplicate_count"] == 1
    assert response["meta"]["returned_count"] == 3
    assert response["meta"]["truncated"] is False
    assert response["data"][0]["listing_ref"] == "beike:1"
    assert response["data"][0]["duplicate_id"] is None
    assert response["data"][1]["listing_ref"] == "anjuke:3"
    assert response["data"][1]["duplicate_id"] is None
    assert response["data"][2]["listing_ref"] == "lianjia:2"
    assert response["data"][2]["duplicate_id"] == "beike:1"


def test_search_treats_minor_district_name_variants_as_possible_duplicates(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "housescraper_mcp.service.prepare_cookies",
        lambda domain, fallback_domains=(): {"session": "ok"},
    )

    service = HouseScraperService(
        adapter_factories={
            "beike": lambda: FakeAdapter(
                [
                    House(
                        id="1",
                        platform="beike",
                        title="世茂滨江花园南向两房",
                        price=500.0,
                        price_unit="万",
                        area=89.0,
                        layout="2室1厅",
                        community="世茂滨江花园",
                        district="浦东",
                        url="https://example.com/beike/1",
                    )
                ]
            ),
            "lianjia": lambda: FakeAdapter(
                [
                    House(
                        id="2",
                        platform="lianjia",
                        title="世茂滨江花园景观两房",
                        price=520.0,
                        price_unit="万",
                        area=90.5,
                        layout="2室1厅",
                        community="世茂滨江花园",
                        district="浦东新区",
                        url="https://example.com/lianjia/2",
                    )
                ]
            ),
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(
        service.search(
            SearchFilter(city="上海"),
            platforms=["beike", "lianjia"],
            limit=10,
        )
    )

    assert response["meta"]["possible_duplicate_count"] == 1
    assert response["data"][1]["listing_ref"] == "lianjia:2"
    assert response["data"][1]["duplicate_id"] == "beike:1"


def test_search_counts_possible_duplicates_toward_limit(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "housescraper_mcp.service.prepare_cookies",
        lambda domain, fallback_domains=(): {"session": "ok"},
    )

    service = HouseScraperService(
        adapter_factories={
            "beike": lambda: FakeAdapter(
                [
                    House(
                        id="1",
                        platform="beike",
                        title="世茂滨江花园南向两房",
                        price=500.0,
                        price_unit="万",
                        area=89.0,
                        layout="2室1厅",
                        community="世茂滨江花园",
                        district="浦东",
                        url="https://example.com/beike/1",
                    )
                ]
            ),
            "lianjia": lambda: FakeAdapter(
                [
                    House(
                        id="2",
                        platform="lianjia",
                        title="世茂滨江花园景观两房",
                        price=520.0,
                        price_unit="万",
                        area=90.5,
                        layout="2室1厅",
                        community="世茂滨江花园",
                        district="浦东",
                        url="https://example.com/lianjia/2",
                    )
                ]
            ),
            "anjuke": lambda: FakeAdapter(
                [
                    House(
                        id="3",
                        platform="anjuke",
                        title="张江独立次新房",
                        price=430.0,
                        price_unit="万",
                        area=78.0,
                        layout="2室1厅",
                        community="张江花园",
                        district="浦东",
                        url="https://example.com/anjuke/3",
                    )
                ]
            ),
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(
        service.search(
            SearchFilter(city="上海"),
            platforms=["beike", "lianjia", "anjuke"],
            limit=2,
        )
    )

    assert response["meta"]["raw_count"] == 3
    assert response["meta"]["possible_duplicate_count"] == 1
    assert response["meta"]["returned_count"] == 2
    assert response["meta"]["truncated"] is True
    assert [listing["listing_ref"] for listing in response["data"]] == ["beike:1", "anjuke:3"]


def test_search_returns_error_when_all_platforms_fail(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "housescraper_mcp.service.prepare_cookies",
        lambda domain, fallback_domains=(): {"session": "ok"},
    )

    service = HouseScraperService(
        adapter_factories={
            "beike": lambda: FakeAdapter(error=RuntimeError("captcha required")),
            "anjuke": lambda: FakeAdapter(error=RuntimeError("cookie missing")),
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(
        service.search(SearchFilter(city="上海"), platforms=["beike", "anjuke"], limit=10)
    )

    assert response["status"] == "error"
    assert response["meta"]["raw_count"] == 0
    assert response["meta"]["returned_count"] == 0
    assert response["meta"]["platforms"][0]["status"] == "error"
    assert response["meta"]["platforms"][1]["status"] == "error"
    assert response["data"] == []


def test_search_applies_client_side_filters(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "housescraper_mcp.service.prepare_cookies",
        lambda domain, fallback_domains=(): {"session": "ok"},
    )

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

    assert response["meta"]["client_side_filtering"] is True
    assert response["meta"]["raw_count"] == 1
    assert response["meta"]["platforms"][0]["raw_result_count"] == 2
    assert response["meta"]["platforms"][0]["filter_mode"] == "post_filtered"
    assert response["data"][0]["title"] == "符合条件"


def test_search_reports_native_filter_mode_for_platforms_that_keep_upstream_filters(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "housescraper_mcp.service.prepare_cookies",
        lambda domain, fallback_domains=(): {"session": "ok"},
    )

    service = HouseScraperService(
        adapter_factories={
            "anjuke": lambda: FakeAdapter(
                [
                    House(
                        id="1",
                        platform="anjuke",
                        title="安居客符合条件",
                        price=480.0,
                        price_unit="万",
                        area=88.0,
                        layout="2室1厅",
                        district="浦东",
                        url="https://example.com/1",
                    )
                ]
            )
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(
        service.search(
            SearchFilter(city="上海", max_price=500, layout="2室", district="浦东"),
            platforms=["anjuke"],
            limit=10,
        )
    )

    assert response["meta"]["platforms"][0]["status"] == "success"
    assert response["meta"]["platforms"][0]["filter_mode"] == "native"
    assert response["data"][0]["platform"] == "anjuke"


def test_search_relaxes_beike_server_filters_before_client_filtering(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "housescraper_mcp.service.prepare_cookies",
        lambda domain, fallback_domains=(): {"session": "ok"},
    )

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
    assert response["meta"]["raw_count"] == 1
    assert response["data"][0]["title"] == "符合条件"


def test_search_relaxes_lianjia_server_filters_before_client_filtering(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "housescraper_mcp.service.prepare_cookies",
        lambda domain, fallback_domains=(): {"session": "ok"},
    )

    adapter = FakeAdapter(
        [
            House(
                id="1",
                platform="lianjia",
                title="链家符合条件",
                price=480.0,
                price_unit="万",
                area=88.0,
                layout="2室1厅",
                district="浦东",
                url="https://example.com/1",
            )
        ]
    )

    service = HouseScraperService(
        adapter_factories={"lianjia": lambda: adapter},
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(
        service.search(
            SearchFilter(city="上海", max_price=500, layout="2室", district="浦东"),
            platforms=["lianjia"],
            limit=10,
        )
    )

    assert adapter.last_filters is not None
    assert adapter.last_filters.max_price is None
    assert adapter.last_filters.layout == ""
    assert adapter.last_filters.district == ""
    assert response["meta"]["raw_count"] == 1
    assert response["data"][0]["platform"] == "lianjia"


def test_baseline_returns_report_and_per_platform_summary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "housescraper_mcp.service.prepare_cookies",
        lambda domain, fallback_domains=(): {"session": "ok"},
    )

    service = HouseScraperService(
        adapter_factories={
            "beike": lambda: FakeAdapter(
                [
                    House(
                        id="1",
                        platform="beike",
                        title="基线样本",
                        price=320.0,
                        price_unit="万",
                        area=78.0,
                        layout="2室1厅",
                        district="浦东",
                        url="https://example.com/1",
                    )
                ]
            ),
            "lianjia": lambda: FakeAdapter(
                [
                    House(
                        id="3",
                        platform="lianjia",
                        title="链家基线样本",
                        price=310.0,
                        price_unit="万",
                        area=74.0,
                        layout="2室1厅",
                        district="浦东",
                        url="https://example.com/3",
                    )
                ]
            ),
            "anjuke": lambda: FakeAdapter(
                [
                    House(
                        id="2",
                        platform="anjuke",
                        title="安居客样本",
                        price=300.0,
                        price_unit="万",
                        area=76.0,
                        layout="2室1厅",
                        district="浦东",
                        url="https://example.com/2",
                    )
                ]
            ),
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(
        service.baseline(
            city="上海",
            platforms=["beike", "lianjia", "anjuke"],
            search_limit=5,
        )
    )

    assert response["ok"] is True
    assert response["requested_platforms"] == ["beike", "lianjia", "anjuke"]
    assert response["platform_summary"][1]["requested_platform"] == "lianjia"
    assert response["platform_summary"][1]["platform"] == "lianjia"
    assert Path(response["report_artifact_path"]).exists()


def test_build_baseline_summary_combines_probe_and_search_status() -> None:
    probe_response = {
        "requested_platforms": ["beike", "anjuke"],
        "results": [
            {
                "requested_platform": "beike",
                "platform": "beike",
                "ok": True,
                "raw_result_count": 30,
                "error_type": None,
                "captcha_suspected": False,
            },
            {
                "requested_platform": "anjuke",
                "platform": "anjuke",
                "ok": False,
                "raw_result_count": 0,
                "error_type": "captcha",
                "captcha_suspected": True,
            },
        ],
    }
    search_response = {
        "meta": {
            "platforms": [
                {
                    "requested_platform": "beike",
                    "status": "success",
                    "result_count": 5,
                    "raw_result_count": 30,
                    "error_type": None,
                    "captcha_suspected": False,
                },
                {
                    "requested_platform": "anjuke",
                    "status": "error",
                    "result_count": 0,
                    "raw_result_count": 0,
                    "error_type": "captcha",
                    "captcha_suspected": True,
                },
            ]
        }
    }

    summary = build_baseline_summary(probe_response, search_response)

    assert summary[0]["requested_platform"] == "beike"
    assert summary[0]["search_result_count"] == 5
    assert summary[1]["probe_captcha_suspected"] is True
    assert summary[1]["search_error_type"] == "captcha"


def test_default_adapter_factories_include_separate_lianjia_adapter() -> None:
    factories = default_adapter_factories()

    assert "beike" in factories
    assert "lianjia" in factories
    assert "anjuke" in factories
