from housescraper_mcp.platforms import resolve_platforms


def test_resolve_platforms_defaults_to_beike_and_anjuke() -> None:
    resolved = resolve_platforms(None)
    assert [item.requested for item in resolved] == ["beike", "anjuke"]
    assert [item.canonical for item in resolved] == ["beike", "anjuke"]


def test_resolve_platforms_maps_lianjia_to_beike() -> None:
    resolved = resolve_platforms(["lianjia"])
    assert len(resolved) == 1
    assert resolved[0].requested == "lianjia"
    assert resolved[0].canonical == "beike"
    assert resolved[0].cookie_domain == "ke.com"


def test_resolve_platforms_rejects_unknown_values() -> None:
    try:
        resolve_platforms(["foo"])
    except ValueError as exc:
        assert "Unsupported platforms" in str(exc)
    else:
        raise AssertionError("expected ValueError")
