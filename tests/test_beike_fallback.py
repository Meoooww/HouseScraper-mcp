import asyncio

import pytest

from house_cli.client.adapters.beike import BeikeClient
from house_cli.models.filter import SearchFilter


BEIKE_BASE_HTML = """
<html><body>
  <ul class="sellListContent">
    <li class="clear">
      <a href="https://sh.ke.com/ershoufang/107114156799.html">
        <img alt="上海浦东二手房"/>
      </a>
      <div class="title">
        <a class="VIEWDATA CLICKDATA maidian-detail">测试房源</a>
      </div>
      <div class="address">
        <div class="houseInfo">2室1厅 | 88平米 | 南北 | 低楼层(共6层) | 1999年建</div>
      </div>
      <div class="flood">
        <div class="positionInfo">
          <a href="https://sh.ke.com/xiaoqu/123/">测试小区</a>
        </div>
      </div>
      <div class="priceInfo">
        <div class="totalPrice"><span>320</span></div>
        <div class="unitPrice"><span>36363元/平米</span></div>
      </div>
      <div class="followInfo">1天前发布</div>
    </li>
  </ul>
</body></html>
"""


class _FakeResp:
    def __init__(self, text: str, url: str, cookies=None):
        self.text = text
        self.url = url
        self.cookies = cookies or {}


class _BeikeFallbackHttpClient:
    def __init__(self, *args, **kwargs):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url: str, **kwargs):
        self.calls.append(url)
        if "pudong" in url:
            return _FakeResp(
                "<html>blocked</html>",
                "https://clogin.ke.com/login?service=mock",
            )
        return _FakeResp(
            BEIKE_BASE_HTML,
            "https://sh.ke.com/ershoufang/",
        )


def test_beike_search_raises_when_filtered_path_is_blocked(monkeypatch):
    monkeypatch.setattr("house_cli.client.adapters.beike.HttpClient", _BeikeFallbackHttpClient)
    monkeypatch.setattr("house_cli.client.adapters.beike.load_or_extract_cookies", lambda domain: {})
    monkeypatch.setattr("house_cli.client.adapters.beike.save_cookies", lambda domain, cookies: None)

    client = BeikeClient()

    with pytest.raises(RuntimeError, match="blocked the strict filter URL"):
        asyncio.run(client.search(SearchFilter(city="上海", district="浦东")))


def test_beike_detail_parses_transaction_ownership_and_city_url():
    html = """
    <html><body>
      <h1 class="main">产权清晰测试房</h1>
      <span class="total">25</span>
      <div class="baseinform">
        <li class=" has-data"><span class="label ">交易权属</span>商品房</li>
        <li class=" has-data"><span class="label ">房屋用途</span>普通住宅</li>
        <li class=" has-data"><span class="label ">产权所属</span>非共有</li>
        <li class=" has-data"><span class="label ">抵押信息</span>无抵押</li>
        <li class=" has-data"><span class="label ">房本备件</span>已上传房本照片</li>
      </div>
    </body></html>
    """

    detail = BeikeClient(city="珠海")._parse_detail(html, "105122339790", "珠海", "zh")

    assert detail.city == "珠海"
    assert detail.url == "https://zh.ke.com/ershoufang/105122339790.html"
    assert detail.transaction_ownership == "商品房"
    assert detail.house_usage == "普通住宅"
    assert detail.ownership == "非共有"
    assert detail.mortgage_info == "无抵押"
    assert detail.deed_status == "已上传房本照片"
