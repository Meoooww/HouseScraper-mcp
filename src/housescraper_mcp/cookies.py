"""Cookie helpers shared by service orchestration and local adapters."""

from __future__ import annotations

from collections.abc import Iterable

from house_cli.client.auth import (
    _try_browser_cookie3,
    get_cookies,
    load_or_extract_cookies,
    save_cookies,
)


def prepare_cookies(domain: str, *, fallback_domains: Iterable[str] = ()) -> dict[str, str]:
    """Load request cookies for one platform, optionally reusing shared SSO cookies.

    The primary domain is refreshed from both the cache file and the browser.
    Fallback domains are only used to fill gaps when the platform has not yet
    written its own browser cookies but still accepts shared session tickets.
    """

    primary_file = get_cookies(domain)
    primary_browser = _try_browser_cookie3(domain)

    merged: dict[str, str] = {}
    for fallback_domain in fallback_domains:
        merged.update(get_cookies(fallback_domain))
        merged.update(_try_browser_cookie3(fallback_domain))

    merged.update(primary_file)
    merged.update(primary_browser)

    if merged:
        if merged != primary_file:
            save_cookies(domain, merged)
        return merged

    return load_or_extract_cookies(domain)
