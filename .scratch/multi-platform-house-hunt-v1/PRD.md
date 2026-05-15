# 00 Master PRD For 01-06

Status: ready-for-agent

## Problem Statement

The current HouseScraper MCP repository already proves that a local MCP service can pull live house listings from `beike`, `lianjia`, and `anjuke`, but the product surface is still fragmented. Baseline regression exists, broad search exists, and individual parser/test pieces exist, yet the overall house-hunting workflow is not fully shaped into a coherent agent-facing system.

From the user's perspective, the repo should become a reliable local house-hunting toolchain for an outer agent. The agent should be able to:

- verify that supported platforms are still usable on the current machine,
- search broadly across platforms using stable inputs and outputs,
- narrow results by keyword or community when broad filtering is not enough,
- understand when multiple results are probably the same listing,
- drill into a selected listing for price and metadata verification,
- export shortlisted candidates for offline comparison.

Today those capabilities are uneven:

- baseline and regression are already largely usable,
- broad search works but the contract is still too script-like and under-specified for long-term agent use,
- keyword search is not exposed,
- duplicate handling is not implemented,
- listing detail is not exposed from the local MCP surface,
- candidate export is not wired into this repo's workflow.

The product problem is therefore not just "add more features." It is to turn the repo into a coherent multi-platform house-hunting workflow where the main search path is honest, machine-friendly, and extensible, while later layers such as keyword search, detail verification, and export build on the same contract instead of becoming isolated side features.

## Solution

Build `Multi-Platform House Hunt V1` as a staged local MCP workflow with six linked workstreams:

1. live baseline and regression for platform health,
2. agent-friendly search contract for the main broad-search path,
3. keyword and community search for narrower discovery,
4. cross-platform aggregation and duplicate reasoning,
5. listing detail and price verification for spot checks,
6. candidate export for offline comparison.

The first major product decision is that this remains an `Agent 工具层` local MCP service rather than a direct consumer app. The service should stay conservative about anti-bot risk, structured in its inputs, explicit in its outputs, and mostly stateless in its day-to-day operation. The outer agent owns interpretation and analysis. The MCP owns reliable retrieval, normalization, status, and evidence.

The implementation should proceed as a layered product roadmap rather than six isolated tickets:

- `01` provides confidence that the supported platforms still work on the current machine.
- `06` hardens the main search contract so later features inherit a stable interface.
- `02` and `03` deepen search usefulness by supporting narrower targeting and duplicate reasoning.
- `04` adds verification depth once search results can be referenced stably.
- `05` adds a practical endpoint for users who want to compare candidates outside the MCP client.

This creates a full workflow: health check, broad search, targeted narrowing, duplicate-aware review, spot-check verification, and shortlist export.

## User Stories

1. As a user operating through an outer agent, I want to verify that all supported platforms still return live listings on my machine, so that I know whether search results are trustworthy before I act on them.
2. As a user operating through an outer agent, I want a single baseline command that checks `beike`, `lianjia`, and `anjuke`, so that I can catch parser, cookie, or anti-bot regressions quickly.
3. As a user operating through an outer agent, I want baseline output saved for later inspection, so that I can compare behavior across runs.
4. As an outer agent, I want to call one broad-search tool across multiple platforms, so that I can gather candidate listings without stitching together separate platform-specific calls.
5. As an outer agent, I want omitted `platforms` input to search all supported platforms, so that I do not accidentally miss results because of a narrow implicit default.
6. As an outer agent, I want explicitly provided `platforms` input to limit the query to the chosen sources, so that I can trade breadth for speed or stability when needed.
7. As an outer agent, I want structured search inputs, so that I can deterministically construct queries from user intent.
8. As an outer agent, I want the main search tool to stay single-page and bounded, so that I can reason about anti-bot risk and execution cost.
9. As an outer agent, I want top-level search status to distinguish success, partial success, no results, and hard failure, so that I do not confuse empty data with broken behavior.
10. As an outer agent, I want each platform to report its own status and failure details, so that I can reason about source-specific reliability.
11. As an outer agent, I want filter-mode visibility, so that I can tell when results came from native upstream filtering versus local post-filtering.
12. As an outer agent, I want search responses to be cleanly split into metadata and business data, so that parsing stays stable as the contract evolves.
13. As an outer agent, I want stable listing references, so that I can refer to a specific listing in later workflows without guessing from raw URLs.
14. As an outer agent, I want keyword and community-oriented search, so that I can look for a known project or neighborhood instead of only doing city-wide screening.
15. As an outer agent, I want search results to make keyword matching visible, so that I know why a result was included.
16. As an outer agent, I want the service to recognize likely duplicate listings across platforms, so that I do not over-count the same home when comparing inventory.
17. As an outer agent, I want duplicate handling to stay cautious and advisory, so that the service does not silently merge distinct listings.
18. As an outer agent, I want duplicate markers and grouping references, so that I can suppress or down-rank repeats in later analysis.
19. As an outer agent, I want likely duplicates pushed behind primary results, so that the most useful candidates appear first.
20. As an outer agent, I want detail lookup for a selected listing, so that I can verify title, price, unit price, community, and other important fields against the source page.
21. As an outer agent, I want listing detail errors to surface clearly by platform, so that I can tell whether verification failed because of cookies, anti-bot, or parsing.
22. As an outer agent, I want a shortlist export workflow, so that I can hand results to a spreadsheet, note-taking tool, or human review process.
23. As an outer agent, I want exports to include enough fields for side-by-side comparison, so that I can compare price, area, layout, community, source, and verification context.
24. As a maintainer, I want the repo to preserve a local CLI for smoke tests and manual verification, so that MCP integration is not the only way to validate behavior.
25. As a maintainer, I want the main search contract to be stable enough that later features can reuse it, so that keyword search, detail lookup, and export do not each invent their own output model.
26. As a maintainer, I want deep modules around duplicate reasoning and contract mapping, so that the most complex logic can evolve safely behind small interfaces.
27. As a maintainer, I want tests to focus on externally visible behavior, so that refactors can improve internals without breaking the specification.
28. As a maintainer, I want the repo to remain conservative about browser automation and anti-bot risk, so that maintenance cost does not explode.
29. As a user, I want the toolchain to remain local and machine-specific, so that my existing browser cookies and real-session environment can be used without building a remote service.
30. As a user, I want the overall workflow to support both broad search and targeted verification, so that I can move from exploration to confident candidate comparison within one repo.

## Implementation Decisions

- The feature set for `01-06` belongs to one parent product line: `Multi-Platform House Hunt V1`.
- This product line remains a local MCP service and local CLI workflow. It is not a hosted backend and not a direct end-user GUI.
- `beike`, `lianjia`, and `anjuke` are the supported first-wave platforms.
- The system remains conservative about anti-bot behavior. Low-risk broad retrieval is preferred over deeper but more brittle upstream filtering when necessary.
- The broad-search path is the center of gravity for the product. Other capabilities should extend or consume that path rather than bypass it.
- `01 Live Baseline And Regression` is part of the product, but it is already substantially complete and now acts as an operational safety net for all later work.
- `06 Agent-Friendly Search Contract` is the main architectural foundation for the remaining unfinished work. It standardizes the outer-agent interface for broad search and should be treated as a prerequisite for product polish in `02`, `03`, and `04`.
- Search inputs should remain structured rather than natural-language-driven within the MCP itself.
- The first-wave broad-search surface should stay bounded and honest: single page per call, bounded page and limit, no unsupported public sorting semantics.
- Search outputs should move toward a stable machine contract with:
  - explicit statuses,
  - clear metadata,
  - platform-level outcomes,
  - stable listing references,
  - duplicate-aware annotations.
- `02 Community Keyword Search` should extend the search path rather than create a parallel search tool. Keyword-oriented narrowing is a search capability, not a separate subsystem with independent semantics.
- `03 Cross-Platform Aggregation And Dedup` should also extend the main search path. Duplicate reasoning belongs in normalized search results, not as a disconnected post-processing export step.
- Duplicate handling in V1 should stay advisory. The service should mark likely duplicates and preserve source visibility rather than aggressively canonicalize listings.
- `04 Listing Detail And Price Check` should consume stable listing references from the main search workflow. Detail lookup should be an on-demand deepening step after broad screening, not a mandatory search-time expansion.
- `05 Candidate Export` should consume the normalized, duplicate-aware, optionally verified candidate model rather than inventing a separate export-only schema.
- Export should support simple formats such as JSON or CSV, with fields chosen for manual house-hunting comparison rather than generic raw dumps.
- Browser login and cookie refresh remain passive dependencies. The repo should read and reuse available browser cookies rather than become a browser automation system.
- Search, diagnosis, detail lookup, and export should all be explainable and verifiable from the local CLI, even when their main intended consumer is an MCP client.

### Product modules implied by 01-06

- Platform health and regression module
  - Owns baseline workflows, health summaries, and saved regression artifacts.
- Search contract module
  - Owns public search naming, bounded inputs, explicit status semantics, and metadata/data envelopes.
- Search narrowing module
  - Owns keyword/community matching and match visibility in results.
- Duplicate reasoning module
  - Owns cross-platform identity heuristics, duplicate annotations, and result ordering.
- Listing verification module
  - Owns selected-listing detail lookup and source-page verification semantics.
- Candidate export module
  - Owns shortlist serialization for offline comparison.

These should be treated as deep product modules rather than scattered layers of conditionals. The more complex behaviors, especially duplicate reasoning and search-contract mapping, should live behind small and well-tested interfaces.

## Testing Decisions

- Good tests should verify public behavior through the MCP-facing or CLI-facing contract, not private helper choreography.
- `01` should continue to be covered by service and CLI-oriented regression tests that prove baseline reports and per-platform summaries behave as documented.
- `06` should receive the strongest contract tests because it defines the main interface that later work depends on.
- `02` should be tested through observable keyword search behavior:
  - accepted keyword input,
  - platform-aware matching,
  - clear match visibility in returned results.
- `03` should be tested through observable duplicate outcomes:
  - multi-platform merged search,
  - source visibility preservation,
  - duplicate markers,
  - duplicate ordering,
  - duplicate-aware counts.
- `04` should be tested through observable detail lookup behavior:
  - fetching a selected listing,
  - returning normalized verification fields,
  - surfacing per-platform access or anti-bot errors clearly.
- `05` should be tested through observable export behavior:
  - generating a file,
  - including comparison-ready fields,
  - preserving merged and verification-aware data.
- Existing service tests that use fake adapters are prior art for orchestration-level behavior.
- Existing parser fixture tests are prior art for normalized field extraction, but future tests for `02-06` should continue to emphasize contract behavior over parser internals.
- Regression tests should remain easy to run locally because this repo depends on real browser/cookie conditions that can drift over time.

## Out of Scope

- Building a hosted or remote service version of HouseScraper MCP
- Building a consumer-facing UI or web app
- Fully automated login flows or browser control for supported platforms
- Large-scale crawling, scheduled warehousing, or historical monitoring as part of V1
- Aggressive hard-merging of listings into a single canonical entity
- Advanced investment analysis or recommendation logic inside the MCP layer
- Natural-language understanding inside the MCP layer for first-wave search
- Expanding beyond the initial supported platform set in this PRD

## Further Notes

- This master PRD is intentionally broader than the standalone `agent-friendly-search-contract-v1` PRD. That smaller PRD should be treated as a focused child PRD for `06`, while this document acts as the parent planning document for the whole `01-06` roadmap.
- Current progress snapshot:
  - `01` is effectively complete.
  - `03` is partially complete because multi-platform merged search already exists, but duplicate reasoning is not done.
  - `02`, `04`, and `05` are not implemented on the local MCP surface yet.
  - `06` is fully specified but not yet implemented.
- Recommended product order from here:
  1. finish `06` to stabilize the broad-search contract,
  2. fold duplicate reasoning into that contract for `03`,
  3. add keyword/community narrowing for `02`,
  4. add selected-listing verification for `04`,
  5. finish shortlist export for `05`.
