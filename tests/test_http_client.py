import gzip

import httpx

from house_cli.client import http as http_module


def _make_response(body: bytes, headers: dict[str, str] | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://example.com/")
    return httpx.Response(200, headers=headers or {}, content=body, request=request)


def test_build_default_headers_matches_windows_edge(monkeypatch):
    monkeypatch.setattr(http_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(http_module, "_detect_browser_family", lambda: "edge")
    monkeypatch.setattr(http_module, "_detect_browser_major_version", lambda family: "148")

    headers = http_module.build_default_headers()

    assert "Windows NT 10.0" in headers["User-Agent"]
    assert "Edg/148.0.0.0" in headers["User-Agent"]
    assert "Microsoft Edge" in headers["sec-ch-ua"]
    assert headers["sec-ch-ua-platform"] == '"Windows"'


def test_decode_response_content_handles_brotli():
    raw_html = b"<html><body><ul class='sellListContent'></ul></body></html>"
    compressed = http_module.brotli.compress(raw_html)
    response = _make_response(
        compressed,
        headers={
            "content-encoding": "br",
            "content-type": "text/html; charset=UTF-8",
        },
    )

    decoded = http_module.decode_response_content(response)

    assert decoded == raw_html.decode("utf-8")


def test_decode_response_content_handles_gzip():
    raw_html = b"<html><body>ok</body></html>"
    compressed = gzip.compress(raw_html)
    response = _make_response(
        compressed,
        headers={
            "content-encoding": "gzip",
            "content-type": "text/html; charset=UTF-8",
        },
    )

    decoded = http_module.decode_response_content(response)

    assert decoded == raw_html.decode("utf-8")
