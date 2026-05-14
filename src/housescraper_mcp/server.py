"""MCP server entrypoint."""

from __future__ import annotations

import os
from typing import Literal

from mcp.server.fastmcp import FastMCP

from housescraper_mcp.service import HouseScraperService, build_search_filter

mcp = FastMCP("HouseScraper MCP", json_response=True)
service = HouseScraperService()


@mcp.tool()
async def probe_sources(
    city: str = "上海",
    platforms: list[str] | None = None,
    district: str = "",
    min_price: float | None = None,
    max_price: float | None = None,
    min_area: float | None = None,
    max_area: float | None = None,
    layout: str = "",
    listing_type: Literal["buy", "rent"] = "buy",
    page: int = 1,
    sample_limit: int = 3,
) -> dict:
    """Probe whether the configured sources can return house listings."""

    filters = build_search_filter(
        city=city,
        district=district,
        min_price=min_price,
        max_price=max_price,
        min_area=min_area,
        max_area=max_area,
        layout=layout,
        listing_type=listing_type,
        page=page,
    )
    return await service.probe(filters, platforms=platforms, sample_limit=sample_limit)


@mcp.tool()
async def search_listings(
    city: str = "上海",
    platforms: list[str] | None = None,
    district: str = "",
    min_price: float | None = None,
    max_price: float | None = None,
    min_area: float | None = None,
    max_area: float | None = None,
    layout: str = "",
    listing_type: Literal["buy", "rent"] = "buy",
    page: int = 1,
    limit: int = 20,
    sort_by: str = "default",
) -> dict:
    """Search house listings and return normalized multi-platform results."""

    filters = build_search_filter(
        city=city,
        district=district,
        min_price=min_price,
        max_price=max_price,
        min_area=min_area,
        max_area=max_area,
        layout=layout,
        listing_type=listing_type,
        page=page,
        sort_by=sort_by,
    )
    return await service.search(filters, platforms=platforms, limit=limit)


def main() -> None:
    """Run the server, defaulting to stdio transport for local MCP clients."""

    transport = os.environ.get("HOUSESCRAPER_MCP_TRANSPORT")
    if transport:
        mcp.run(transport=transport)
        return
    mcp.run()


if __name__ == "__main__":
    main()
