import asyncio

from house_cli.client.adapters.anjuke import AnjukeClient
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
        return type("Resp", (), {"status_code": 200, "text": SALE_HTML, "cookies": {}})()


def test_anjuke_builds_district_sale_url_from_known_slug():
    client = AnjukeClient()

    url = client._build_list_url(SearchFilter(city="上海", district="浦东"))

    assert url == "https://shanghai.anjuke.com/sale/pudong/"


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


def test_anjuke_search_returns_sale_results_for_current_dom(monkeypatch):
    monkeypatch.setattr("house_cli.client.adapters.anjuke.HttpClient", _SaleFlowHttpClient)
    monkeypatch.setattr("house_cli.client.adapters.anjuke.load_or_extract_cookies", lambda domain: {})
    monkeypatch.setattr("house_cli.client.adapters.anjuke.save_cookies", lambda domain, cookies: None)

    client = AnjukeClient()
    houses = asyncio.run(client.search(SearchFilter(city="上海", district="浦东")))

    assert len(houses) == 1
    assert houses[0].id == "S3884961297163274"
