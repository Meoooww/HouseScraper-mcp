from housescraper_mcp.platforms import resolve_platforms


def test_resolve_platforms_defaults_to_all_supported_platforms() -> None:
    resolved = resolve_platforms(None)
    assert [item.requested for item in resolved] == ["beike", "lianjia", "anjuke"]
    assert [item.canonical for item in resolved] == ["beike", "lianjia", "anjuke"]


def test_resolve_platforms_keeps_lianjia_separate() -> None:
    resolved = resolve_platforms(["lianjia"])
    assert len(resolved) == 1
    assert resolved[0].requested == "lianjia"
    assert resolved[0].canonical == "lianjia"
    assert resolved[0].cookie_domain == "lianjia.com"
    assert resolved[0].fallback_cookie_domains == ("ke.com",)


def test_resolve_platforms_rejects_unknown_values() -> None:
    try:
        resolve_platforms(["foo"])
    except ValueError as exc:
        assert "Unsupported platforms" in str(exc)
    else:
        raise AssertionError("expected ValueError")
