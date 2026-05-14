# 03 Cross-Platform Aggregation And Dedup

Status: ready-for-agent

## What to build

Add a true multi-platform house-hunting workflow that queries several supported platforms in one call, merges the results, and reduces obvious duplicates. The output should help with broad screening instead of forcing the user to compare each platform separately.

## Acceptance criteria

- [x] One MCP call can search multiple platforms and return a merged result set.
- [x] The merged output preserves source-platform visibility for each listing.
- [ ] Obvious duplicates are grouped or removed using stable heuristics.
- [ ] The merged workflow has a local verification example and test coverage for the dedup behavior.

## Blocked by

- `.scratch/multi-platform-house-hunt-v1/issues/06-agent-friendly-search-contract.md`

## Comments

2026-05-14 progress audit:

- Partially implemented.
- `search_listings` already supports multi-platform search in one call and returns merged normalized listings plus per-platform status.
- Source-platform visibility already exists through per-listing `platform` fields and platform-status metadata.
- Duplicate heuristics, `listing_ref`, `duplicate_id`, and explicit duplicate ordering are not implemented yet.
