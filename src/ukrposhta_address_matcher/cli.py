from __future__ import annotations

import argparse
from pathlib import Path
import sys

from ukrposhta_address_matcher.config import Settings
from ukrposhta_address_matcher.service import process_registry, refresh_cached_entries


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ukrposhta-address-matcher")
    subparsers = parser.add_subparsers(dest="command", required=True)

    match_parser = subparsers.add_parser("match-registry", help="Transform a registry TXT file.")
    match_parser.add_argument("input_path")
    match_parser.add_argument("output_path")
    match_parser.add_argument("--report", required=True, dest="report_path")
    match_parser.add_argument("--cache", required=True, dest="cache_path")
    match_parser.add_argument("--env-file", default=".env")
    match_parser.add_argument("--no-ai", action="store_true")

    refresh_parser = subparsers.add_parser("refresh-cache", help="Refresh cached classifier responses.")
    refresh_parser.add_argument("--cache", required=True, dest="cache_path")
    refresh_parser.add_argument("--env-file", default=".env")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings.load(args.env_file)

    if not settings.ukrposhta_bearer_token:
        parser.error("UKRPOSHTA_BEARER_TOKEN is required in .env or environment.")

    if args.command == "match-registry":
        summary = process_registry(
            input_path=args.input_path,
            output_path=args.output_path,
            report_path=args.report_path,
            cache_path=args.cache_path,
            settings=settings,
            use_ai=not args.no_ai,
        )
        print(f"Processed {summary['rows']} rows. Review rows: {summary['review_rows']}.")
        return 0

    if args.command == "refresh-cache":
        refreshed = refresh_cached_entries(args.cache_path, settings=settings)
        print(f"Refreshed {refreshed} cached classifier responses.")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2

