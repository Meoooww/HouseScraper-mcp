# 02 Community Keyword Search

Status: ready-for-agent

## What to build

Add keyword search oriented around community names, building names, and user-entered text so the service is not limited to city-wide broad filtering. A user should be able to search for a known community or project name and get normalized results from the supported platforms whenever the upstream source can expose them.

## Acceptance criteria

- [x] The MCP service accepts a keyword or community name in its search workflow.
- [x] Supported platforms use the keyword when building upstream requests or filtering returned results.
- [x] The returned results make it obvious which fields matched the keyword.
- [x] The repo includes at least one local verification example for a real Shanghai community or project name.

## Blocked by

- `.scratch/multi-platform-house-hunt-v1/issues/06-agent-friendly-search-contract.md`

## Comments

2026-05-14 progress audit:

- Not started in the local MCP layer.
- The current MCP server and local CLI do not expose a keyword or community-name search parameter.
- The upstream `SearchFilter` model includes a `keywords` field, but this repo does not currently pass it through or report which fields matched.

2026-05-15 completion update:

- `search_listings` now accepts a public `keyword` parameter and maps it into the shared `SearchFilter.keywords`.
- Local CLI `housescraper-cli search` now accepts `--keyword` for smoke tests and manual verification.
- Search results now expose `keyword_match.matched_fields` so agents can see why a listing matched.
- The service keeps the anti-bot conservative path for `beike` / `lianjia`: keyword queries are still validated locally through post-filtering, while supported upstream requests continue to receive the keyword where appropriate.
- `README.md` now includes a real Shanghai verification example using `世茂滨江花园`.
