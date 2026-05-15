# 04 Listing Detail And Price Check

Status: ready-for-agent

## What to build

Add a detail lookup workflow for a selected listing so the user can verify a price, title, unit price, community name, and related metadata against the original platform page. The result should support quick phone-side spot checks after broad screening.

## Acceptance criteria

- [x] The service can fetch and return structured detail for a selected listing.
- [x] The detail response includes the core verification fields needed for phone comparison.
- [x] Errors caused by anti-bot or missing cookies are surfaced clearly by platform.
- [x] The repo documents at least one real verification example using a recent live listing.

## Blocked by

- `.scratch/multi-platform-house-hunt-v1/issues/06-agent-friendly-search-contract.md`

## Comments

2026-05-14 progress audit:

- Not implemented in the local MCP or local smoke-test CLI.
- The current server only exposes `probe_sources` and `search_listings`.
- Some upstream adapter code already has platform detail methods, but this repo does not yet normalize and expose a listing-detail workflow for agents.

2026-05-15 completion update:

- Added explicit `get_listing_detail` MCP tool that accepts `listing_ref`.
- Added `housescraper-cli detail --listing-ref ...` for local smoke tests and manual verification.
- Detail responses now return structured verification fields such as `price`, `unit_price`, `community`, `layout`, `area`, `url`, and other normalized metadata.
- Cookie / CAPTCHA failures are surfaced as structured `status = error` responses with platform-specific `error_type` and `error_message`.
- `beike` and `lianjia` now have local detail-page parsing support in this repo, and `README.md` includes a local verification flow using a freshly searched Shanghai listing.
