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
from html import unescape

from house_cli.client.base import BaseClient
from house_cli.client.http import HttpClient
from house_cli.client.auth import load_or_extract_cookies, save_cookies
from house_cli.models.house import House, HouseDetail
from house_cli.models.filter import SearchFilter
from house_cli.models.cities import DISTRICTS

CITY_INDEX_URL = "https://www.anjuke.com/sy-city.html"


class AnjukeClient(BaseClient):
    """Anjuke adapter (buy + rent). Requires browser cookies."""

    platform_name = "anjuke"
    _city_slug_cache: dict[str, str] = {}

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

    def _build_list_url(self, city_slug: str, filters: SearchFilter) -> str:
        district_map = DISTRICTS.get(filters.city, {})
        district_slug = district_map.get(filters.district or "", "")

        if district_slug:
            return f"https://{city_slug}.anjuke.com/sale/{district_slug}/"
        return f"https://{city_slug}.anjuke.com/sale/?from=HomePage_Search"

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

        flow = getattr(filters, "anjuke_flow", "auto")
        async with HttpClient(referer=referer) as client:
            city = await self._resolve_city_slug(filters.city, client, cookies)
            sale_url = self._build_list_url(city, filters)
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

                if resp.status_code != 403 and len(html) > 5000:
                    houses = self._parse_list(html, filters.city)
                    if houses:
                        return houses

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
                    retry_houses = self._parse_list(html, filters.city)
                    if retry_houses:
                        return retry_houses
            except Exception:
                html = ""

            if flow in {"search", "auto"}:
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

        return HouseDetail(
            id=house_id, platform="anjuke", title=title, price=price,
            price_unit="万", area=0.0,
            url=f"https://{city}.anjuke.com/prop/view/{house_id}",
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
