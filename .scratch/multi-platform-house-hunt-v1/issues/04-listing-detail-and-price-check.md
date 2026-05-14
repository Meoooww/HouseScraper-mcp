# 04 Listing Detail And Price Check

Status: ready-for-agent

## What to build

Add a detail lookup workflow for a selected listing so the user can verify a price, title, unit price, community name, and related metadata against the original platform page. The result should support quick phone-side spot checks after broad screening.

## Acceptance criteria

- [ ] The service can fetch and return structured detail for a selected listing.
- [ ] The detail response includes the core verification fields needed for phone comparison.
- [ ] Errors caused by anti-bot or missing cookies are surfaced clearly by platform.
- [ ] The repo documents at least one real verification example using a recent live listing.

## Blocked by

- `.scratch/multi-platform-house-hunt-v1/issues/06-agent-friendly-search-contract.md`

## Comments

2026-05-14 progress audit:

- Not implemented in the local MCP or local smoke-test CLI.
- The current server only exposes `probe_sources` and `search_listings`.
- Some upstream adapter code already has platform detail methods, but this repo does not yet normalize and expose a listing-detail workflow for agents.
