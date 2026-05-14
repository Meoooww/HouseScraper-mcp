# Agent-Friendly Search Contract V1

Status: ready-for-agent

## Problem Statement

As the owner of a local MCP service for house-hunting, I want the main search workflow to be reliable and easy for an outer agent to consume without guessing. The current search behavior can return useful listings, but its public contract is still closer to an internal script response than a stable agent-facing protocol. Top-level success is expressed too loosely, default platform behavior does not fully match the desired product behavior, duplicate handling is under-specified, and some public inputs such as sorting imply capabilities that are not consistently implemented across platforms.

From the user's perspective, the MCP should behave like a low-complexity, honest search tool: search current listings on demand, return machine-friendly status and metadata, surface partial success clearly, mark possible duplicates without over-claiming, and avoid pretending to support features that are not truly dependable yet.

## Solution

Refactor the primary search path into a cleaner agent-facing MCP contract focused on broad buy-side screening across `beike`, `lianjia`, and `anjuke`. The first wave should keep the tool stateless, structured-input-only, single-page, and conservative about anti-bot risk. The MCP should expose a normalized `meta/data` response shape, explicit status enums, unambiguous listing references, and lightweight possible-duplicate annotations that help an outer agent reason about results without requiring embedded analysis logic.

This PRD covers the main search workflow only. Diagnose/probe contract cleanup and detail lookup are follow-up work.

## User Stories

1. As an outer agent, I want to call one search tool across multiple housing platforms, so that I can gather a broad set of current listings in one workflow.
2. As an outer agent, I want omitted `platforms` input to search all supported platforms by default, so that I do not accidentally miss listings because of an implicit narrow default.
3. As an outer agent, I want explicitly provided `platforms` input to limit the search scope to only those platforms, so that I can narrow calls deliberately.
4. As an outer agent, I want the search tool to accept structured filtering parameters instead of free-form language, so that I can control query construction deterministically.
5. As an outer agent, I want the search tool to preserve single-page behavior, so that I can reason about cost and anti-bot risk per call.
6. As an outer agent, I want page and limit bounds to be enforced, so that I do not accidentally treat the MCP as a bulk crawler.
7. As an outer agent, I want a top-level `status` enum instead of a loose boolean success flag, so that I can distinguish `success`, `partial_success`, `no_results`, and `error` without inference.
8. As an outer agent, I want each searched platform to report its own status, so that I can tell whether one platform failed while others succeeded.
9. As an outer agent, I want stable machine-readable failure categories and human-readable failure messages, so that I can branch on error type and still inspect what happened.
10. As an outer agent, I want the response split into `meta` and `data`, so that I can separate control information from business results cleanly.
11. As an outer agent, I want machine-style naming across the new contract, so that similar concepts are consistently named and easier to parse.
12. As an outer agent, I want each listing to include a platform-native `id`, so that I can still inspect the underlying listing identifier when needed.
13. As an outer agent, I want each listing to include a stable `listing_ref`, so that I can reference results unambiguously across platforms and future tools.
14. As an outer agent, I want `listing_ref` to be future-proof for detail lookup, so that later deeper workflows can reuse the same stable identifier.
15. As an outer agent, I want possible duplicates to be marked directly on listings instead of silently merged, so that I can keep the original evidence while avoiding false confidence.
16. As an outer agent, I want `duplicate_id` to point to the retained listing reference, so that I can group suspected duplicates with simple logic.
17. As an outer agent, I want retained primary listings to remain clearly primary, so that I do not have to interpret self-referential duplicate markers.
18. As an outer agent, I want possible duplicates sorted behind primary listings, so that the first results I inspect are more likely to be unique candidates.
19. As an outer agent, I want possible duplicates to still count toward `limit`, so that the returned count has simple semantics and does not imply hidden fetch expansion.
20. As an outer agent, I want possible duplicates to be allowed even when prices differ, so that mild cross-platform drift does not prevent useful duplicate hints.
21. As an outer agent, I want duplicate heuristics to avoid relying on apartment or room numbers in the first wave, so that the tool stays compatible with current list-page data.
22. As an outer agent, I want metadata counts for raw listings, possible duplicates, returned listings, and truncation, so that I can understand how much of the candidate set I am actually seeing.
23. As an outer agent, I want `no_results` to mean the query executed normally but matched nothing after filtering, so that I do not mistake an empty result for a broken source.
24. As an outer agent, I want `partial_success` to mean some platforms succeeded while others errored, so that I can continue with caution instead of treating the whole call as healthy.
25. As an outer agent, I want platform-level `filter_mode`, so that I can understand whether results came from native server-side constraints or client-side post-filtering.
26. As an outer agent, I want the search tool to avoid exposing unsupported sort behavior, so that I do not trust ordering controls that are not truly implemented.
27. As an outer agent, I want the MCP to stay passive about browser cookies and login state, so that the tool remains low-complexity and does not become a browser automation system.
28. As a repository maintainer, I want the first wave to focus on the search path only, so that we can stabilize the main workflow before redesigning diagnosis or detail lookup.
29. As a repository maintainer, I want the search contract to be testable at the service boundary and in isolated helper modules, so that the behavior can evolve safely.
30. As a repository maintainer, I want the new contract to be explicit enough that future diagnose and detail tools can align with it later, so that the MCP grows as a coherent tool family instead of a loose set of responses.

## Implementation Decisions

- The feature remains an `Agent 工具层` local MCP service, not a direct end-user application and not an embedded recommendation engine.
- The service remains stateless in normal operation. The first wave does not add history, monitoring, background jobs, or long-term snapshots.
- The real committed workflow is broad buy-side screening. The public shape may continue to include `listing_type` for forward compatibility, but rent support is not a first-wave promise.
- The main search tool may be renamed as part of the contract cleanup if that yields a clearer agent-facing vocabulary.
- The public MCP search input stays structured-parameter-only. Do not add a natural-language query entrypoint in this wave.
- Omitted `platforms` input should default to all three supported platforms: `beike`, `lianjia`, and `anjuke`.
- Provided `platforms` input should be treated as an exact requested subset.
- Remove public sorting input from the first-wave search tool because current platform behavior does not reliably implement it.
- Keep single-page search semantics. One call may request one page only, and the service should not auto-traverse more pages behind the scenes.
- Retain `page` but bound it to `1..3`.
- Retain `limit` with a default of `20` and a maximum of `30`.
- Replace top-level boolean success semantics with an explicit top-level `status` enum: `success`, `partial_success`, `no_results`, `error`.
- Use a two-layer response envelope:
  - `meta` contains query context, status, counts, and per-platform status summaries.
  - `data` contains the returned listing payload.
- Standardize naming toward machine-style contract terms rather than loosely mixed human/script-style naming.
- Replace platform-level boolean status with a platform `status` enum: `success`, `no_results`, `error`.
- Preserve machine-readable platform failure classification and human-readable platform failure detail through `error_type` and `error_message`.
- Keep platform-level `filter_mode` as the only first-wave exposure of relaxed-query behavior. Do not add a second full filter payload such as `filters_executed`.
- Introduce a stable listing reference concept for agent consumption. Each listing should expose both native `id` and derived `listing_ref`.
- `listing_ref` must be unambiguous across platforms and suitable for future detail lookup, for example a `platform:id` shape.
- Possible duplicate handling should be extracted into a deep, isolated helper module with a simple interface that accepts normalized listings and returns annotated, ordered results. This module encapsulates heuristic grouping without forcing the service orchestration layer to understand duplicate internals.
- Possible duplicates are advisory only in this wave. The contract marks them but does not hard-merge them into one listing.
- Each listing may expose `duplicate_id` pointing at the retained primary listing's `listing_ref`.
- Retained primary listings should remain clearly non-duplicate rather than pointing to themselves.
- Possible duplicates should be ordered after primary results.
- Possible duplicates still count toward the final `limit`.
- Duplicate suspicion may survive modest price differences across platforms.
- Duplicate heuristics should not rely on apartment number or room-number matching because the current list-page data is insufficiently consistent for that rule.
- `meta` should expose `raw_count`, `possible_duplicate_count`, `returned_count`, and `truncated`.
- When all requested platforms execute without platform error but no filtered listings remain, top-level `status` should be `no_results`.
- When one or more platforms succeed and one or more platforms error, top-level `status` should be `partial_success`.
- Search calls should not write artifacts by default in this wave.
- The diagnose/probe tool is not part of this implementation wave, but future alignment should reuse the same general vocabulary where practical.
- Detail lookup remains a follow-up feature and should be designed later to accept `listing_ref`.

### Major modules to build or modify

- Search tool contract layer
  - Owns public MCP naming, input shape, and response envelope.
- Search orchestration service
  - Owns default platform selection, parameter validation, platform fan-out, and top-level status aggregation.
- Platform status mapper
  - Owns per-platform contract normalization, including `status`, `error_type`, `error_message`, and `filter_mode`.
- Listing reference and duplicate annotation module
  - Owns `listing_ref` creation, possible-duplicate grouping, duplicate markers, and primary-versus-duplicate ordering.
- Response envelope mapper
  - Owns translation from service results into the final `meta/data` machine contract.

These modules should stay deep and testable. In particular, duplicate annotation and response mapping should not be smeared across the MCP entrypoint, service orchestration, and tests as shallow inline conditionals.

## Testing Decisions

- Good tests should verify externally visible behavior rather than internal implementation details. The important assertions are contract shape, statuses, counts, ordering, validation behavior, and duplicate annotations, not the exact sequence of helper calls.
- The search orchestration service should be tested because it now owns the most important business semantics: default platforms, validation, top-level status aggregation, and empty-result handling.
- The listing reference and duplicate annotation module should be tested in isolation because it is a deep behavior module with the highest risk of subtle regressions.
- The response envelope mapping should be tested so the public MCP contract cannot silently drift.
- Platform normalization and validation behavior should be tested so omitted `platforms`, explicit subsets, `page`, and `limit` semantics remain stable.
- Existing service-focused tests that use fake adapters are prior art for orchestration-level behavior.
- Existing platform normalization tests are prior art for platform default and validation behavior.
- Existing adapter fixture tests are prior art for verifying normalized listing fields from HTML samples, but first-wave contract tests should stay focused on normalized outputs rather than parser internals.
- Search-artifact behavior should be tested only as far as confirming that normal search does not write artifacts in this wave.

## Out of Scope

- Diagnose/probe tool contract redesign
- Formal baseline MCP exposure
- Detail lookup for a selected listing
- Automatic detail enrichment during search
- Natural-language query parsing
- Long-term listing history, monitoring, scheduled collection, or reminders
- Browser automation for login or cookie refresh
- Hard duplicate merging or canonical listing collapse
- Apartment-number-dependent duplicate logic
- Public sort controls in the MCP search interface
- A standalone schema-version field in the response
- Search-time artifact generation by default

## Further Notes

- This PRD synthesizes the `grill-me` decisions already made in conversation and is intended to be implementation-ready without another discovery interview.
- The recommended implementation order is to stabilize the main search contract first, then align the diagnose tool to the same vocabulary in a follow-up wave.
- The new contract is intentionally conservative: it favors honesty and low complexity over pretending to support richer automation than the current platform behavior can sustain.
