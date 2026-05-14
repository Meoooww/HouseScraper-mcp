"""Small local CLI for smoke-testing the MCP service logic."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from typing import Any

from housescraper_mcp.service import HouseScraperService, build_search_filter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local smoke-test CLI for HouseScraper MCP")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_arguments(target: argparse.ArgumentParser) -> None:
        target.add_argument("--city", default="上海")
        target.add_argument("--platform", action="append", dest="platforms", default=[])
        target.add_argument("--district", default="")
        target.add_argument("--min-price", type=float, dest="min_price")
        target.add_argument("--max-price", type=float, dest="max_price")
        target.add_argument("--min-area", type=float, dest="min_area")
        target.add_argument("--max-area", type=float, dest="max_area")
        target.add_argument("--layout", default="")
        target.add_argument("--listing-type", choices=["buy", "rent"], default="buy")
        target.add_argument("--page", type=int, default=1)

    probe = subparsers.add_parser("probe", help="Probe platform availability")
    add_common_arguments(probe)
    probe.add_argument("--sample-limit", type=int, default=3)

    search = subparsers.add_parser("search", help="Search listings")
    add_common_arguments(search)
    search.add_argument("--limit", type=int, default=20)
    search.add_argument("--sort-by", default="default")

    return parser


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    service = HouseScraperService()
    filters = build_search_filter(
        city=args.city,
        district=args.district,
        min_price=args.min_price,
        max_price=args.max_price,
        min_area=args.min_area,
        max_area=args.max_area,
        layout=args.layout,
        listing_type=args.listing_type,
        page=args.page,
        sort_by=getattr(args, "sort_by", "default"),
    )
    platforms = args.platforms or None
    if args.command == "probe":
        return await service.probe(filters, platforms=platforms, sample_limit=args.sample_limit)
    return await service.search(filters, platforms=platforms, limit=args.limit)


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = asyncio.run(_run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
