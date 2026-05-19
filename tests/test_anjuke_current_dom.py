import asyncio

from click.testing import CliRunner

from house_cli.client.adapters.anjuke import AnjukeClient
from house_cli.commands.detail import detail
from house_cli.models.house import HouseDetail
from house_cli.models.filter import SearchFilter


SALE_HTML = """
<html><body>
  <a class="property-ex" href="https://shanghai.anjuke.com/prop/view/S3884961297163274?from=from_esf_List_screen" target="_blank">
    <div class="property-content">
      <div class="property-content-title">
        <h3 class="property-content-title-name" title="世博 大两居 精装可拎包入住 购物方便 近地铁 正规商品房">世博 大两居 精装可拎包入住 购物方便 近地铁 正规商品房</h3>
      </div>
      <div class="property-content-info">
        <p class="property-content-info-text property-content-info-attribute">
          <span>2</span><span>室</span><span>2</span><span>厅</span><span>1</span><span>卫</span>
        </p>
        <p class="property-content-info-text">93.4㎡</p>
        <p class="property-content-info-text">南北</p>
        <p class="property-content-info-text">低层(共6层)</p>
        <p class="property-content-info-text">1999年建造</p>
      </div>
      <div class="property-content-info-comm">
        <p class="property-content-info-comm-name">上南花苑(三期)</p>
        <p class="property-content-info-comm-address">浦东 世博 齐河路257弄,齐河路259弄</p>
      </div>
      <div class="property-content-tags"><span>近地铁</span><span>VR看房</span></div>
    </div>
    <div class="property-price">
      <p class="property-price-total">498 万</p>
      <p class="property-price-average">53320元/㎡</p>
    </div>
  </a>
</body></html>
"""


CURRENT_ZHUHAI_SALE_HTML = """
<html><body>
  <div class="filters">
    <a href="https://zh.anjuke.com/sale/a326-o4/?from=HomePage_Search">50-70㎡</a>
    <a href="https://zh.anjuke.com/sale/b282-o4/?from=HomePage_Search">二室</a>
    <a href="https://zh.anjuke.com/sale/z1-o4/?from=HomePage_Search">商品房住宅</a>
    <a href="https://zh.anjuke.com/sale/p3/?from=HomePage_Search">3</a>
  </div>
  <a class="property-ex" href="https://zh.anjuke.com/prop/view/S4332249199799304?from=from_esf_List_screen" target="_blank">
    <div class="property-content">
      <div class="property-content-title">
        <h3 class="property-content-title-name" title="沿江路住宅 满五 高楼层采光充足 商品房 低容积白蕉">沿江路住宅 满五 高楼层采光充足 商品房 低容积白蕉</h3>
      </div>
      <div class="property-content-info">
        <p class="property-content-info-text property-content-info-attribute">
          <span>2</span><span>室</span><span>1</span><span>厅</span><span>1</span><span>卫</span>
        </p>
        <p class="property-content-info-text">60.25㎡</p>
        <p class="property-content-info-text">北</p>
        <p class="property-content-info-text">共3层</p>
        <p class="property-content-info-text">1992年建造</p>
      </div>
      <div class="property-content-info-comm">
        <p class="property-content-info-comm-name"><a href="https://zh.anjuke.com/community/view/1">沿江路住宅</a></p>
        <p class="property-content-info-comm-address">斗门 白蕉 沿江路</p>
      </div>
      <div class="property-content-info-tags">
        <span class="property-content-info-tag">满五年</span>
        <span class="property-content-info-tag">采光较好</span>
      </div>
    </div>
    <div class="property-price">
      <p class="property-price-total"><span class="property-price-total-num">18</span><span class="property-price-total-text">万</span></p>
      <p class="property-price-average">2988元/㎡</p>
    </div>
  </a>
</body></html>
"""


class _SaleFlowHttpClient:
    def __init__(self, *args, **kwargs):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def set_referer(self, referer: str):
        return None

    async def get(self, url: str, **kwargs):
        self.calls.append(url)
        if url == "https://www.anjuke.com/sy-city.html":
            return type("Resp", (), {"status_code": 200, "text": "<html><a href=\"https://shanghai.anjuke.com/\">上海房产网</a></html>", "cookies": {}})()
        return type("Resp", (), {"status_code": 200, "text": SALE_HTML, "cookies": {}})()


class _DetailHttpClient:
    calls: list[str] = []

    def __init__(self, *args, **kwargs):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url: str, **kwargs):
        self.calls.append(url)
        html = "<title>珠海详情</title><span class=\"item-info-price-one-num\">18</span>" + "x" * 5000
        return type("Resp", (), {"status_code": 200, "text": html, "cookies": {}})()


def test_anjuke_builds_district_sale_url_from_known_slug():
    client = AnjukeClient()

    url = client._build_list_url("shanghai", SearchFilter(city="上海", district="浦东"))

    assert url == "https://shanghai.anjuke.com/sale/pudong/?from=HomePage_Search"


def test_anjuke_parses_current_sale_dom():
    client = AnjukeClient()

    houses = client._parse_list(SALE_HTML, "上海")

    assert len(houses) == 1
    house = houses[0]
    assert house.id == "S3884961297163274"
    assert house.title == "世博 大两居 精装可拎包入住 购物方便 近地铁 正规商品房"
    assert house.price == 498.0
    assert house.area == 93.4
    assert house.unit_price == 53320.0
    assert house.layout == "2室2厅1卫"
    assert house.orientation == "南北"
    assert house.floor == "低层(共6层)"
    assert house.community == "上南花苑(三期)"
    assert house.district == "浦东"
    assert "近地铁" in house.tags


def test_anjuke_parses_current_zhuhai_sale_dom_with_nested_links_and_price_spans():
    client = AnjukeClient()

    houses = client._parse_list(CURRENT_ZHUHAI_SALE_HTML, "珠海")

    assert len(houses) == 1
    house = houses[0]
    assert house.id == "S4332249199799304"
    assert house.title == "沿江路住宅 满五 高楼层采光充足 商品房 低容积白蕉"
    assert house.price == 18.0
    assert house.area == 60.25
    assert house.unit_price == 2988.0
    assert house.layout == "2室1厅1卫"
    assert house.community == "沿江路住宅"
    assert house.district == "斗门"
    assert "满五年" in house.tags


def test_anjuke_search_returns_sale_results_for_current_dom(monkeypatch):
    monkeypatch.setattr("house_cli.client.adapters.anjuke.HttpClient", _SaleFlowHttpClient)
    monkeypatch.setattr("house_cli.client.adapters.anjuke.load_or_extract_cookies", lambda domain: {})
    monkeypatch.setattr("house_cli.client.adapters.anjuke.save_cookies", lambda domain, cookies: None)

    client = AnjukeClient()
    houses = asyncio.run(client.search(SearchFilter(city="上海", district="浦东")))

    assert len(houses) == 1
    assert houses[0].id == "S3884961297163274"


def test_anjuke_search_flow_builds_filtered_sale_url(monkeypatch):
    seen = []

    class RecordingHttpClient:
        def __init__(self, *args, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def set_referer(self, referer: str):
            return None

        async def get(self, url: str, **kwargs):
            seen.append(url)
            if url == "https://www.anjuke.com/sy-city.html":
                return type(
                    "Resp",
                    (),
                    {"status_code": 200, "text": "<html><a href=\"https://zh.anjuke.com/\">珠海房产网</a></html>", "cookies": {}},
                )()
            return type("Resp", (), {"status_code": 200, "text": CURRENT_ZHUHAI_SALE_HTML, "cookies": {}})()

    monkeypatch.setattr("house_cli.client.adapters.anjuke.HttpClient", RecordingHttpClient)
    monkeypatch.setattr("house_cli.client.adapters.anjuke.load_or_extract_cookies", lambda domain: {})
    monkeypatch.setattr("house_cli.client.adapters.anjuke.save_cookies", lambda domain, cookies: None)

    client = AnjukeClient()
    AnjukeClient._city_slug_cache.clear()
    houses = asyncio.run(
        client.search(
            SearchFilter(
                city="珠海",
                min_area=60,
                max_area=70,
                layout="2室",
                tags=["商品房住宅"],
                sort_by="price_asc",
                page=3,
                anjuke_flow="search",
            )
        )
    )

    assert len(houses) == 1
    assert seen[1] == "https://zh.anjuke.com/sale/o4/?from=HomePage_Search"
    assert seen[2] == "https://zh.anjuke.com/sale/a326-b282-o4-p3-z1/?from=HomePage_Search"


def test_anjuke_browser_flow_clicks_real_filters(monkeypatch):
    seen = []

    class RecordingHttpClient:
        def __init__(self, *args, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def set_referer(self, referer: str):
            return None

        async def get(self, url: str, **kwargs):
            seen.append(("http", url))
            if url == "https://www.anjuke.com/sy-city.html":
                return type(
                    "Resp",
                    (),
                    {"status_code": 200, "text": "<html><a href=\"https://zh.anjuke.com/\">珠海房产网</a></html>", "cookies": {}},
                )()
            return type("Resp", (), {"status_code": 200, "text": CURRENT_ZHUHAI_SALE_HTML, "cookies": {}})()

    class FakeBrowserSession:
        def __init__(self, domain: str, port: int = 9222):
            assert domain == "anjuke.com"
            assert port == 9222
            self._title = "珠海安居客"
            self._html = CURRENT_ZHUHAI_SALE_HTML

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def navigate(self, url: str):
            seen.append(("navigate", url))
            self._html = CURRENT_ZHUHAI_SALE_HTML
            self._title = "珠海安居客"

        def click_sale_link(self, label: str):
            seen.append(("click", label))
            self._html = CURRENT_ZHUHAI_SALE_HTML
            self._title = "珠海安居客"

        def get_html(self) -> str:
            return self._html

        def get_title(self) -> str:
            return self._title

    monkeypatch.setattr("house_cli.client.adapters.anjuke.HttpClient", RecordingHttpClient)
    monkeypatch.setattr("house_cli.client.adapters.anjuke.AnjukeBrowserSaleSession", FakeBrowserSession)
    monkeypatch.setattr("house_cli.client.adapters.anjuke.load_or_extract_cookies", lambda domain: {})
    monkeypatch.setattr("house_cli.client.adapters.anjuke.save_cookies", lambda domain, cookies: None)

    client = AnjukeClient()
    AnjukeClient._city_slug_cache.clear()
    houses = asyncio.run(
        client.search(
            SearchFilter(
                city="珠海",
                min_area=60,
                max_area=70,
                layout="2室",
                tags=["商品房住宅"],
                sort_by="price_asc",
                page=3,
                anjuke_flow="browser",
            )
        )
    )

    assert len(houses) == 1
    assert seen == [
        ("http", "https://www.anjuke.com/sy-city.html"),
        ("navigate", "https://zh.anjuke.com/sale/o4/?from=HomePage_Search"),
        ("click", "50-70㎡"),
        ("click", "二室"),
        ("click", "商品房住宅"),
        ("click", "3"),
    ]


def test_anjuke_detail_uses_configured_city_slug(monkeypatch):
    _DetailHttpClient.calls = []
    monkeypatch.setattr("house_cli.client.adapters.anjuke.HttpClient", _DetailHttpClient)
    monkeypatch.setattr("house_cli.client.adapters.anjuke.load_or_extract_cookies", lambda domain: {"sessid": "ok"})

    detail_result = asyncio.run(AnjukeClient(city="zh").detail("S4332249199799304"))

    assert _DetailHttpClient.calls == ["https://zh.anjuke.com/prop/view/S4332249199799304"]
    assert detail_result.url == "https://zh.anjuke.com/prop/view/S4332249199799304"


def test_anjuke_detail_parses_transaction_ownership_fields():
    html = """
    <html><body>
      <title>珠海安居客产权测试房</title>
      <span class="item-info-price-one-num">18</span>
      <div class="house-info-detail-list">
        <div><span>交易权属</span><span>商品房</span></div>
        <div><span>房屋用途</span><span>普通住宅</span></div>
        <div><span>产权所属</span><span>非共有</span></div>
        <div><span>房本备件</span><span>已上传房本照片</span></div>
      </div>
    </body></html>
    """ + ("x" * 5000)

    detail_result = AnjukeClient(city="zh")._parse_detail(html, "S4332249199799304", "zh")

    assert detail_result.url == "https://zh.anjuke.com/prop/view/S4332249199799304"
    assert detail_result.transaction_ownership == "商品房"
    assert detail_result.house_usage == "普通住宅"
    assert detail_result.ownership == "非共有"
    assert detail_result.deed_status == "已上传房本照片"


def test_detail_command_passes_city_to_anjuke_adapter(monkeypatch):
    seen = {}

    class FakeAnjukeClient:
        def __init__(self, city: str):
            seen["city"] = city

        async def detail(self, house_id: str):
            seen["house_id"] = house_id
            return HouseDetail(id=house_id, platform="anjuke", title="", price=0, price_unit="万", area=0)

    monkeypatch.setitem(
        __import__("house_cli.commands.detail", fromlist=["ADAPTER_REGISTRY"]).ADAPTER_REGISTRY,
        "anjuke",
        FakeAnjukeClient,
    )

    result = CliRunner().invoke(detail, ["anjuke:S4332249199799304", "--city", "zh", "--output", "json"])

    assert result.exit_code == 0
    assert seen == {"city": "zh", "house_id": "S4332249199799304"}
