"""Local platform adapters that wrap or extend upstream house-cli behavior."""

from __future__ import annotations

import re
from html import unescape

from house_cli.client.http import HttpClient
from house_cli.client.auth import save_cookies
from house_cli.models.cities import CITY_ABBR, DISTRICTS
from house_cli.models.filter import SearchFilter
from house_cli.models.house import House

from housescraper_mcp.cookies import prepare_cookies


class KeFamilyClient:
    """Shared list-page implementation for the Ke/Lianjia family sites."""

    platform_name = "beike"
    site_domain = "ke.com"
    cookie_domain = "ke.com"
    fallback_cookie_domains: tuple[str, ...] = ()

    def _build_list_url(self, filters: SearchFilter) -> str:
        city_abbr = CITY_ABBR.get(filters.city, "sh")
        base = f"https://{city_abbr}.{self.site_domain}/ershoufang/"

        parts: list[str] = []
        district_map = DISTRICTS.get(filters.city, {})
        if filters.district:
            slug = district_map.get(filters.district, "")
            if slug:
                parts.append(slug + "/")

        segs: list[str] = []
        if filters.min_price is not None or filters.max_price is not None:
            lo = int(filters.min_price) if filters.min_price else 0
            hi = int(filters.max_price) if filters.max_price else 0
            if lo and hi:
                segs.append(f"bp{lo}ep{hi}")
            elif lo:
                segs.append(f"bp{lo}ep0")
            elif hi:
                segs.append(f"bp0ep{hi}")

        if filters.min_area is not None or filters.max_area is not None:
            lo = int(filters.min_area) if filters.min_area else 0
            hi = int(filters.max_area) if filters.max_area else 0
            if lo and hi:
                segs.append(f"ba{lo}ea{hi}")
            elif lo:
                segs.append(f"ba{lo}ea0")
            elif hi:
                segs.append(f"ba0ea{hi}")

        if filters.layout:
            match = re.search(r"(\d)", filters.layout)
            if match:
                room_count = int(match.group(1))
                if 1 <= room_count <= 5:
                    segs.append(f"l{room_count}")

        if filters.page > 1:
            segs.append(f"pg{filters.page}")

        filter_str = "".join(segs)
        if filter_str:
            if parts:
                return base + parts[0] + filter_str + "/"
            return base + filter_str + "/"

        if parts:
            return base + parts[0]
        return base

    async def search(self, filters: SearchFilter) -> list[House]:
        city_abbr = CITY_ABBR.get(filters.city, "sh")
        url = self._build_list_url(filters)
        referer = f"https://{city_abbr}.{self.site_domain}/ershoufang/"
        cookies = prepare_cookies(
            self.cookie_domain,
            fallback_domains=self.fallback_cookie_domains,
        )

        async with HttpClient(referer=referer) as client:
            resp = await client.get(url, cookies=cookies)
            if resp.cookies:
                merged = {**cookies, **{key: value for key, value in resp.cookies.items()}}
                save_cookies(self.cookie_domain, merged)
            html = resp.text

        if self._looks_like_captcha(html):
            domains = ", ".join((self.cookie_domain, *self.fallback_cookie_domains))
            raise RuntimeError(
                f"{self.site_domain} returned CAPTCHA. Please visit {domains} in your browser first, "
                "then retry the MCP service."
            )

        return self._parse_list(html, filters.city)

    def _looks_like_captcha(self, html: str) -> bool:
        title = _extract_title(html).upper()
        return title == "CAPTCHA" or "sellListContent" not in html or 'class="priceInfo"' not in html

    def _parse_list(self, html: str, city: str) -> list[House]:
        container_match = re.search(
            r'<ul[^>]*class="sellListContent"[^>]*>(.*?)</ul>',
            html,
            re.DOTALL,
        )
        if container_match is None:
            return []

        houses: list[House] = []
        container = container_match.group(1)
        for match in re.finditer(r'<li class="clear[^"]*"[^>]*>(.*?)</li>', container, re.DOTALL):
            house = self._parse_card(match.group(0), city)
            if house is not None:
                houses.append(house)
        return houses

    def _parse_card(self, card: str, city: str) -> House | None:
        href_match = re.search(r'href="(https?://[^"]*?/ershoufang/(\d+)\.html)"', card)
        if href_match is None:
            return None

        url = href_match.group(1)
        house_id = href_match.group(2)
        title = self._extract_title_from_card(card)
        community = self._extract_community(card)
        district = self._extract_district(card)
        layout, area, orientation, floor = self._extract_house_info(card)
        listing_date = self._extract_listing_date(card)
        tags = self._extract_tags(card)

        price = 0.0
        price_match = re.search(
            r'class="totalPrice[^"]*">\s*(?:<i>\s*</i>)?\s*<span[^>]*>\s*([\d.]+)\s*</span>',
            card,
            re.DOTALL,
        )
        if price_match is not None:
            price = float(price_match.group(1))

        unit_price = None
        unit_price_match = re.search(
            r'class="unitPrice"[^>]*>\s*<span>\s*([^<]+)\s*</span>',
            card,
            re.DOTALL,
        )
        if unit_price_match is not None:
            raw = unit_price_match.group(1).replace(",", "").replace("元/平", "").strip()
            if raw:
                unit_price = float(raw)

        return House(
            id=house_id,
            platform=self.platform_name,
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
            listing_date=listing_date,
            tags=tags,
        )

    def _extract_title_from_card(self, card: str) -> str:
        patterns = [
            r'<div class="title">\s*<a[^>]*>([^<]+)</a>',
            r'<a[^>]*class="[^"]*maidian-detail[^"]*"[^>]*>([^<]+)</a>',
            r'title="([^"]+)"',
        ]
        for pattern in patterns:
            match = re.search(pattern, card, re.DOTALL)
            if match is not None:
                return _clean(match.group(1))
        return ""

    def _extract_community(self, card: str) -> str:
        match = re.search(r'href="https?://[^"]*?/xiaoqu/\d+/?"[^>]*>([^<]+)</a>', card)
        return _clean(match.group(1)) if match is not None else ""

    def _extract_district(self, card: str) -> str:
        position_match = re.search(r'<div class="positionInfo">(.*?)</div>', card, re.DOTALL)
        if position_match is not None:
            links = re.findall(r'<a[^>]*>([^<]+)</a>', position_match.group(1))
            if len(links) >= 2:
                return _clean(links[1])

        alt_match = re.search(r'alt="[^"]*-(?:上海|北京|深圳|广州)(\S+?)二手房"', card)
        if alt_match is None:
            return ""

        raw_district = alt_match.group(1)
        for district in [
            "浦东",
            "闵行",
            "宝山",
            "徐汇",
            "普陀",
            "杨浦",
            "长宁",
            "松江",
            "嘉定",
            "黄浦",
            "静安",
            "虹口",
            "青浦",
            "奉贤",
            "金山",
            "崇明",
        ]:
            if raw_district.startswith(district):
                return district
        return raw_district

    def _extract_house_info(self, card: str) -> tuple[str, float, str, str]:
        info_match = re.search(r'class="houseInfo"[^>]*>(.*?)</div>', card, re.DOTALL)
        if info_match is None:
            return "", 0.0, "", ""

        segments = [_clean(segment) for segment in _strip_tags(info_match.group(1)).split("|")]
        layout = ""
        area = 0.0
        orientation = ""
        floor = ""
        for segment in segments:
            compact = segment.replace(" ", "")
            if not segment:
                continue
            if "室" in segment or "厅" in segment or "房" in segment:
                layout = segment
                continue
            if "平米" in segment or "平" in segment:
                area_match = re.search(r"([\d.]+)", segment)
                if area_match is not None:
                    area = float(area_match.group(1))
                continue
            if "楼层" in segment or ("共" in segment and "层" in segment):
                floor = segment
                continue
            if re.search(r"\d{4}年", segment):
                continue
            if re.fullmatch(r"[东南西北\s]+", compact):
                orientation = compact
        return layout, area, orientation, floor

    def _extract_listing_date(self, card: str) -> str:
        follow_match = re.search(r'class="followInfo"[^>]*>(.*?)</div>', card, re.DOTALL)
        if follow_match is None:
            return ""

        follow_text = _strip_tags(follow_match.group(1))
        match = re.search(r"/\s*([^/]+?发布)", follow_text)
        return _clean(match.group(1)) if match is not None else ""

    def _extract_tags(self, card: str) -> list[str]:
        tags: list[str] = []

        title_tag = re.search(r'<span class="goodhouse_tag[^"]*">([^<]+)</span>', card)
        if title_tag is not None:
            tags.append(_clean(title_tag.group(1)))

        tag_block = re.search(r'<div class="tag">(.*?)</div>', card, re.DOTALL)
        if tag_block is not None:
            tags.extend(
                _clean(value)
                for value in re.findall(r"<span[^>]*>\s*([^<]+?)\s*</span>", tag_block.group(1))
            )

        deduped: list[str] = []
        seen: set[str] = set()
        for tag in tags:
            if not tag or tag in seen:
                continue
            seen.add(tag)
            deduped.append(tag)
        return deduped


class BeikeClient(KeFamilyClient):
    platform_name = "beike"
    site_domain = "ke.com"
    cookie_domain = "ke.com"
    fallback_cookie_domains = ()


class LianjiaClient(KeFamilyClient):
    platform_name = "lianjia"
    site_domain = "lianjia.com"
    cookie_domain = "lianjia.com"
    fallback_cookie_domains = ("ke.com",)


def _extract_title(html: str) -> str:
    match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return _clean(match.group(1)) if match is not None else ""


def _clean(text: str) -> str:
    return unescape(text).strip()


def _strip_tags(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
