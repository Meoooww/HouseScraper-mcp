# HouseScraper MCP Context

## Domain

- **Platform Probe**: a lightweight check that verifies whether a platform can return live listings on the current machine.
- **Listing Search**: a multi-platform retrieval workflow that returns normalized listing data for agent-side screening.
- **Listing Reference**: a stable identifier in the format `<platform>:<id>` used to chain workflows safely.
- **Duplicate Hint**: an advisory marker (`duplicate_id`) indicating likely cross-platform duplicates without hard merge.
- **Detail Check**: a targeted lookup for one listing reference to verify price and metadata against the source page.
- **Baseline Report**: a local artifact combining probe and filtered-search checks for regression tracking.

## Module Map

- **SearchFiltering module** (`src/housescraper_mcp/search_filtering.py`)
  - Interface: build and apply search filters, including local post-filtering rules.
  - Leverage: callers do not need to know platform-specific anti-bot fallback logic.
- **SearchContract module** (`src/housescraper_mcp/search_contract.py`)
  - Interface: shape search/detail contract payloads, listing reference handling, keyword match visibility, and duplicate hints.
  - Locality: response semantics are concentrated in one place instead of spread across orchestration code.
- **HouseScraperService module** (`src/housescraper_mcp/service.py`)
  - Interface: orchestration entry points (`probe`, `search`, `detail`, `baseline`).
  - Adapter seams: platform adapters are injected through `adapter_factories`.
  - Implementation: delegates filtering and envelope construction to deep modules and keeps orchestration shallow.

## Current Seams

- **Probe seam**: platform execution + status summaries.
- **Search seam**: retrieval orchestration separated from filter policy and response contract shaping.
- **Detail seam**: listing reference resolution and platform-level error normalization (`error_type`, `error_message`).
