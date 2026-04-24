from __future__ import annotations

import argparse
from pathlib import Path
import sys

from ukrposhta_address_matcher.config import Settings
from ukrposhta_address_matcher.review_ui import run_review_ui
from ukrposhta_address_matcher.service import process_registry, refresh_cached_entries, warm_cache_for_registry


def _resolve_cache_path(raw_cache_path: str | None, settings: Settings) -> str:
    return raw_cache_path or settings.classifier_cache_path


def _resolve_match_workers(raw_workers: int | None, settings: Settings) -> int:
    if raw_workers is None:
        return settings.classifier_match_workers
    return max(1, raw_workers)


def _resolve_review_data_dir(raw_data_dir: str | None) -> str:
    if raw_data_dir:
        return raw_data_dir
    return str(Path(".review-ui-data").resolve())


def _format_stats(stats: dict[str, object]) -> str:
    final_cache = stats["final_cache"]
    city_cache = stats["city_cache"]
    street_cache = stats["street_cache"]
    street_house_cache = stats["street_house_cache"]
    response_cache = stats["response_cache"]
    return (
        f"Stats: unique={stats['unique_requests']}, http={stats['classifier_http_requests']}, "
        f"final={final_cache['hits']}/{final_cache['lookups']} ({final_cache['hit_rate_percent']}%), "
        f"city={city_cache['hits']}/{city_cache['lookups']} ({city_cache['hit_rate_percent']}%), "
        f"street={street_cache['hits']}/{street_cache['lookups']} ({street_cache['hit_rate_percent']}%), "
        f"houses={street_house_cache['hits']}/{street_house_cache['lookups']} ({street_house_cache['hit_rate_percent']}%), "
        f"response={response_cache['hits']}/{response_cache['lookups']} ({response_cache['hit_rate_percent']}%)"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ukrposhta-address-matcher")
    subparsers = parser.add_subparsers(dest="command", required=True)

    match_parser = subparsers.add_parser("match-registry", help="Transform a registry TXT file.")
    match_parser.add_argument("input_path")
    match_parser.add_argument("output_path")
    match_parser.add_argument("--report", required=True, dest="report_path")
    match_parser.add_argument("--cache", dest="cache_path")
    match_parser.add_argument("--workers", type=int, dest="match_workers")
    match_parser.add_argument("--env-file", default=".env")
    match_parser.add_argument("--no-ai", action="store_true")

    warm_parser = subparsers.add_parser("warm-cache", help="Warm classifier cache using a registry TXT file.")
    warm_parser.add_argument("input_path")
    warm_parser.add_argument("--cache", dest="cache_path")
    warm_parser.add_argument("--workers", type=int, dest="match_workers")
    warm_parser.add_argument("--env-file", default=".env")
    warm_parser.add_argument("--no-ai", action="store_true")

    refresh_parser = subparsers.add_parser("refresh-cache", help="Refresh cached classifier responses.")
    refresh_parser.add_argument("--cache", dest="cache_path")
    refresh_parser.add_argument("--env-file", default=".env")

    review_parser = subparsers.add_parser("review-ui", help="Run local review UI for human-in-the-loop processing.")
    review_parser.add_argument("--host", default="127.0.0.1")
    review_parser.add_argument("--port", type=int, default=8765)
    review_parser.add_argument("--data-dir", dest="data_dir")
    review_parser.add_argument("--cache", dest="cache_path")
    review_parser.add_argument("--workers", type=int, dest="match_workers")
    review_parser.add_argument("--env-file", default=".env")
    review_parser.add_argument("--no-ai", action="store_true")
    review_parser.add_argument("--no-open-browser", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings.load(args.env_file)

    if not settings.ukrposhta_bearer_token:
        parser.error("UKRPOSHTA_BEARER_TOKEN is required in .env or environment.")

    cache_path = _resolve_cache_path(getattr(args, "cache_path", None), settings)
    match_workers = _resolve_match_workers(getattr(args, "match_workers", None), settings)

    if args.command == "match-registry":
        summary = process_registry(
            input_path=args.input_path,
            output_path=args.output_path,
            report_path=args.report_path,
            cache_path=cache_path,
            settings=settings,
            use_ai=not args.no_ai,
            match_workers=match_workers,
        )
        print(f"Processed {summary['rows']} rows. Review rows: {summary['review_rows']}.")
        print(
            f"Postcode unresolved rows: {summary['postcode_unresolved_rows']}. "
            f"Report: {summary['postcode_unresolved_report']}"
        )
        print(_format_stats(summary["stats"]))
        return 0

    if args.command == "warm-cache":
        summary = warm_cache_for_registry(
            input_path=args.input_path,
            cache_path=cache_path,
            settings=settings,
            use_ai=not args.no_ai,
            match_workers=match_workers,
        )
        print(
            f"Warmed cache for {summary['rows']} rows "
            f"({summary['unique_requests']} unique requests). Review rows: {summary['review_rows']}. "
            f"Postcode unresolved rows: {summary['postcode_unresolved_rows']}."
        )
        print(_format_stats(summary["stats"]))
        return 0

    if args.command == "refresh-cache":
        refreshed = refresh_cached_entries(cache_path, settings=settings)
        print(f"Refreshed {refreshed} cached classifier responses.")
        return 0

    if args.command == "review-ui":
        run_review_ui(
            host=args.host,
            port=args.port,
            data_dir=_resolve_review_data_dir(args.data_dir),
            cache_path=cache_path,
            settings=settings,
            use_ai=not args.no_ai,
            match_workers=match_workers,
            open_browser=not args.no_open_browser,
        )
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def match_registry_main(argv: list[str] | None = None) -> int:
    return main(["match-registry", *(argv or sys.argv[1:])])


def refresh_cache_main(argv: list[str] | None = None) -> int:
    return main(["refresh-cache", *(argv or sys.argv[1:])])


def review_ui_main(argv: list[str] | None = None) -> int:
    return main(["review-ui", *(argv or sys.argv[1:])])
