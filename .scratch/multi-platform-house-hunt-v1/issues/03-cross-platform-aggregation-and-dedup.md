# 03 Cross-Platform Aggregation And Dedup

Status: ready-for-agent

## What to build

Add a true multi-platform house-hunting workflow that queries several supported platforms in one call, merges the results, and reduces obvious duplicates. The output should help with broad screening instead of forcing the user to compare each platform separately.

## Acceptance criteria

- [ ] One MCP call can search multiple platforms and return a merged result set.
- [ ] The merged output preserves source-platform visibility for each listing.
- [ ] Obvious duplicates are grouped or removed using stable heuristics.
- [ ] The merged workflow has a local verification example and test coverage for the dedup behavior.

## Blocked by

- `.scratch/multi-platform-house-hunt-v1/issues/01-live-baseline-and-regression.md`

## Comments
