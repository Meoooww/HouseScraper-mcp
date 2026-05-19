# Anjuke (安居客) platform adapter
"""Anjuke adapter for second-hand houses.

Anjuke's /sale/ page returns 403 without full browser session.
The city homepage (/{city}.anjuke.com/?from=AJK_Web_City) contains
recommended house listings that can be parsed.

URL patterns:
    City homepage: https://{city}.anjuke.com/?from=AJK_Web_City
    Sale listing:  https://{city}.anjuke.com/sale/ (requires full cookies)
    Detail:        https://{city}.anjuke.com/prop/view/{id}

HTML card structure (Vue SSR):
    <div class="item-info">
      <div class="item-info-title">小区名</div>
      <div class="item-info-meta"><span>区域</span><span>户型 面积</span></div>
      <div class="item-info-price">
        <span class="item-info-price-one-num">599</span>
        <span class="item-info-price-one-unit">万</span>
        <span class="item-info-price-one-avg">62396元/㎡</span>
      </div>
    </div>
"""

import re
import json
import time
import urllib.request
from html import unescape

from house_cli.client.base import BaseClient
from house_cli.client.http import HttpClient
from house_cli.client.auth import load_or_extract_cookies, save_cookies
from house_cli.models.house import House, HouseDetail
from house_cli.models.filter import SearchFilter
from house_cli.models.cities import DISTRICTS

CITY_INDEX_URL = "https://www.anjuke.com/sy-city.html"
SORT_TOKENS = {
    "area": "o2",
    "price_asc": "o4",
}
ROOM_LABELS = {
    "1": "一室",
    "2": "二室",
    "3": "三室",
    "4": "四室",
    "5": "五室",
}
ROOM_TOKEN_PATTERNS = {
    "一室": re.compile(r"b\d+"),
    "二室": re.compile(r"b\d+"),
    "三室": re.compile(r"b\d+"),
    "四室": re.compile(r"b\d+"),
    "五室": re.compile(r"b\d+"),
    "五室以上": re.compile(r"b\d+"),
}
PROPERTY_NATURE_LABELS = {
    "商品房住宅",
}


class AnjukeBrowserSaleSession:
    """Minimal CDP session for browser-driven Anjuke sale filtering."""

    def __init__(self, domain: str, port: int = 9222):
        self.domain = domain
        self.port = port
        self._ws = None
        self._msg_id = 0

    def __enter__(self):
        try:
            import websocket
        except ImportError as exc:  # pragma: no cover - runtime guard
            raise RuntimeError(
                "websocket-client is required for Anjuke browser flow. "
                "Install dependencies from pyproject.toml first."
            ) from exc

        tabs_url = f"http://127.0.0.1:{self.port}/json"
        try:
            with urllib.request.urlopen(tabs_url, timeout=5) as resp:
                tabs = json.load(resp)
        except OSError as exc:
            raise RuntimeError(
                f"Cannot connect to Chrome/Edge DevTools at {tabs_url}. "
                f"Start the browser with --remote-debugging-port={self.port} first."
            ) from exc

        page = next(
            (
                tab for tab in tabs
                if tab.get("type") == "page"
                and self.domain.lstrip(".") in tab.get("url", "")
                and tab.get("webSocketDebuggerUrl")
            ),
            None,
        )
        if page is None:
            raise RuntimeError(
                f"No open page for {self.domain} found in DevTools. "
                "Open an Anjuke sale page in that browser first."
            )

        self._ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=20)
        self._send("Page.enable")
        self._send("Runtime.enable")
        return self

    def __exit__(self, *args):
        if self._ws is not None:
            self._ws.close()
            self._ws = None
        return None

    def _send(self, method: str, params: dict | None = None) -> int:
        self._msg_id += 1
        self._ws.send(json.dumps({"id": self._msg_id, "method": method, "params": params or {}}))
        return self._msg_id

    def _recv_until(self, *, target_id: int | None = None, methods: set[str] | None = None, timeout: float = 20.0):
        end = time.time() + timeout
        while time.time() < end:
            msg = json.loads(self._ws.recv())
            if target_id is not None and msg.get("id") == target_id:
                return msg
            if methods and msg.get("method") in methods:
                return msg
        raise TimeoutError("Timed out waiting for CDP response")

    def _wait_load(self):
        for _ in range(80):
            try:
                evt = self._recv_until(methods={"Page.loadEventFired"}, timeout=1.0)
                if evt.get("method") == "Page.loadEventFired":
                    break
            except Exception:
                pass
            time.sleep(0.2)
        time.sleep(0.6)

    def _eval(self, expression: str):
        msg_id = self._send("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        result = self._recv_until(target_id=msg_id)
        return result["result"]["result"].get("value")

    def navigate(self, url: str):
        msg_id = self._send("Page.navigate", {"url": url})
        self._recv_until(target_id=msg_id)
        self._wait_load()

    def click_sale_link(self, label: str):
        expr = f"""
        (() => {{
          const target = [...document.querySelectorAll('a')].find(
            a => (a.innerText || '').trim() === {json.dumps(label)} && a.href.includes('/sale/')
          );
          if (!target) return false;
          target.click();
          return true;
        }})()
        """
        ok = self._eval(expr)
        if not ok:
            raise RuntimeError(f"Could not find Anjuke browser filter link: {label}")
        self._wait_load()

    def get_html(self) -> str:
        return self._eval("document.documentElement.outerHTML") or ""

    def get_title(self) -> str:
        return self._eval("document.title") or ""


class AnjukeClient(BaseClient):
    """Anjuke adapter (buy + rent). Requires browser cookies."""

    platform_name = "anjuke"
    _city_slug_cache: dict[str, str] = {}
    _sale_filter_cache: dict[str, dict[str, dict[str, str]]] = {}

    def __init__(self, city: str = "beijing"):
        self.city = city

    @staticmethod
    def _clean_city_label(text: str) -> str:
        s = _clean(re.sub(r"<[^>]+>", " ", text))
        s = re.sub(r"\s+", "", s)
        s = s.replace("安居客", "")
        s = re.sub(r"(二手房|新房|租房|房产网|房产信息网|楼盘|买房|卖房)$", "", s)
        m = re.search(r"[\u4e00-\u9fff]{2,6}", s)
        return m.group(0) if m else ""

    @classmethod
    def _extract_city_slug_map(cls, html: str) -> dict[str, str]:
        mapping: dict[str, str] = {}
        # Primary pattern: https://{slug}.anjuke.com/... city links
        for m in re.finditer(
            r'<a[^>]*href="https?://([a-z0-9-]+)\.anjuke\.com[^"]*"[^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        ):
            slug = m.group(1).strip().lower()
            label = cls._clean_city_label(m.group(2))
            if label and slug:
                mapping[label] = slug

        # Supplementary: links where city appears in title attribute.
        for m in re.finditer(
            r'<a[^>]*href="https?://([a-z0-9-]+)\.anjuke\.com[^"]*"[^>]*title="([^"]+)"[^>]*>',
            html,
            re.DOTALL,
        ):
            slug = m.group(1).strip().lower()
            label = cls._clean_city_label(m.group(2))
            if label and slug:
                mapping[label] = slug

        return mapping

    async def _resolve_city_slug(self, city_name: str, client: HttpClient, cookies: dict) -> str:
        if re.fullmatch(r"[a-z0-9-]+", city_name):
            return city_name.lower()

        cached = self._city_slug_cache.get(city_name)
        if cached:
            return cached

        try:
            client.set_referer("https://www.anjuke.com/")
            resp = await client.get(CITY_INDEX_URL, cookies=cookies)
            mapping = self._extract_city_slug_map(resp.text)
        except Exception as exc:
            raise RuntimeError(
                f"Unable to resolve Anjuke city slug for {city_name}: failed to load {CITY_INDEX_URL}"
            ) from exc

        slug = mapping.get(city_name)
        if not slug:
            raise RuntimeError(
                f"Unable to resolve Anjuke city slug for {city_name}. "
                f"Confirm this city exists on anjuke and is visible in {CITY_INDEX_URL}"
            )

        self._city_slug_cache[city_name] = slug
        return slug

    def _build_sale_entry_url(self, city_slug: str, filters: SearchFilter) -> str:
        district_map = DISTRICTS.get(filters.city, {})
        district_slug = district_map.get(filters.district or "", "")

        sort_token = SORT_TOKENS.get(filters.sort_by, "")
        if district_slug and sort_token:
            return f"https://{city_slug}.anjuke.com/sale/{district_slug}/{sort_token}/?from=HomePage_Search"
        if district_slug:
            return f"https://{city_slug}.anjuke.com/sale/{district_slug}/?from=HomePage_Search"
        if sort_token:
            return f"https://{city_slug}.anjuke.com/sale/{sort_token}/?from=HomePage_Search"
        return f"https://{city_slug}.anjuke.com/sale/?from=HomePage_Search"

    def _build_list_url(self, city_slug: str, filters: SearchFilter) -> str:
        """Compatibility shim for tests and existing call sites."""
        return self._build_sale_entry_url(city_slug, filters)

    @staticmethod
    def _extract_sale_path_tokens(href: str, city_slug: str) -> list[str]:
        m = re.search(
            rf"https?://{re.escape(city_slug)}\.anjuke\.com/sale/([^?\"]*)",
            href,
        )
        if not m:
            return []
        path = m.group(1).strip("/")
        if not path:
            return []
        tokens: list[str] = []
        for seg in path.split("/"):
            if seg:
                tokens.extend(tok for tok in seg.split("-") if tok)
        return tokens

    @classmethod
    def _extract_sale_filter_options(cls, html: str, city_slug: str) -> dict[str, dict[str, str]]:
        options = {"area": {}, "layout": {}}
        for href, label_html in re.findall(
            r'<a[^>]*href="(https?://[^"]*?/sale/[^"]*)"[^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        ):
            label = cls._clean_city_label(label_html)
            if not label:
                label = _clean(re.sub(r"<[^>]+>", " ", label_html))
            if not label or label == "不限":
                continue

            tokens = cls._extract_sale_path_tokens(href, city_slug)
            area_token = next((tok for tok in tokens if re.fullmatch(r"a\d+", tok)), "")
            room_token = next((tok for tok in tokens if re.fullmatch(r"b\d+", tok)), "")
            if area_token and ("㎡" in label or "以下" in label or "以上" in label):
                options["area"][label] = area_token
            if room_token and label in ROOM_LABELS.values():
                options["layout"][label] = room_token
        return options

    @staticmethod
    def _parse_area_label_range(label: str) -> tuple[float, float | None] | None:
        below = re.search(r"(\d+)\s*㎡?以下", label)
        if below:
            return 0.0, float(below.group(1))
        between = re.search(r"(\d+)\s*-\s*(\d+)\s*㎡", label)
        if between:
            return float(between.group(1)), float(between.group(2))
        above = re.search(r"(\d+)\s*㎡?以上", label)
        if above:
            return float(above.group(1)), None
        return None

    @classmethod
    def _select_area_tokens(cls, filters: SearchFilter, options: dict[str, str]) -> list[str]:
        if filters.min_area is None and filters.max_area is None:
            return []

        want_lo = float(filters.min_area or 0)
        want_hi = float(filters.max_area) if filters.max_area is not None else None
        tokens: list[str] = []
        for label, token in options.items():
            area_range = cls._parse_area_label_range(label)
            if not area_range:
                continue
            have_lo, have_hi = area_range
            overlaps = (want_hi is None or have_lo <= want_hi) and (have_hi is None or want_lo <= have_hi)
            if overlaps:
                tokens.append(token)
        return list(dict.fromkeys(tokens))

    @classmethod
    def _select_layout_tokens(cls, layout: str, options: dict[str, str]) -> list[str]:
        if not layout:
            return []
        m = re.search(r"(\d)", layout)
        if not m:
            return []
        room_label = ROOM_LABELS.get(m.group(1), "")
        token = options.get(room_label, "")
        return [token] if token else []

    def _build_list_urls(
        self,
        city_slug: str,
        filters: SearchFilter,
        filter_options: dict[str, dict[str, str]],
    ) -> list[str]:
        district_map = DISTRICTS.get(filters.city, {})
        district_slug = district_map.get(filters.district or "", "")
        sort_token = SORT_TOKENS.get(filters.sort_by, "")
        page_token = f"p{filters.page}" if filters.page and filters.page > 1 else ""
        area_tokens = self._select_area_tokens(filters, filter_options.get("area", {})) or [""]
        layout_tokens = self._select_layout_tokens(filters.layout, filter_options.get("layout", {})) or [""]

        urls: list[str] = []
        for area_token in area_tokens:
            for layout_token in layout_tokens:
                tokens = [tok for tok in [area_token, layout_token, sort_token, page_token] if tok]
                if district_slug:
                    if tokens:
                        urls.append(
                            f"https://{city_slug}.anjuke.com/sale/{district_slug}/{'-'.join(tokens)}/?from=HomePage_Search"
                        )
                    else:
                        urls.append(
                            f"https://{city_slug}.anjuke.com/sale/{district_slug}/?from=HomePage_Search"
                        )
                else:
                    if tokens:
                        urls.append(
                            f"https://{city_slug}.anjuke.com/sale/{'-'.join(tokens)}/?from=HomePage_Search"
                        )
                    else:
                        urls.append(
                            f"https://{city_slug}.anjuke.com/sale/?from=HomePage_Search"
                        )
        return list(dict.fromkeys(urls))

    @staticmethod
    def _href_contains_token(href: str, token: str) -> bool:
        return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])", href))

    def _discover_refined_urls(
        self,
        html: str,
        city_slug: str,
        filters: SearchFilter,
    ) -> list[str]:
        base_url = self._build_sale_entry_url(city_slug, filters)
        sort_token = SORT_TOKENS.get(filters.sort_by, "")
        page_token = f"p{filters.page}" if filters.page and filters.page > 1 else ""

        room_label = ""
        if filters.layout:
            m = re.search(r"(\d)", filters.layout)
            if m:
                room_label = ROOM_LABELS.get(m.group(1), "")
        property_nature_label = next(
            (tag for tag in getattr(filters, "tags", []) if tag in PROPERTY_NATURE_LABELS),
            "",
        )

        wanted_links: list[str] = []
        property_nature_href = ""
        for href, label_html in re.findall(
            r'<a[^>]*href="(https?://[^"]*?/sale/[^"]*)"[^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        ):
            label = _clean(re.sub(r"<[^>]+>", " ", label_html))
            if sort_token and not self._href_contains_token(href, sort_token):
                continue
            if property_nature_label and label == property_nature_label:
                property_nature_href = href

            area_ok = filters.min_area is None and filters.max_area is None
            if not area_ok:
                area_range = self._parse_area_label_range(label)
                if area_range:
                    have_lo, have_hi = area_range
                    want_lo = float(filters.min_area or 0)
                    want_hi = float(filters.max_area) if filters.max_area is not None else None
                    area_ok = (want_hi is None or have_lo <= want_hi) and (have_hi is None or want_lo <= have_hi)

            room_ok = not room_label or label == room_label
            if area_ok or room_ok:
                wanted_links.append(href)

        if not wanted_links:
            return [base_url]

        area_links = [href for href in wanted_links if self._parse_area_label_range(_clean(href)) is not None]
        room_links = [href for href, label_html in re.findall(
            r'<a[^>]*href="(https?://[^"]*?/sale/[^"]*)"[^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        ) if _clean(re.sub(r"<[^>]+>", " ", label_html)) == room_label] if room_label else []

        area_href = next((href for href in wanted_links if any(tok in href for tok in ["/sale/a", "-a"])), "")
        room_href = next((href for href in wanted_links if any(tok in href for tok in ["/sale/b", "-b"])), "")
        if not area_href and not room_href:
            return [base_url]

        tokens: list[str] = []
        if area_href:
            tokens.extend(tok for tok in self._extract_sale_path_tokens(area_href, city_slug) if re.fullmatch(r"a\d+", tok))
        if room_href:
            tokens.extend(tok for tok in self._extract_sale_path_tokens(room_href, city_slug) if re.fullmatch(r"b\d+", tok))
        if sort_token:
            tokens.append(sort_token)
        if page_token:
            tokens.append(page_token)
        if property_nature_href:
            tokens.extend(
                tok
                for tok in self._extract_sale_path_tokens(property_nature_href, city_slug)
                if re.fullmatch(r"z\d+", tok)
            )
        tokens = list(dict.fromkeys(tokens))
        if not tokens:
            return [base_url]
        return [f"https://{city_slug}.anjuke.com/sale/{'-'.join(tokens)}/?from=HomePage_Search"]

    def _labels_for_browser_flow(self, filters: SearchFilter) -> list[str]:
        labels: list[str] = []
        area_tokens = self._select_area_tokens(
            filters,
            {
                "50㎡以下": "a325",
                "50-70㎡": "a326",
                "70-90㎡": "a327",
                "90-110㎡": "a328",
                "110-130㎡": "a329",
                "130-150㎡": "a330",
                "150-200㎡": "a331",
                "200㎡以上": "a332",
            },
        )
        area_label_by_token = {
            "a325": "50㎡以下",
            "a326": "50-70㎡",
            "a327": "70-90㎡",
            "a328": "90-110㎡",
            "a329": "110-130㎡",
            "a330": "130-150㎡",
            "a331": "150-200㎡",
            "a332": "200㎡以上",
        }
        if area_tokens:
            labels.append(area_label_by_token[area_tokens[0]])

        if filters.layout:
            m = re.search(r"(\d)", filters.layout)
            if m:
                room_label = ROOM_LABELS.get(m.group(1), "")
                if room_label:
                    labels.append(room_label)

        property_nature_label = next(
            (tag for tag in getattr(filters, "tags", []) if tag in PROPERTY_NATURE_LABELS),
            "",
        )
        if property_nature_label:
            labels.append(property_nature_label)

        if filters.page and filters.page > 1:
            labels.append(str(filters.page))

        return labels

    def _search_via_browser_flow(self, city_slug: str, filters: SearchFilter) -> list[House]:
        base_url = self._build_sale_entry_url(city_slug, SearchFilter(city=filters.city, district=filters.district, sort_by=filters.sort_by))
        with AnjukeBrowserSaleSession("anjuke.com") as session:
            session.navigate(base_url)
            for label in self._labels_for_browser_flow(filters):
                session.click_sale_link(label)
            html = session.get_html()
            title = session.get_title()
            if "验证码" in title or self._is_antibot_gateway_page(html):
                raise RuntimeError(
                    "anjuke.com browser sale flow is blocked by anti-bot challenge. "
                    "Please complete browser verification in the opened browser tab and retry."
                )
            return self._parse_list(html, filters.city)

    @staticmethod
    def _is_antibot_gateway_page(html: str) -> bool:
        if not html:
            return False
        return (
            "@@xxzlGatewayUrl" in html
            or "esfcommon-captcha-geetest" in html
            or "callback.58.com/antibot/verifycode" in html
        )

    @staticmethod
    def _has_sale_page_content(html: str) -> bool:
        if not html:
            return False
        return (
            'class="property-ex"' in html
            or "/prop/view/" in html
            or "/sale/" in html
        )

    @staticmethod
    def _extract_gateway_url(html: str) -> str:
        m = re.search(
            r'id="@@xxzlGatewayUrl"[^>]*>\s*(https?://[^<\s]+)',
            html,
        )
        if not m:
            return ""
        return unescape(m.group(1)).strip()

    @staticmethod
    def _merge_response_cookies(base_cookies: dict, resp) -> dict:
        if not getattr(resp, "cookies", None):
            return base_cookies
        merged = {**base_cookies, **{k: v for k, v in resp.cookies.items()}}
        if merged != base_cookies:
            save_cookies("anjuke.com", merged)
        return merged

    async def search(self, filters: SearchFilter) -> list[House]:
        cookies = load_or_extract_cookies("anjuke.com")
        referer = "https://www.anjuke.com/sy-city.html"
        refined_attempted = False
        refined_blocked = False

        flow = getattr(filters, "anjuke_flow", "auto")
        async with HttpClient(referer=referer) as client:
            city = await self._resolve_city_slug(filters.city, client, cookies)
            if flow == "browser":
                return self._search_via_browser_flow(city, filters)
            sale_url = self._build_sale_entry_url(city, filters)
            if flow == "recommend":
                homepage_url = f"https://{city}.anjuke.com/?from=AJK_Web_City"
                try:
                    client.set_referer(referer)
                    resp = await client.get(homepage_url, cookies=cookies)
                    html = resp.text
                    cookies = self._merge_response_cookies(cookies, resp)
                except Exception:
                    html = ""
                return self._parse_list(html, filters.city)

            try:
                resp = await client.get(sale_url, cookies=cookies)
                html = resp.text

                cookies = self._merge_response_cookies(cookies, resp)

                if resp.status_code != 403 and (
                    len(html) > 5000 or self._has_sale_page_content(html)
                ):
                    sale_urls = self._discover_refined_urls(html, city, filters)
                    if sale_urls == [sale_url]:
                        houses = self._parse_list(html, filters.city)
                        if houses:
                            return houses
                    else:
                        refined_attempted = True
                        merged: dict[str, House] = {}
                        for refined_url in sale_urls:
                            refined_resp = await client.get(refined_url, cookies=cookies)
                            refined_html = refined_resp.text
                            cookies = self._merge_response_cookies(cookies, refined_resp)
                            if self._is_antibot_gateway_page(refined_html) or not self._has_sale_page_content(refined_html):
                                refined_blocked = True
                                continue
                            for house in self._parse_list(refined_html, filters.city):
                                merged[house.id] = house
                        if merged:
                            return list(merged.values())

                if self._is_antibot_gateway_page(html):
                    gateway_url = self._extract_gateway_url(html)
                    if gateway_url:
                        try:
                            challenge_resp = await client.get(gateway_url, cookies=cookies)
                            cookies = self._merge_response_cookies(cookies, challenge_resp)
                        except Exception:
                            pass

                    retry_resp = await client.get(sale_url, cookies=cookies)
                    html = retry_resp.text
                    cookies = self._merge_response_cookies(cookies, retry_resp)
                    retry_urls = self._discover_refined_urls(html, city, filters)
                    if retry_urls == [sale_url]:
                        retry_houses = self._parse_list(html, filters.city)
                        if retry_houses:
                            return retry_houses
                    else:
                        refined_attempted = True
                        merged: dict[str, House] = {}
                        for refined_url in retry_urls:
                            refined_resp = await client.get(refined_url, cookies=cookies)
                            refined_html = refined_resp.text
                            cookies = self._merge_response_cookies(cookies, refined_resp)
                            if self._is_antibot_gateway_page(refined_html) or not self._has_sale_page_content(refined_html):
                                refined_blocked = True
                                continue
                            for house in self._parse_list(refined_html, filters.city):
                                merged[house.id] = house
                        if merged:
                            return list(merged.values())
            except Exception:
                html = ""

            if flow in {"search", "auto"}:
                if refined_attempted:
                    if refined_blocked:
                        raise RuntimeError(
                            "anjuke.com sale flow is blocked by anti-bot challenge. "
                            "Please complete browser verification and refresh anjuke.com cookies."
                        )
                    return []
                houses = self._parse_list(html, filters.city)
                if houses:
                    return houses
                if self._is_antibot_gateway_page(html) or "esfcommon-captcha" in html:
                    raise RuntimeError(
                        "anjuke.com sale flow is blocked by anti-bot challenge. "
                        "Please complete browser verification and refresh anjuke.com cookies."
                    )
                return houses

        houses = self._parse_list(html, filters.city)
        if houses:
            return houses

        if len(html) < 5000:
            raise RuntimeError(
                "anjuke.com requires browser cookies. "
                "Please visit anjuke.com in your browser, select a city, "
                "then cookies will be automatically extracted (or export to "
                "~/.config/house-cli/cookies.json)"
            )

        return houses

    async def detail(self, house_id: str) -> HouseDetail:
        cookies = load_or_extract_cookies("anjuke.com")
        if not cookies:
            raise RuntimeError(
                "Anjuke detail pages require browser cookies. "
                "Please visit anjuke.com in your browser first."
            )

        city = self.city
        url = f"https://{city}.anjuke.com/prop/view/{house_id}"
        async with HttpClient(referer=f"https://{city}.anjuke.com/sale/") as client:
            try:
                resp = await client.get(url, cookies=cookies)
                html = resp.text
            except Exception:
                html = ""

        if len(html) < 5000:
            raise RuntimeError("Anjuke detail page not accessible")

        return self._parse_detail(html, house_id, city)

    async def get_price_history(self, house_id: str) -> list[dict]:
        d = await self.detail(house_id)
        return d.price_history

    def _parse_list(self, html: str, city: str) -> list[House]:
        if "property-content-title-name" in html:
            return self._parse_sale_list(html, city)
        return self._parse_recommend_list(html, city)

    def _parse_sale_list(self, html: str, city: str) -> list[House]:
        houses: list[House] = []

        card_starts = list(
            re.finditer(
                r'<a\b[^>]*class="[^"]*\bproperty-ex\b[^"]*"[^>]*>',
                html,
                re.DOTALL,
            )
        )

        for index, start_m in enumerate(card_starts):
            card_start = start_m.start()
            card_end = (
                card_starts[index + 1].start()
                if index + 1 < len(card_starts)
                else len(html)
            )
            card_html = html[card_start:card_end]
            href_m = re.search(
                r'href="(https?://[^"]*?/prop/view/([^?"]+)[^"]*)"',
                start_m.group(0),
            )
            if not href_m:
                continue
            url = unescape(href_m.group(1))
            house_id = href_m.group(2)
            try:
                house = self._parse_sale_card(card_html, house_id, url, city)
                if house:
                    houses.append(house)
            except Exception:
                continue

        return houses

    def _parse_recommend_list(self, html: str, city: str) -> list[House]:
        houses: list[House] = []

        # Find all recommendation cards with price-one-num (actual house listings)
        # Split by <a> tags that link to /prop/view/
        card_pattern = re.compile(
            r'<a\s+href="(https?://[^"]*?/prop/view/([^?"]+)[^"]*)"[^>]*>'
            r'(.*?)</a>',
            re.DOTALL,
        )

        for m in card_pattern.finditer(html):
            url = m.group(1)
            house_id = m.group(2)
            card_html = m.group(3)

            # Must have price to be a real listing
            if "item-info-price-one-num" not in card_html:
                continue

            try:
                h = self._parse_recommend_card(card_html, house_id, url, city)
                if h:
                    houses.append(h)
            except Exception:
                continue

        return houses

    def _parse_sale_card(self, card: str, house_id: str, url: str, city: str) -> House | None:
        title = ""
        title_m = re.search(
            r'class="property-content-title-name"[^>]*title="([^"]+)"',
            card,
        )
        if title_m:
            title = _clean(title_m.group(1))
        else:
            title_m = re.search(
                r'class="property-content-title-name"[^>]*>([^<]+)',
                card,
            )
            title = _clean(title_m.group(1)) if title_m else ""

        layout = ""
        attr_m = re.search(
            r'class="[^"]*property-content-info-attribute[^"]*"[^>]*>(.*?)</p>',
            card,
            re.DOTALL,
        )
        if attr_m:
            spans = re.findall(r'<span[^>]*>([^<]+)</span>', attr_m.group(1))
            layout = "".join(seg.strip() for seg in spans)

        area = 0.0
        orientation = ""
        floor = ""
        info_texts = re.findall(
            r'class="property-content-info-text"[^>]*>\s*([^<]+?)\s*<',
            card,
        )
        for text in info_texts:
            text = _clean(text)
            if "㎡" in text:
                area_m = re.search(r"([\d.]+)", text)
                if area_m:
                    area = float(area_m.group(1))
            elif "层" in text:
                floor = text
            elif text in (
                "南", "北", "东", "西", "南北", "东南", "东北", "西南", "西北", "东西"
            ):
                orientation = text

        community = _first_class_text(card, "property-content-info-comm-name")

        district = ""
        address_text = _first_class_text(card, "property-content-info-comm-address")
        if address_text:
            district = address_text.split()[0]

        price = 0.0
        price_text = _first_class_text(card, "property-price-total")
        price_m = re.search(r"([\d.]+)", price_text)
        if price_m:
            price = float(price_m.group(1))

        unit_price = None
        unit_price_text = _first_class_text(card, "property-price-average")
        up_m = re.search(r"([\d,]+)元/㎡", unit_price_text)
        if up_m:
            unit_price = float(up_m.group(1).replace(",", ""))

        tags = _class_texts(card, "property-content-info-tag")
        legacy_tags = re.search(
            r'class="property-content-tags"[^>]*>(.*?)</div>',
            card,
            re.DOTALL,
        )
        if legacy_tags:
            tags.extend(
                _clean(tag)
                for tag in re.findall(r"<span[^>]*>(.*?)</span>", legacy_tags.group(1), re.DOTALL)
                if _clean(tag)
            )

        if not price:
            return None

        return House(
            id=house_id,
            platform="anjuke",
            title=title,
            price=price,
            price_unit="万",
            area=area,
            unit_price=unit_price,
            layout=layout,
            floor=floor,
            orientation=orientation,
            community=community,
            district=district,
            city=city,
            url=url,
            tags=tags,
        )

    def _parse_recommend_card(self, card: str, house_id: str, url: str, city: str) -> House | None:
        # Community / title
        title = ""
        title_m = re.search(r'class="item-info-title"[^>]*>([^<]+)', card)
        if title_m:
            title = _clean(title_m.group(1))

        # Meta: district + layout/area
        district = ""
        layout = ""
        area = 0.0
        meta_spans = re.findall(
            r'<span[^>]*data-v-[^>]*>([^<]+)</span>', card
        )
        for span in meta_spans:
            span = span.strip()
            if not span:
                continue
            # "朝阳 双井" pattern
            if re.match(r'[\u4e00-\u9fff]+\s+[\u4e00-\u9fff]+$', span):
                parts = span.split()
                district = parts[0]
            # "2室1厅 96㎡" pattern
            layout_m = re.search(r'(\d室\d厅)', span)
            if layout_m:
                layout = layout_m.group(1)
            area_m = re.search(r'([\d.]+)㎡', span)
            if area_m:
                area = float(area_m.group(1))

        # Price
        price = 0.0
        price_m = re.search(r'item-info-price-one-num"[^>]*>([\d.]+)', card)
        if price_m:
            price = float(price_m.group(1))

        # Unit price
        unit_price = None
        up_m = re.search(r'item-info-price-one-avg"[^>]*>([\d,]+)元/㎡', card)
        if up_m:
            unit_price = float(up_m.group(1).replace(",", ""))

        if not price:
            return None

        return House(
            id=house_id,
            platform="anjuke",
            title=title,
            price=price,
            price_unit="万",
            area=area,
            unit_price=unit_price,
            layout=layout,
            district=district,
            city=city,
            url=url,
        )

    def _parse_detail(self, html: str, house_id: str, city: str = "beijing") -> HouseDetail:
        title_m = re.search(r"<title>([^<]+)", html)
        title = _clean(title_m.group(1)) if title_m else ""

        price = 0.0
        price_m = re.search(r'item-info-price-one-num[^>]*>([\d.]+)', html)
        if price_m:
            price = float(price_m.group(1))

        transaction_ownership = ""
        house_usage = ""
        ownership = ""
        deed_status = ""

        detail_items = re.findall(
            r"<div[^>]*>\s*<span>\s*([^<]+)\s*</span>\s*<span>\s*([^<]+)\s*</span>\s*</div>",
            html,
            re.DOTALL,
        )
        for label, value in detail_items:
            label = _clean(label)
            value = _clean(value)
            if "交易权属" in label:
                transaction_ownership = value
            elif "房屋用途" in label:
                house_usage = value
            elif "产权所属" in label:
                ownership = value
            elif "房本" in label:
                deed_status = value

        return HouseDetail(
            id=house_id, platform="anjuke", title=title, price=price,
            price_unit="万", area=0.0,
            url=f"https://{city}.anjuke.com/prop/view/{house_id}",
            transaction_ownership=transaction_ownership,
            house_usage=house_usage,
            ownership=ownership,
            deed_status=deed_status,
        )


def _first_class_text(html: str, class_name: str) -> str:
    texts = _class_texts(html, class_name, max_count=1)
    return texts[0] if texts else ""


def _class_texts(html: str, class_name: str, max_count: int | None = None) -> list[str]:
    pattern = re.compile(
        rf'<[^>]*class="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>(.*?)</[^>]+>',
        re.DOTALL,
    )
    texts: list[str] = []
    for match in pattern.finditer(html):
        text = _clean(re.sub(r"<[^>]+>", " ", match.group(1)))
        if text:
            texts.append(text)
        if max_count is not None and len(texts) >= max_count:
            break
    return texts


def _clean(text: str) -> str:
    return unescape(text).strip()
