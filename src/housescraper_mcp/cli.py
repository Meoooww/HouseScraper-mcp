"""Small local CLI for smoke-testing the MCP service logic."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from typing import Any

from housescraper_mcp.search_filtering import build_search_filter
from housescraper_mcp.service import HouseScraperService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local smoke-test CLI for HouseScraper MCP")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_arguments(target: argparse.ArgumentParser) -> None:
        target.add_argument("--city", default="上海")
        target.add_argument("--platform", action="append", dest="platforms", default=[])
        target.add_argument("--keyword", default="")
        target.add_argument("--district", default="")
        target.add_argument("--min-price", type=float, dest="min_price")
        target.add_argument("--max-price", type=float, dest="max_price")
        target.add_argument("--min-area", type=float, dest="min_area")
        target.add_argument("--max-area", type=float, dest="max_area")
        target.add_argument("--layout", default="")
        target.add_argument("--layouts", nargs="+")
        target.add_argument("--max-unit-price", type=float, dest="max_unit_price")
        target.add_argument("--detail-verify-limit", type=int, dest="detail_verify_limit", default=0)
        target.add_argument("--listing-type", choices=["buy", "rent"], default="buy")
        target.add_argument("--page", type=int, default=1)

    probe = subparsers.add_parser("probe", help="Probe platform availability")
    add_common_arguments(probe)
    probe.add_argument("--sample-limit", type=int, default=3)

    search = subparsers.add_parser("search", help="Search listings")
    add_common_arguments(search)
    search.add_argument("--limit", type=int, default=20)

    detail = subparsers.add_parser("detail", help="Fetch detail for one listing reference")
    detail.add_argument("--listing-ref", required=True, dest="listing_ref")

    baseline = subparsers.add_parser("baseline", help="Run live multi-platform baseline")
    baseline.add_argument("--city", default="上海")
    baseline.add_argument("--platform", action="append", dest="platforms", default=[])
    baseline.add_argument("--max-price", type=float, dest="max_price", default=500.0)
    baseline.add_argument("--layout", default="2室")
    baseline.add_argument("--listing-type", choices=["buy", "rent"], default="buy")
    baseline.add_argument("--page", type=int, default=1)
    baseline.add_argument("--sample-limit", type=int, default=3)
    baseline.add_argument("--search-limit", type=int, default=5)

    return parser


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    service = HouseScraperService()
    if args.command == "baseline":
        return await service.baseline(
            city=args.city,
            platforms=args.platforms or None,
            max_price=args.max_price,
            layout=args.layout,
            listing_type=args.listing_type,
            page=args.page,
            sample_limit=args.sample_limit,
            search_limit=args.search_limit,
        )
    if args.command == "detail":
        return await service.detail(args.listing_ref)

    filters = build_search_filter(
        city=args.city,
        district=args.district,
        min_price=args.min_price,
        max_price=args.max_price,
        min_area=args.min_area,
        max_area=args.max_area,
        layout=args.layout,
        layouts=args.layouts,
        max_unit_price=args.max_unit_price,
        detail_verify_limit=args.detail_verify_limit,
        listing_type=args.listing_type,
        page=args.page,
        keywords=args.keyword,
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
