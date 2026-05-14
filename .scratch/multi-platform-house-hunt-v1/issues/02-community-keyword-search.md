# 02 Community Keyword Search

Status: ready-for-agent

## What to build

Add keyword search oriented around community names, building names, and user-entered text so the service is not limited to city-wide broad filtering. A user should be able to search for a known community or project name and get normalized results from the supported platforms whenever the upstream source can expose them.

## Acceptance criteria

- [ ] The MCP service accepts a keyword or community name in its search workflow.
- [ ] Supported platforms use the keyword when building upstream requests or filtering returned results.
- [ ] The returned results make it obvious which fields matched the keyword.
- [ ] The repo includes at least one local verification example for a real Shanghai community or project name.

## Blocked by

- `.scratch/multi-platform-house-hunt-v1/issues/06-agent-friendly-search-contract.md`

## Comments

2026-05-14 progress audit:

- Not started in the local MCP layer.
- The current MCP server and local CLI do not expose a keyword or community-name search parameter.
- The upstream `SearchFilter` model includes a `keywords` field, but this repo does not currently pass it through or report which fields matched.
