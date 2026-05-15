import asyncio

import pytest

from house_cli.client.adapters.anjuke import AnjukeClient
from house_cli.models.filter import SearchFilter


class _FakeResp:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text
        self.cookies = {}


class _FakeHttpClient:
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
        if "/sale/" in url:
            # Simulate anti-bot gateway shell page
            return _FakeResp(200, '<html><div id="@@xxzlGatewayUrl">anti-bot</div></html>')

        # Simulate city homepage with one recommendation card
        html = '''
        <html><body>
          <a href="https://shanghai.anjuke.com/prop/view/S1234567890?from=HomePage_RecommendHouse">
            <div class="item-info">
              <div class="item-info-title">测试小区</div>
              <div class="item-info-meta">
                <span data-v-abc>浦东 陆家嘴</span>
                <span data-v-def>2室1厅 88㎡</span>
              </div>
              <div class="item-info-price">
                <span class="item-info-price-one-num">320</span>
                <span class="item-info-price-one-unit">万</span>
                <span class="item-info-price-one-avg">36363元/㎡</span>
              </div>
            </div>
          </a>
        </body></html>
        '''
        return _FakeResp(200, html)


def test_anjuke_search_falls_back_to_homepage_when_sale_is_blocked(monkeypatch):
    monkeypatch.setattr("house_cli.client.adapters.anjuke.HttpClient", _FakeHttpClient)
    monkeypatch.setattr("house_cli.client.adapters.anjuke.load_or_extract_cookies", lambda domain: {})
    monkeypatch.setattr("house_cli.client.adapters.anjuke.save_cookies", lambda domain, cookies: None)

    client = AnjukeClient()
    houses = asyncio.run(client.search(SearchFilter(city="上海")))

    assert len(houses) == 1
    assert houses[0].id == "S1234567890"
    assert houses[0].title == "测试小区"
    assert houses[0].price == 320.0


class _RecommendOnlyEmptyClient:
    calls: list[str] = []

    def __init__(self, *args, **kwargs):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def set_referer(self, referer: str):
        return None

    async def get(self, url: str, **kwargs):
        _RecommendOnlyEmptyClient.calls.append(url)
        return _FakeResp(200, "<html><body>empty</body></html>")


def test_anjuke_recommend_mode_has_no_cross_flow_fallback(monkeypatch):
    _RecommendOnlyEmptyClient.calls = []
    monkeypatch.setattr("house_cli.client.adapters.anjuke.HttpClient", _RecommendOnlyEmptyClient)
    monkeypatch.setattr("house_cli.client.adapters.anjuke.load_or_extract_cookies", lambda domain: {})
    monkeypatch.setattr("house_cli.client.adapters.anjuke.save_cookies", lambda domain, cookies: None)

    client = AnjukeClient()
    houses = asyncio.run(client.search(SearchFilter(city="上海", anjuke_flow="recommend")))

    assert houses == []
    assert len(_RecommendOnlyEmptyClient.calls) == 1
    assert _RecommendOnlyEmptyClient.calls[0].startswith("https://shanghai.anjuke.com/?from=AJK_Web_City")


def test_anjuke_search_does_not_fallback_city_when_city_is_unknown():
    client = AnjukeClient()
    with pytest.raises(RuntimeError) as exc:
        asyncio.run(client.search(SearchFilter(city="火星", anjuke_flow="recommend")))
    assert "Unsupported city" in str(exc.value)


class _ChallengeThenPassHttpClient:
    def __init__(self, *args, **kwargs):
        self.sale_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def set_referer(self, referer: str):
        return None

    async def get(self, url: str, **kwargs):
        if "/sale/" in url:
            self.sale_count += 1
            if self.sale_count == 1:
                challenge = (
                    '<div id="@@xxzlGatewayUrl">'
                    "https://callback.58.com/antibot/verifycode?foo=1&amp;bar=2"
                    "</div>"
                )
                return _FakeResp(200, f"<html>{challenge}</html>")

            html = '''
            <html><body>
              <a href="https://shanghai.anjuke.com/prop/view/S9999999999?from=HomePage_Search">
                <div class="item-info">
                  <div class="item-info-title">筛选流房源</div>
                  <div class="item-info-meta">
                    <span data-v-abc>浦东 陆家嘴</span>
                    <span data-v-def>2室1厅 88㎡</span>
                  </div>
                  <div class="item-info-price">
                    <span class="item-info-price-one-num">500</span>
                    <span class="item-info-price-one-unit">万</span>
                    <span class="item-info-price-one-avg">56818元/㎡</span>
                  </div>
                </div>
              </a>
            </body></html>
            '''
            return _FakeResp(200, html)

        if "callback.58.com/antibot/verifycode" in url:
            return _FakeResp(200, "<html>ok</html>")

        return _FakeResp(200, "<html></html>")


def test_anjuke_search_retries_sale_flow_after_gateway_challenge(monkeypatch):
    monkeypatch.setattr("house_cli.client.adapters.anjuke.HttpClient", _ChallengeThenPassHttpClient)
    monkeypatch.setattr("house_cli.client.adapters.anjuke.load_or_extract_cookies", lambda domain: {})
    monkeypatch.setattr("house_cli.client.adapters.anjuke.save_cookies", lambda domain, cookies: None)

    client = AnjukeClient()
    houses = asyncio.run(client.search(SearchFilter(city="上海")))

    assert len(houses) == 1
    assert houses[0].id == "S9999999999"
    assert "HomePage_Search" in houses[0].url
