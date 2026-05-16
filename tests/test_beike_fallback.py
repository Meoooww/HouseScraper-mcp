import asyncio

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


def test_beike_search_falls_back_to_base_listing_when_filtered_path_is_blocked(monkeypatch):
    monkeypatch.setattr("house_cli.client.adapters.beike.HttpClient", _BeikeFallbackHttpClient)
    monkeypatch.setattr("house_cli.client.adapters.beike.load_or_extract_cookies", lambda domain: {})
    monkeypatch.setattr("house_cli.client.adapters.beike.save_cookies", lambda domain, cookies: None)

    client = BeikeClient()
    houses = asyncio.run(client.search(SearchFilter(city="上海", district="浦东")))

    assert len(houses) == 1
    assert houses[0].id == "107114156799"
    assert houses[0].title == "测试房源"
