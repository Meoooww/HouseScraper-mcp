import asyncio
from pathlib import Path

import pytest
from house_cli.models.filter import SearchFilter
from house_cli.models.house import House
from house_cli.models.house import HouseDetail

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
        self.search_filters_history: list[SearchFilter] = []

    async def search(self, filters: SearchFilter) -> list[House]:
        self.last_filters = filters
        self.search_filters_history.append(filters)
        if self._error is not None:
            raise self._error
        return self._houses


class FakeDetailAdapter(FakeAdapter):
    def __init__(
        self,
        detail: HouseDetail | None = None,
        error: Exception | None = None,
        *,
        details_by_id: dict[str, HouseDetail] | None = None,
        errors_by_id: dict[str, Exception] | None = None,
    ) -> None:
        super().__init__(houses=[], error=error)
        self._detail = detail
        self._details_by_id = details_by_id or {}
        self._errors_by_id = errors_by_id or {}
        self.last_detail_id: str | None = None
        self.last_detail_city: str | None = None
        self.last_detail_url: str | None = None
        self.detail_calls: list[str] = []

    async def detail(
        self,
        house_id: str,
        *,
        city: str | None = None,
        url: str | None = None,
    ) -> HouseDetail:
        self.last_detail_id = house_id
        self.last_detail_city = city
        self.last_detail_url = url
        self.detail_calls.append(house_id)
        if house_id in self._errors_by_id:
            raise self._errors_by_id[house_id]
        if house_id in self._details_by_id:
            return self._details_by_id[house_id]
        if self._error is not None:
            raise self._error
        if self._detail is None:
            raise RuntimeError("detail missing")
        return self._detail


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


def test_search_propagates_single_city_to_all_platforms(tmp_path: Path) -> None:
    beike_adapter = FakeAdapter()
    lianjia_adapter = FakeAdapter()
    anjuke_adapter = FakeAdapter()
    service = HouseScraperService(
        adapter_factories={
            "beike": lambda: beike_adapter,
            "lianjia": lambda: lianjia_adapter,
            "anjuke": lambda: anjuke_adapter,
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )

    asyncio.run(
        service.search(
            SearchFilter(city="珠海"),
            platforms=["beike", "lianjia", "anjuke"],
            limit=10,
        )
    )

    assert [f.city for f in beike_adapter.search_filters_history] == ["珠海"]
    assert [f.city for f in lianjia_adapter.search_filters_history] == ["珠海"]
    assert [f.city for f in anjuke_adapter.search_filters_history] == ["珠海"]


def test_search_keeps_platform_error_honest_for_city_routing_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "housescraper_mcp.service.prepare_cookies",
        lambda domain, fallback_domains=(): {"session": "ok"},
    )
    beike_adapter = FakeAdapter(
        [
            House(
                id="1",
                platform="beike",
                title="基线样本",
                price=320.0,
                price_unit="万",
                area=78.0,
                layout="2室1厅",
                district="香洲",
                city="珠海",
                url="https://example.com/1",
            )
        ]
    )
    lianjia_adapter = FakeAdapter(error=RuntimeError("Unsupported city for lianjia: 不存在城市"))
    anjuke_adapter = FakeAdapter(
        [
            House(
                id="2",
                platform="anjuke",
                title="安居客样本",
                price=300.0,
                price_unit="万",
                area=76.0,
                layout="2室1厅",
                district="香洲",
                city="珠海",
                url="https://example.com/2",
            )
        ]
    )
    service = HouseScraperService(
        adapter_factories={
            "beike": lambda: beike_adapter,
            "lianjia": lambda: lianjia_adapter,
            "anjuke": lambda: anjuke_adapter,
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(
        service.search(
            SearchFilter(city="不存在城市"),
            platforms=["beike", "lianjia", "anjuke"],
            limit=10,
        )
    )

    assert response["status"] == "partial_success"
    meta_by_requested = {item["requested_platform"]: item for item in response["meta"]["platforms"]}
    assert meta_by_requested["lianjia"]["status"] == "error"
    assert meta_by_requested["lianjia"]["error_type"] == "adapter_error"
    assert meta_by_requested["beike"]["status"] == "success"
    assert meta_by_requested["anjuke"]["status"] == "success"


def test_detail_returns_structured_fields_for_listing_ref(tmp_path: Path) -> None:
    adapter = FakeDetailAdapter(
        detail=HouseDetail(
            id="107114117310",
            platform="beike",
            title="世茂滨江花园南向两房",
            price=1249.0,
            price_unit="万",
            area=143.2,
            unit_price=87221.0,
            layout="2室2厅",
            floor="低楼层",
            orientation="东 南",
            community="世茂滨江花园",
            district="浦东",
            city="上海",
            address="陆家嘴 世茂滨江花园",
            url="https://sh.ke.com/ershoufang/107114117310.html",
            listing_date="7月前发布",
            tags=["必看好房", "近地铁"],
            description="正南大客厅，落地窗森系景观。",
            building_year="2004年",
            building_type="塔楼",
            elevator="有",
            parking="充足",
            green_ratio="35%",
            volume_ratio="2.5",
            property_fee="6元/平/月",
            nearby_schools=["明珠小学"],
            nearby_subway=["2号线陆家嘴"],
            price_history=[],
            images=["https://example.com/1.jpg"],
        )
    )

    service = HouseScraperService(
        adapter_factories={"beike": lambda: adapter},
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(service.detail("beike:107114117310"))

    assert adapter.last_detail_id == "107114117310"
    assert response["status"] == "success"
    assert response["meta"]["platform"] == "beike"
    assert response["meta"]["listing_ref"] == "beike:107114117310"
    assert response["data"]["listing_ref"] == "beike:107114117310"
    assert response["data"]["title"] == "世茂滨江花园南向两房"
    assert response["data"]["price"] == 1249.0
    assert response["data"]["unit_price"] == 87221.0
    assert response["data"]["community"] == "世茂滨江花园"
    assert response["data"]["layout"] == "2室2厅"


def test_detail_surfaces_platform_errors_for_missing_cookies(tmp_path: Path) -> None:
    adapter = FakeDetailAdapter(error=RuntimeError("cookie missing"))

    service = HouseScraperService(
        adapter_factories={"anjuke": lambda: adapter},
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(service.detail("anjuke:S123"))

    assert adapter.last_detail_id == "S123"
    assert response["status"] == "error"
    assert response["meta"]["listing_ref"] == "anjuke:S123"
    assert response["meta"]["platform"] == "anjuke"
    assert response["meta"]["error_type"] == "missing_cookies"
    assert response["meta"]["error_message"] == "cookie missing"
    assert response["data"] is None


def test_detail_surfaces_platform_errors_for_captcha(tmp_path: Path) -> None:
    adapter = FakeDetailAdapter(error=RuntimeError("captcha required"))

    service = HouseScraperService(
        adapter_factories={"beike": lambda: adapter},
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(service.detail("beike:107114117310"))

    assert adapter.last_detail_id == "107114117310"
    assert response["status"] == "error"
    assert response["meta"]["platform"] == "beike"
    assert response["meta"]["error_type"] == "captcha"
    assert response["meta"]["error_message"] == "captcha required"
    assert response["data"] is None


def test_detail_uses_cached_city_context_from_search_results(tmp_path: Path) -> None:
    adapter = FakeDetailAdapter(
        detail=HouseDetail(
            id="105121773212",
            platform="lianjia",
            title="嘉年华国际公寓 1室0厅 南",
            price=50.0,
            price_unit="万",
            area=43.58,
            unit_price=11474.0,
            layout="1室0厅",
            floor="高楼层(共29层)",
            orientation="南",
            community="嘉年华国际公寓",
            district="吉大",
            city="珠海",
            address="",
            url="https://zh.lianjia.com/ershoufang/105121773212.html",
            listing_date="8个月以前发布",
            tags=["房本满五年"],
            description="珠海吉大公寓",
            building_year="2008年",
            building_type="塔楼",
            elevator="有",
            parking="有",
            green_ratio="30%",
            volume_ratio="2.0",
            property_fee="3元/平/月",
            nearby_schools=[],
            nearby_subway=[],
            price_history=[],
            images=[],
        )
    )
    adapter._houses = [
        House(
            id="105121773212",
            platform="lianjia",
            title="嘉年华国际公寓 1室0厅 南",
            price=50.0,
            price_unit="万",
            area=43.58,
            unit_price=11474.0,
            layout="1室0厅",
            community="嘉年华国际公寓",
            district="吉大",
            city="珠海",
            url="https://zh.lianjia.com/ershoufang/105121773212.html",
        )
    ]

    service = HouseScraperService(
        adapter_factories={"lianjia": lambda: adapter},
        artifact_store=ArtifactStore(root=tmp_path),
    )

    search_response = asyncio.run(service.search(SearchFilter(city="珠海"), platforms=["lianjia"], limit=5))
    listing_ref = search_response["data"][0]["listing_ref"]

    detail_response = asyncio.run(service.detail(listing_ref))

    assert listing_ref == "lianjia:105121773212"
    assert adapter.last_detail_id == "105121773212"
    assert adapter.last_detail_city == "珠海"
    assert adapter.last_detail_url == "https://zh.lianjia.com/ershoufang/105121773212.html"
    assert detail_response["status"] == "success"
    assert detail_response["data"]["listing_ref"] == "lianjia:105121773212"


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


def test_search_filters_by_layouts_and_max_unit_price(tmp_path: Path) -> None:
    service = HouseScraperService(
        adapter_factories={
            "lianjia": lambda: FakeAdapter(
                [
                    House(
                        id="too-expensive",
                        platform="lianjia",
                        title="单价过高的一居室",
                        price=30.0,
                        price_unit="万",
                        area=50.0,
                        unit_price=6001.0,
                        layout="1室1厅",
                        city="珠海",
                        url="https://zh.lianjia.com/ershoufang/too-expensive.html",
                    ),
                    House(
                        id="derived-ok",
                        platform="lianjia",
                        title="可用总价和面积推导单价的两居",
                        price=28.0,
                        price_unit="万",
                        area=70.0,
                        unit_price=None,
                        layout="2室1厅",
                        city="珠海",
                        url="https://zh.lianjia.com/ershoufang/derived-ok.html",
                    ),
                    House(
                        id="wrong-layout",
                        platform="lianjia",
                        title="户型明确不满足的三居",
                        price=21.0,
                        price_unit="万",
                        area=60.0,
                        unit_price=3500.0,
                        layout="3室1厅",
                        city="珠海",
                        url="https://zh.lianjia.com/ershoufang/wrong-layout.html",
                    ),
                ]
            )
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )
    filters = SearchFilter(city="珠海")
    filters.layouts = ["1室", "2室"]
    filters.max_unit_price = 5000.0

    response = asyncio.run(service.search(filters, platforms=["lianjia"], limit=10))

    assert response["status"] == "success"
    assert [item["id"] for item in response["data"]] == ["derived-ok"]
    assert response["meta"]["query"]["layouts"] == ["1室", "2室"]
    assert response["meta"]["query"]["max_unit_price"] == 5000.0
    assert response["meta"]["platforms"][0]["filter_mode"] == "post_filtered"
    assert response["meta"]["platforms"][0]["result_count"] == 1


def test_search_buy_side_screening_adds_a_b_tiers_and_sorts_ahead_of_b(tmp_path: Path) -> None:
    service = HouseScraperService(
        adapter_factories={
            "lianjia": lambda: FakeAdapter(
                [
                    House(
                        id="b-cheapest",
                        platform="lianjia",
                        title="低总价小两居",
                        price=28.0,
                        price_unit="万",
                        area=70.0,
                        unit_price=None,
                        layout="2室1厅",
                        city="珠海",
                        url="https://zh.lianjia.com/ershoufang/b-cheapest.html",
                    ),
                    House(
                        id="a-more-expensive",
                        platform="lianjia",
                        title="70年产权纯住宅小两居",
                        price=32.0,
                        price_unit="万",
                        area=64.0,
                        unit_price=5000.0,
                        layout="2室1厅",
                        city="珠海",
                        url="https://zh.lianjia.com/ershoufang/a-more-expensive.html",
                        tags=["70年产权", "纯住宅"],
                    ),
                    House(
                        id="a-cheaper",
                        platform="lianjia",
                        title="70年产权纯住宅一居室",
                        price=22.5,
                        price_unit="万",
                        area=50.0,
                        unit_price=4500.0,
                        layout="1室1厅",
                        city="珠海",
                        url="https://zh.lianjia.com/ershoufang/a-cheaper.html",
                        tags=["70年产权", "纯住宅"],
                    ),
                ]
            )
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )
    filters = SearchFilter(city="珠海", min_area=40, max_area=70)
    filters.layouts = ["1室", "2室"]
    filters.max_unit_price = 5000.0

    response = asyncio.run(service.search(filters, platforms=["lianjia"], limit=10))

    assert [item["id"] for item in response["data"]] == ["a-cheaper", "a-more-expensive", "b-cheapest"]
    assert [item["eligibility_tier"] for item in response["data"]] == ["A", "A", "B"]
    assert response["data"][0]["unit_price_effective"] == 4500.0
    assert response["data"][1]["unit_price_effective"] == 5000.0
    assert response["data"][2]["unit_price_effective"] == 4000.0
    assert response["data"][0]["uncertain_reasons"] == []
    assert response["data"][1]["uncertain_reasons"] == []
    assert response["data"][2]["uncertain_reasons"] == ["ownership_missing", "residential_use_missing"]


def test_search_buy_side_screening_excludes_explicit_non_residential_summary_listings(tmp_path: Path) -> None:
    service = HouseScraperService(
        adapter_factories={
            "lianjia": lambda: FakeAdapter(
                [
                    House(
                        id="excluded-apartment",
                        platform="lianjia",
                        title="70年产权公寓一居室",
                        price=20.0,
                        price_unit="万",
                        area=45.0,
                        unit_price=4444.0,
                        layout="1室1厅",
                        city="珠海",
                        url="https://zh.lianjia.com/ershoufang/excluded-apartment.html",
                        tags=["公寓"],
                    ),
                    House(
                        id="kept-uncertain",
                        platform="lianjia",
                        title="低总价一居室",
                        price=18.0,
                        price_unit="万",
                        area=45.0,
                        unit_price=4000.0,
                        layout="1室1厅",
                        city="珠海",
                        url="https://zh.lianjia.com/ershoufang/kept-uncertain.html",
                    ),
                ]
            )
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )
    filters = SearchFilter(city="珠海", min_area=40, max_area=70)
    filters.layouts = ["1室", "2室"]
    filters.max_unit_price = 5000.0

    response = asyncio.run(service.search(filters, platforms=["lianjia"], limit=10))

    assert [item["id"] for item in response["data"]] == ["kept-uncertain"]
    assert response["data"][0]["eligibility_tier"] == "B"


def test_search_buy_side_screening_returns_no_results_when_screening_excludes_everything(tmp_path: Path) -> None:
    service = HouseScraperService(
        adapter_factories={
            "lianjia": lambda: FakeAdapter(
                [
                    House(
                        id="excluded-apartment",
                        platform="lianjia",
                        title="70年产权公寓一居室",
                        price=20.0,
                        price_unit="万",
                        area=45.0,
                        unit_price=4444.0,
                        layout="1室1厅",
                        city="珠海",
                        url="https://zh.lianjia.com/ershoufang/excluded-apartment.html",
                        tags=["公寓"],
                    )
                ]
            )
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )
    filters = SearchFilter(city="珠海", min_area=40, max_area=70)
    filters.layouts = ["1室", "2室"]
    filters.max_unit_price = 5000.0

    response = asyncio.run(service.search(filters, platforms=["lianjia"], limit=10))

    assert response["status"] == "no_results"
    assert response["meta"]["raw_count"] == 0
    assert response["meta"]["returned_count"] == 0
    assert response["meta"]["platforms"][0]["status"] == "no_results"
    assert response["meta"]["platforms"][0]["result_count"] == 0
    assert response["data"] == []


def test_search_buy_side_screening_promotes_b_listing_to_a_via_bounded_detail_verification(
    tmp_path: Path,
) -> None:
    adapter = FakeDetailAdapter(
        details_by_id={
            "promote-me": HouseDetail(
                id="promote-me",
                platform="lianjia",
                title="70年产权纯住宅一居室",
                price=18.0,
                price_unit="万",
                area=45.0,
                unit_price=4000.0,
                layout="1室1厅",
                floor="中楼层",
                orientation="南",
                community="海边花园",
                district="吉大",
                city="珠海",
                address="吉大 海边花园",
                url="https://zh.lianjia.com/ershoufang/promote-me.html",
                listing_date="1个月前发布",
                tags=["70年产权", "纯住宅"],
                description="明确70年纯住宅。",
                building_year="2010年",
                building_type="板楼",
                elevator="有",
                parking="有",
                green_ratio="30%",
                volume_ratio="2.0",
                property_fee="3元/平/月",
                nearby_schools=[],
                nearby_subway=[],
                price_history=[],
                images=[],
            )
        }
    )
    adapter._houses = [
        House(
            id="excluded-apartment",
            platform="lianjia",
            title="低总价公寓一居室",
            price=15.0,
            price_unit="万",
            area=45.0,
            unit_price=3333.0,
            layout="1室1厅",
            city="珠海",
            url="https://zh.lianjia.com/ershoufang/excluded-apartment.html",
            tags=["公寓"],
        ),
        House(
            id="promote-me",
            platform="lianjia",
            title="低总价一居室",
            price=18.0,
            price_unit="万",
            area=45.0,
            unit_price=4000.0,
            layout="1室1厅",
            city="珠海",
            url="https://zh.lianjia.com/ershoufang/promote-me.html",
        ),
        House(
            id="still-b",
            platform="lianjia",
            title="低总价两居室",
            price=22.5,
            price_unit="万",
            area=50.0,
            unit_price=4500.0,
            layout="2室1厅",
            city="珠海",
            url="https://zh.lianjia.com/ershoufang/still-b.html",
        ),
    ]

    service = HouseScraperService(
        adapter_factories={"lianjia": lambda: adapter},
        artifact_store=ArtifactStore(root=tmp_path),
    )
    filters = SearchFilter(city="珠海", min_area=40, max_area=70)
    filters.layouts = ["1室", "2室"]
    filters.max_unit_price = 5000.0
    filters.detail_verify_limit = 1

    response = asyncio.run(service.search(filters, platforms=["lianjia"], limit=10))

    assert adapter.detail_calls == ["promote-me"]
    assert [item["id"] for item in response["data"]] == ["promote-me", "still-b"]
    assert response["data"][0]["eligibility_tier"] == "A"
    assert response["data"][0]["detail_verification_status"] == "verified"
    assert response["data"][1]["eligibility_tier"] == "B"
    assert response["data"][1]["detail_verification_status"] == "not_requested"
    assert "detail_not_verified" in response["data"][1]["uncertain_reasons"]


def test_search_buy_side_screening_keeps_b_listing_when_detail_verification_fails(tmp_path: Path) -> None:
    adapter = FakeDetailAdapter(errors_by_id={"needs-review": RuntimeError("captcha required")})
    adapter._houses = [
        House(
            id="needs-review",
            platform="lianjia",
            title="低总价一居室",
            price=18.0,
            price_unit="万",
            area=45.0,
            unit_price=4000.0,
            layout="1室1厅",
            city="珠海",
            url="https://zh.lianjia.com/ershoufang/needs-review.html",
        )
    ]

    service = HouseScraperService(
        adapter_factories={"lianjia": lambda: adapter},
        artifact_store=ArtifactStore(root=tmp_path),
    )
    filters = SearchFilter(city="珠海", min_area=40, max_area=70)
    filters.layouts = ["1室", "2室"]
    filters.max_unit_price = 5000.0
    filters.detail_verify_limit = 1

    response = asyncio.run(service.search(filters, platforms=["lianjia"], limit=10))

    assert adapter.detail_calls == ["needs-review"]
    assert response["data"][0]["eligibility_tier"] == "B"
    assert response["data"][0]["detail_verification_status"] == "error"
    assert response["data"][0]["detail_verification_error_type"] == "captcha"
    assert "detail_verification_failed" in response["data"][0]["uncertain_reasons"]


def test_search_filters_by_keyword_and_exposes_match_fields(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "housescraper_mcp.service.prepare_cookies",
        lambda domain, fallback_domains=(): {"session": "ok"},
    )

    beike_adapter = FakeAdapter(
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
    )
    anjuke_adapter = FakeAdapter(
        [
            House(
                id="2",
                platform="anjuke",
                title="张江独立次新房",
                price=430.0,
                price_unit="万",
                area=78.0,
                layout="2室1厅",
                community="张江花园",
                district="浦东",
                url="https://example.com/anjuke/2",
            )
        ]
    )

    service = HouseScraperService(
        adapter_factories={
            "beike": lambda: beike_adapter,
            "anjuke": lambda: anjuke_adapter,
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(
        service.search(
            SearchFilter(city="上海", keywords="世茂滨江花园"),
            platforms=["beike", "anjuke"],
            limit=10,
        )
    )

    assert beike_adapter.last_filters is not None
    assert anjuke_adapter.last_filters is not None
    assert beike_adapter.last_filters.keywords == ""
    assert anjuke_adapter.last_filters.keywords == "世茂滨江花园"
    assert response["status"] == "success"
    assert response["meta"]["raw_count"] == 1
    assert response["meta"]["returned_count"] == 1
    assert response["meta"]["platforms"][0]["result_count"] == 1
    assert response["meta"]["platforms"][1]["result_count"] == 0
    assert response["meta"]["platforms"][0]["filter_mode"] == "post_filtered"
    assert response["meta"]["platforms"][1]["filter_mode"] == "post_filtered"
    assert response["data"][0]["listing_ref"] == "beike:1"
    assert response["data"][0]["keyword_match"]["keyword"] == "世茂滨江花园"
    assert response["data"][0]["keyword_match"]["matched_fields"] == ["title", "community"]


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


def test_baseline_non_shanghai_city_keeps_honest_platform_status(monkeypatch, tmp_path: Path) -> None:
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
            "lianjia": lambda: FakeAdapter(error=RuntimeError("captcha required")),
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
                        district="香洲",
                        url="https://example.com/2",
                    )
                ]
            ),
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )

    response = asyncio.run(
        service.baseline(
            city="珠海",
            platforms=["beike", "lianjia", "anjuke"],
            search_limit=5,
        )
    )

    assert response["ok"] is False
    assert response["city"] == "珠海"
    assert Path(response["report_artifact_path"]).exists()
    assert response["platform_summary"][0]["requested_platform"] == "beike"
    assert response["platform_summary"][1]["requested_platform"] == "lianjia"
    assert response["platform_summary"][0]["search_result_count"] == 1
    assert response["platform_summary"][1]["search_error_type"] == "captcha"
    assert response["platform_summary"][2]["search_result_count"] == 1
    assert response["checks"]["filtered_search"]["status"] == "partial_success"


def test_baseline_propagates_single_city_to_all_platforms(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "housescraper_mcp.service.prepare_cookies",
        lambda domain, fallback_domains=(): {"session": "ok"},
    )

    beike_adapter = FakeAdapter()
    lianjia_adapter = FakeAdapter()
    anjuke_adapter = FakeAdapter()

    service = HouseScraperService(
        adapter_factories={
            "beike": lambda: beike_adapter,
            "lianjia": lambda: lianjia_adapter,
            "anjuke": lambda: anjuke_adapter,
        },
        artifact_store=ArtifactStore(root=tmp_path),
    )

    asyncio.run(service.baseline(city="珠海", platforms=["beike", "lianjia", "anjuke"], search_limit=5))

    expected_cities = ["珠海", "珠海"]
    assert [f.city for f in beike_adapter.search_filters_history] == expected_cities
    assert [f.city for f in lianjia_adapter.search_filters_history] == expected_cities
    assert [f.city for f in anjuke_adapter.search_filters_history] == expected_cities

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
