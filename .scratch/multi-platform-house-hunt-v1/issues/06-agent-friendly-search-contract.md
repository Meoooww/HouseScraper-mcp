# 06 Agent-Friendly Search Contract

Status: ready-for-agent

## What to build

Refactor the main search MCP tool into a cleaner agent-facing contract for broad house-hunting queries. The first implementation wave should focus on the primary search path only, not the diagnose tool. The goal is to make the service honest, low-complexity, and easy for an outer agent to reason about without guessing.

## Decisions captured from the grill session

- This repo remains an `Agent 工具层` local MCP service, not a direct end-user product and not an embedded analysis engine.
- The MCP stays stateless for normal use: query current listings on demand, do not add long-term history or monitoring in this wave.
- The real first-stage promise is buy-side broad screening. Keep the `listing_type` shape compatible with future rent work, but do not treat rent as a committed first-wave capability.
- Normal agent flow is direct search first, then diagnosis only when results look suspicious.
- Break compatibility if needed to get the contract clean. Do not optimize for preserving the current response schema.
- Prioritize the search path in this wave. Diagnose-tool contract cleanup is a follow-up issue.

## Contract requirements

- [ ] Rename the public search MCP tool to a cleaner agent-facing name if needed as part of the contract cleanup.
- [ ] Remove `sort_by` from the first-wave MCP search interface because the current implementation does not reliably honor it across platforms.
- [ ] Keep the search interface structured-parameter only. Do not add a free-form natural language query field.
- [ ] Default to searching all three platforms when `platforms` is omitted: `beike`, `lianjia`, and `anjuke`.
- [ ] If `platforms` is provided, search only the requested subset.
- [ ] Keep `page`, but enforce a maximum page value of `3`.
- [ ] Keep `limit`, with default `20` and maximum `30`.
- [ ] Preserve the single-page behavior. One call may fetch one page only; do not add automatic multi-page traversal.

## Response-shape requirements

- [ ] Replace the top-level `ok` contract with an explicit top-level `status` enum.
- [ ] The top-level search `status` must use these values: `success`, `partial_success`, `no_results`, `error`.
- [ ] Use a two-layer response shape with `meta` for control/status information and `data` for returned listings.
- [ ] Adopt consistent machine-style naming in the new response contract.
- [ ] At platform level, replace `ok` with a platform `status` enum using: `success`, `no_results`, `error`.
- [ ] Keep stable machine-readable failure details at platform level via `error_type` and `error_message`.
- [ ] Keep platform-level `filter_mode` so the outer agent can distinguish default server-side behavior from client-side post-filtered behavior.
- [ ] Do not add `filters_executed` or a second full filter payload in this wave. `filter_mode` alone is enough for now.

## Search-result requirements

- [ ] Every listing must include the original platform `id`.
- [ ] Every listing must also include a stable agent-facing `listing_ref`.
- [ ] `listing_ref` should be unambiguous across platforms, for example `beike:107114117310`.
- [ ] The first-wave contract should reserve `listing_ref` as the future input for listing-detail lookup, even though detail lookup is out of scope for this issue.
- [ ] Add duplicate-marking fields directly on each listing rather than returning a separate duplicate map.
- [ ] The contract should not hard-merge suspected duplicates in this wave.
- [ ] Use a `duplicate_id` field that points to the retained listing's `listing_ref`.
- [ ] A retained primary listing should be represented as not duplicated rather than pointing to itself.
- [ ] Suspected duplicates should be moved behind primary results in the returned ordering.
- [ ] Suspected duplicates still count toward `limit`.
- [ ] It is acceptable to mark two listings as suspected duplicates even if their prices differ.
- [ ] Do not depend on room-number or apartment-number matching in the first-wave duplicate heuristic.

## Search-meta requirements

- [ ] `meta` must include `raw_count`, meaning the total number of listings gathered before final return truncation.
- [ ] `meta` must include `possible_duplicate_count`.
- [ ] `meta` must include `returned_count`.
- [ ] `meta` must include `truncated`.
- [ ] When all searched platforms execute normally but no listings remain after filtering, return top-level `status = no_results`.
- [ ] When at least one platform succeeds and at least one platform errors, return top-level `status = partial_success`.

## Non-goals for this issue

- Do not add detail lookup in this wave.
- Do not expose baseline as a formal MCP tool in this wave.
- Do not redesign the diagnose tool yet.
- Do not add natural-language parsing.
- Do not add history, snapshots, background monitoring, or reminders.
- Do not automate browser login or cookie refresh beyond the current passive browser-cookie dependency.
- Do not add a standalone schema-version field in the response.
- Do not write search artifacts by default.

## Suggested verification

- [ ] Update or replace tests so the new top-level `status` and `meta/data` shape are covered.
- [ ] Add coverage for default-platform behavior including implicit `lianjia`.
- [ ] Add coverage for `limit <= 30` and `page <= 3` validation.
- [ ] Add coverage for suspected-duplicate ordering and `duplicate_id` / `listing_ref` behavior.
- [ ] Add coverage for `partial_success` and `no_results` top-level status handling.

## Follow-up issues to create later

- Align and rename the diagnose/probe MCP tool with the same `meta/data` response shell.
- Add an explicit detail lookup tool that accepts `listing_ref`.

## Comments

2026-05-14:

- Captured from the `grill-me` session.
- Progress audit: current MCP behavior still diverges from this target contract in several important ways: top-level responses still use `ok`, default platforms are still `beike + anjuke`, `sort_by` is still public, and there is no `listing_ref` or duplicate annotation yet.
