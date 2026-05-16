"""HTTP client wrapper with anti-detection headers, jitter delays, burst detection, and retry."""

import asyncio
import collections
import gzip
import os
import platform
import random
import re
import shutil
import subprocess
import time
import zlib
from functools import lru_cache

import httpx

try:
    import brotli
except ImportError:  # pragma: no cover - optional at runtime, covered in behavior
    brotli = None


def _detect_browser_family() -> str:
    system = platform.system()
    if system == "Windows":
        edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
        if any(os.path.exists(path) for path in edge_paths):
            return "edge"
        return "chrome"
    if system == "Darwin":
        return "chrome"
    return "chrome"


def _browser_version_command(family: str) -> list[str] | None:
    system = platform.system()
    if family == "edge" and system == "Windows":
        for path in [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]:
            if os.path.exists(path):
                return [path, "--version"]
        return None

    candidates = {
        "chrome": [
            "google-chrome",
            "chrome",
            "chromium",
            "chromium-browser",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ]
    }.get(family, [])
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved, "--version"]
        if os.path.exists(candidate):
            return [candidate, "--version"]
    return None


@lru_cache(maxsize=4)
def _detect_browser_major_version(family: str) -> str:
    command = _browser_version_command(family)
    if command:
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            output = f"{proc.stdout} {proc.stderr}"
            match = re.search(r"(\d+)\.", output)
            if match:
                return match.group(1)
        except Exception:
            pass
    return "148" if family == "edge" else "145"


def build_default_headers() -> dict[str, str]:
    family = _detect_browser_family()
    version = _detect_browser_major_version(family)
    system = platform.system()

    platform_token = {
        "Windows": '"Windows"',
        "Darwin": '"macOS"',
        "Linux": '"Linux"',
    }.get(system, '"Windows"')

    if family == "edge":
        user_agent = (
            f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{version}.0.0.0 Safari/537.36 Edg/{version}.0.0.0"
        )
        sec_ch_ua = (
            f'"Chromium";v="{version}", '
            f'"Microsoft Edge";v="{version}", '
            f'"Not=A?Brand";v="24"'
        )
    elif system == "Darwin":
        user_agent = (
            f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{version}.0.0.0 Safari/537.36"
        )
        sec_ch_ua = (
            f'"Chromium";v="{version}", '
            f'"Google Chrome";v="{version}", '
            f'"Not.A/Brand";v="99"'
        )
    elif system == "Linux":
        user_agent = (
            f"Mozilla/5.0 (X11; Linux x86_64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{version}.0.0.0 Safari/537.36"
        )
        sec_ch_ua = (
            f'"Chromium";v="{version}", '
            f'"Google Chrome";v="{version}", '
            f'"Not.A/Brand";v="99"'
        )
    else:
        user_agent = (
            f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{version}.0.0.0 Safari/537.36"
        )
        sec_ch_ua = (
            f'"Chromium";v="{version}", '
            f'"Google Chrome";v="{version}", '
            f'"Not.A/Brand";v="99"'
        )

    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "sec-ch-ua": sec_ch_ua,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": platform_token,
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Priority": "u=0, i",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    }


DEFAULT_HEADERS = build_default_headers()


def _decode_response_bytes(resp: httpx.Response) -> bytes | None:
    encoding = resp.headers.get("content-encoding", "").lower()
    if not encoding:
        return None

    payload = resp.content
    try:
        if "br" in encoding and brotli is not None:
            return brotli.decompress(payload)
        if "gzip" in encoding:
            return gzip.decompress(payload)
        if "deflate" in encoding:
            try:
                return zlib.decompress(payload)
            except zlib.error:
                return zlib.decompress(payload, -zlib.MAX_WBITS)
    except Exception:
        return None
    return None


def decode_response_content(resp: httpx.Response) -> str:
    decoded = _decode_response_bytes(resp)
    if decoded is None:
        return resp.text

    charset = resp.encoding or "utf-8"
    return decoded.decode(charset, errors="replace")


def _normalize_response_content(resp: httpx.Response):
    decoded = _decode_response_bytes(resp)
    if decoded is None:
        return
    resp._content = decoded
    if "content-encoding" in resp.headers:
        del resp.headers["content-encoding"]

# Retry config
MAX_RETRIES = 3
BACKOFF_BASE = 10  # seconds
BACKOFF_CAP = 60  # max backoff seconds

# Burst detection config
BURST_WINDOW_SIZE = 12  # track last N request timestamps
BURST_SHORT_WINDOW = 15  # seconds
BURST_SHORT_THRESHOLD = 3  # requests in short window
BURST_SHORT_PENALTY = (1.2, 2.8)  # delay range
BURST_LONG_WINDOW = 45  # seconds
BURST_LONG_THRESHOLD = 6  # requests in long window
BURST_LONG_PENALTY = (4.0, 7.0)  # delay range


class HttpClient:
    """Async HTTP client with anti-detection, burst detection, and retry logic."""

    # Per-instance request history to avoid cross-adapter interference during concurrent searches
    _base_delay_multiplier: float = 1.0  # permanent multiplier after rate-limit hits (shared)

    def __init__(self, base_url: str = "", referer: str = ""):
        self._request_history: collections.deque = collections.deque(maxlen=BURST_WINDOW_SIZE)
        headers = build_default_headers()
        if referer:
            headers["Referer"] = referer
        self._client = httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            timeout=httpx.Timeout(30.0),
            http2=False,
        )
        self._base_url = base_url

    async def _jitter_delay(self):
        """Gaussian jitter delay + burst detection penalty."""
        # Base delay: Gaussian jitter (mean=1s, sigma=0.3s) with 5% long pause
        if random.random() < 0.05:
            delay = random.uniform(2.0, 5.0)
        else:
            delay = max(0.1, random.gauss(1.0, 0.3))

        # Apply permanent multiplier (increases after rate-limit hits)
        delay *= self._base_delay_multiplier

        # Burst detection: check recent request frequency
        now = time.monotonic()
        timestamps = list(self._request_history)

        if timestamps:
            # Short burst: 3+ requests in 15 seconds
            recent_short = sum(1 for t in timestamps if now - t < BURST_SHORT_WINDOW)
            if recent_short >= BURST_SHORT_THRESHOLD:
                delay += random.uniform(*BURST_SHORT_PENALTY)

            # Long burst: 6+ requests in 45 seconds
            recent_long = sum(1 for t in timestamps if now - t < BURST_LONG_WINDOW)
            if recent_long >= BURST_LONG_THRESHOLD:
                delay += random.uniform(*BURST_LONG_PENALTY)

        await asyncio.sleep(delay)
        self._request_history.append(time.monotonic())

    def set_referer(self, referer: str):
        """Dynamically update the Referer header for the next request."""
        self._client.headers["Referer"] = referer

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """GET with jitter delay, burst detection, and exponential backoff retry."""
        if not url.startswith("http"):
            url = self._base_url.rstrip("/") + "/" + url.lstrip("/")

        await self._jitter_delay()

        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._client.get(url, **kwargs)
                _normalize_response_content(resp)
                if resp.status_code == 429 or resp.status_code >= 500:
                    wait = min(BACKOFF_BASE * (2 ** attempt), BACKOFF_CAP)
                    # Permanently increase base delay on rate-limit
                    if resp.status_code == 429:
                        HttpClient._base_delay_multiplier = min(
                            HttpClient._base_delay_multiplier * 2, 8.0
                        )
                    await asyncio.sleep(wait)
                    last_exc = httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                    continue
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError:
                raise
            except httpx.HTTPError as e:
                last_exc = e
                wait = min(BACKOFF_BASE * (2 ** attempt), BACKOFF_CAP)
                await asyncio.sleep(wait)

        raise last_exc  # type: ignore[misc]

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
