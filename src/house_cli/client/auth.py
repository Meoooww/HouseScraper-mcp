"""Cookie file and DevTools-based credential management.

Cookie resolution order:
1. Manual cookie file ~/.config/house-cli/cookies.json (fastest, user-controlled)
2. Explicit refresh from a verified Chrome/Edge DevTools session
3. Fallback: empty dict (caller handles gracefully)

Cookie file format (cookies.json):
{
    "ke.com": {
        "lianjia_uuid": "xxx",
        "lianjia_ssid": "xxx",
        ...
    }
}
"""

import json
import os
import stat
import time
import urllib.request

CONFIG_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
    "house-cli",
)
COOKIE_FILE = os.path.join(CONFIG_DIR, "cookies.json")
COOKIE_TTL = 7 * 24 * 3600  # 7 days


def _load_cookie_file() -> dict:
    """Load cookies from the manual cookie file."""
    if not os.path.exists(COOKIE_FILE):
        return {}
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_cookies(domain: str, cookies: dict):
    """Save cookies for a domain to the cookie file with restricted permissions."""
    data = _load_cookie_file()
    data[domain] = {
        "_updated_at": int(time.time()),
        **cookies,
    }
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # Set 0o600 permissions (owner read/write only)
    try:
        os.chmod(COOKIE_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass  # Windows may not support chmod fully


def get_cookies(domain: str) -> dict:
    """Get cookies for a domain. Returns empty dict if none or expired."""
    data = _load_cookie_file()
    entry = data.get(domain, {})
    if not entry:
        return {}
    updated = entry.get("_updated_at", 0)
    if time.time() - updated > COOKIE_TTL:
        return {}
    # Strip internal keys
    return {k: v for k, v in entry.items() if not k.startswith("_")}


def load_or_extract_cookies(domain: str) -> dict:
    """Load cookies from the explicit cookie file.

    Browser database extraction is intentionally not used here. On current
    Windows/Edge builds it is often locked or encrypted in a way that fails
    silently. Use refresh_cookies_from_cdp after completing browser verification.
    """
    return get_cookies(domain)


def _domain_matches(host: str, domain: str) -> bool:
    host = host.lstrip(".")
    domain = domain.lstrip(".")
    return host == domain or host.endswith(f".{domain}")


def refresh_cookies_from_cdp(domain: str, port: int = 9222) -> dict:
    """Refresh cookies from a running Chromium/Edge DevTools session.

    Start Edge/Chrome with --remote-debugging-port=9222, complete the target
    site's login or verification in that browser, then call this function.
    """
    try:
        import websocket
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError(
            "websocket-client is required for CDP cookie refresh. "
            "Install dependencies from pyproject.toml first."
        ) from exc

    tabs_url = f"http://127.0.0.1:{port}/json"
    try:
        with urllib.request.urlopen(tabs_url, timeout=5) as resp:
            tabs = json.load(resp)
    except OSError as exc:
        raise RuntimeError(
            f"Cannot connect to Chrome/Edge DevTools at {tabs_url}. "
            f"Start the browser with --remote-debugging-port={port} first."
        ) from exc

    page = next(
        (
            tab for tab in tabs
            if tab.get("type") == "page"
            and domain.lstrip(".") in tab.get("url", "")
            and tab.get("webSocketDebuggerUrl")
        ),
        None,
    )
    if page is None:
        raise RuntimeError(
            f"No open page for {domain} found in DevTools. "
            "Open the verified target page in that browser first."
        )

    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)
    try:
        ws.send(json.dumps({"id": 1, "method": "Network.getAllCookies"}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                break
    finally:
        ws.close()

    cookies = {
        item["name"]: item.get("value", "")
        for item in msg.get("result", {}).get("cookies", [])
        if _domain_matches(item.get("domain", ""), domain)
    }
    if not cookies:
        raise RuntimeError(f"No {domain} cookies found in the verified browser page.")

    save_cookies(domain, cookies)
    return cookies
