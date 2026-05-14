# 01 Live Baseline And Regression

Status: ready-for-agent

## What to build

Add a repeatable live baseline workflow that probes `beike`, `lianjia`, and `anjuke` on the same machine and records whether each platform can still return real listings. The workflow should be runnable locally before and after scraper changes so we can catch regressions in cookies, anti-bot behavior, parsing, or transport setup.

## Acceptance criteria

- [ ] There is a single local command that runs a baseline check for all supported platforms.
- [ ] The command returns platform-by-platform status that is easy to compare over time.
- [ ] The baseline output is saved to an artifact or report location for later inspection.
- [ ] The repo documents how to run the baseline and what a healthy result looks like.

## Blocked by

None - can start immediately.

## Comments

2026-05-14:

- Added `uv run housescraper-cli baseline --city 上海`.
- Added `artifacts/baseline/` report output plus per-platform `platform_summary`.
- `lianjia` is now a separate adapter and separate test target instead of a `beike` alias.
- Latest live run on this machine returned healthy results for `beike`, `lianjia`, and `anjuke`.
