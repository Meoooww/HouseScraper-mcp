# 05 Candidate Export

Status: ready-for-agent

## What to build

Add a shortlist export workflow so the user can take filtered and verified candidates out of the MCP client and continue comparison in a spreadsheet or notes tool. The export should focus on fields that are useful for manual house-hunting decisions.

## Acceptance criteria

- [ ] The service or local CLI can export a shortlist in a simple file format such as JSON or CSV.
- [ ] The export includes enough fields for side-by-side manual comparison.
- [ ] The export can include merged results from multiple platforms.
- [ ] The repo documents how to generate and inspect an export locally.

## Blocked by

- `.scratch/multi-platform-house-hunt-v1/issues/03-cross-platform-aggregation-and-dedup.md`
- `.scratch/multi-platform-house-hunt-v1/issues/04-listing-detail-and-price-check.md`

## Comments

2026-05-14 progress audit:

- Not started in this repo's MCP or local CLI surface.
- There is no shortlist export workflow documented or exposed from the local `housescraper-cli`.
- The upstream `house-cli` dependency has its own export command, but that capability is not yet wired into this repo's candidate-screening workflow.
