from housescraper_mcp.cookies import prepare_cookies


def test_prepare_cookies_merges_browser_values_into_cached_file(monkeypatch) -> None:
    saved: dict[str, dict[str, str]] = {}

    monkeypatch.setattr("housescraper_mcp.cookies.get_cookies", lambda domain: {"lianjia_ssid": "old"})
    monkeypatch.setattr(
        "housescraper_mcp.cookies._try_browser_cookie3",
        lambda domain: {"lianjia_ssid": "new", "hip": "ok", "srcid": "1"},
    )
    monkeypatch.setattr(
        "housescraper_mcp.cookies.save_cookies",
        lambda domain, cookies: saved.setdefault(domain, cookies),
    )

    cookies = prepare_cookies("ke.com")

    assert cookies["lianjia_ssid"] == "new"
    assert cookies["hip"] == "ok"
    assert saved["ke.com"]["srcid"] == "1"


def test_prepare_cookies_can_fill_lianjia_from_ke_fallback(monkeypatch) -> None:
    saved: dict[str, dict[str, str]] = {}

    def fake_get_cookies(domain: str) -> dict[str, str]:
        if domain == "ke.com":
            return {"lianjia_token": "shared-token"}
        return {}

    monkeypatch.setattr("housescraper_mcp.cookies.get_cookies", fake_get_cookies)
    monkeypatch.setattr("housescraper_mcp.cookies._try_browser_cookie3", lambda domain: {})
    monkeypatch.setattr(
        "housescraper_mcp.cookies.save_cookies",
        lambda domain, cookies: saved.setdefault(domain, cookies),
    )

    cookies = prepare_cookies("lianjia.com", fallback_domains=("ke.com",))

    assert cookies["lianjia_token"] == "shared-token"
    assert saved["lianjia.com"]["lianjia_token"] == "shared-token"
