"""Replay address search over an Excel file and write a quality report."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd

import config
from handlers.excel_handler import ExcelHandler
from models.address import Address
from search.hybrid_search import HybridSearch


PLACEHOLDER_INDEXES = {"", "*", "00000", "01000"}
REPORT_COLUMNS = [
    "row_number",
    "mode",
    "total_found",
    "issue_tags",
    "input_index",
    "query_index_used",
    "input_region",
    "input_district",
    "input_city",
    "input_street",
    "input_building",
    "processed_city",
    "processed_street",
    "processed_building",
    "auto_index",
    "auto_confidence",
    "top1_index",
    "top1_confidence",
    "top1_city",
    "top1_street",
    "top1_buildings",
    "top2_index",
    "top2_confidence",
    "top2_city",
    "top2_street",
    "top3_index",
    "top3_confidence",
    "top3_city",
    "top3_street",
]


def load_mapping(mapping_arg: Optional[str]) -> Dict[str, List[int]]:
    if not mapping_arg:
        mapping_path = Path(config.COLUMN_MAPPINGS_DIR) / "Vodafon.json"
    else:
        candidate = Path(mapping_arg)
        if candidate.exists():
            mapping_path = candidate
        else:
            mapping_path = Path(config.COLUMN_MAPPINGS_DIR) / mapping_arg
            if mapping_path.suffix.lower() != ".json":
                mapping_path = mapping_path.with_suffix(".json")

    if not mapping_path.exists():
        raise FileNotFoundError(f"Mapping file not found: {mapping_path}")

    with mapping_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def clone_address(address: Address) -> Address:
    return Address(**address.to_dict())


def normalize_report_index(search: HybridSearch, index: str) -> str:
    return search._normalize_query_index(index)


def compact_result(result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not result:
        return {
            "index": "",
            "confidence": "",
            "city": "",
            "street": "",
            "buildings": "",
        }

    return {
        "index": result.get("index", ""),
        "confidence": result.get("confidence", ""),
        "city": result.get("city_ua") or result.get("city", ""),
        "street": result.get("street_ua") or result.get("street", ""),
        "buildings": result.get("buildings", ""),
    }


def build_issue_tags(
    original: Address,
    processed: Address,
    result: Dict[str, Any],
    search: HybridSearch,
) -> List[str]:
    tags = []
    manual_results = result.get("manual", [])
    auto_result = result.get("auto")
    top_result = manual_results[0] if manual_results else auto_result
    query_index = normalize_report_index(search, original.index)

    if str(original.index or "").strip() in PLACEHOLDER_INDEXES:
        tags.append("placeholder_index")
    if original.street and original.building:
        if search.normalizer.normalize_text(original.street) == search.normalizer.normalize_text(original.building):
            tags.append("street_building_same_source")
    if processed.building and processed.building != original.building:
        tags.append("building_extracted")
    if processed.street != original.street:
        tags.append("street_cleaned")
    if result.get("search_mode") == "none" or result.get("total_found", 0) == 0:
        tags.append("no_candidates")
    if result.get("search_mode") == "manual":
        tags.append("manual_review")
    if result.get("total_found", 0) >= 50:
        tags.append("many_candidates")
    if top_result and top_result.get("is_general"):
        tags.append("general_index_top")
    if top_result and int(top_result.get("confidence") or 0) < 90:
        tags.append("low_top_confidence")
    if query_index and top_result:
        top_index = str(top_result.get("index") or "").strip().lstrip("0")
        if top_index and top_index != query_index:
            tags.append("input_index_differs_from_top")

    high_confidence = [
        r for r in manual_results
        if int(r.get("confidence") or 0) >= config.AUTO_MATCH_CONFIDENCE
    ]
    if len(high_confidence) > 1:
        tags.append("ambiguous_high_confidence")

    return tags


def analyze_row(
    row_index: int,
    address: Address,
    search: HybridSearch,
    max_results: int,
) -> Dict[str, Any]:
    original = clone_address(address)
    processed = clone_address(address)
    result = search.search_with_confidence(processed, max_results=max_results)
    manual_results = result.get("manual", [])
    auto_result = result.get("auto")
    top = [compact_result(r) for r in manual_results[:3]]
    while len(top) < 3:
        top.append(compact_result(None))

    auto = compact_result(auto_result)
    tags = build_issue_tags(original, processed, result, search)

    return {
        "row_number": row_index + 1,
        "mode": result.get("search_mode", "none"),
        "total_found": result.get("total_found", 0),
        "issue_tags": ",".join(tags),
        "input_index": original.index,
        "query_index_used": normalize_report_index(search, original.index),
        "input_region": original.region,
        "input_district": original.district,
        "input_city": original.city,
        "input_street": original.street,
        "input_building": original.building,
        "processed_city": processed.city,
        "processed_street": processed.street,
        "processed_building": processed.building,
        "auto_index": auto["index"],
        "auto_confidence": auto["confidence"],
        "top1_index": top[0]["index"],
        "top1_confidence": top[0]["confidence"],
        "top1_city": top[0]["city"],
        "top1_street": top[0]["street"],
        "top1_buildings": top[0]["buildings"],
        "top2_index": top[1]["index"],
        "top2_confidence": top[1]["confidence"],
        "top2_city": top[1]["city"],
        "top2_street": top[1]["street"],
        "top3_index": top[2]["index"],
        "top3_confidence": top[2]["confidence"],
        "top3_city": top[2]["city"],
        "top3_street": top[2]["street"],
    }


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    modes = Counter(row["mode"] for row in rows)
    tags = Counter()
    for row in rows:
        tags.update(tag for tag in row["issue_tags"].split(",") if tag)

    return {
        "rows_analyzed": len(rows),
        "modes": dict(modes),
        "issue_tags": dict(tags.most_common()),
    }


def default_output_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(config.LOGS_DIR) / f"search_quality_report_{timestamp}.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay postal index search over an Excel file and write a CSV quality report."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=r"C:\Users\Mykhaillyk Yurii\Downloads\Telegram Desktop\all.xlsx",
        help="Excel file to analyze.",
    )
    parser.add_argument(
        "--mapping",
        default=None,
        help="Mapping JSON path or saved mapping name. Defaults to column_mappings/Vodafon.json.",
    )
    parser.add_argument("--output", default=None, help="CSV report path.")
    parser.add_argument("--start", type=int, default=1, help="1-based first row to analyze.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum rows to analyze. Use 0 for all rows.")
    parser.add_argument("--max-results", type=int, default=20, help="Manual candidates to keep per row.")
    parser.add_argument("--verbose", action="store_true", help="Show detailed search logs while replaying.")
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Do not apply the same column filter that the UI applies after mapping.",
    )
    return parser.parse_args()


def configure_console_logging(verbose: bool) -> None:
    if verbose:
        return

    logger = logging.getLogger("AddressMatcher")
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            handler.setLevel(logging.CRITICAL)


def quiet_call(verbose: bool, func, *args, **kwargs):
    if verbose:
        return func(*args, **kwargs)

    with contextlib.redirect_stdout(io.StringIO()):
        return func(*args, **kwargs)


def main() -> int:
    args = parse_args()
    configure_console_logging(args.verbose)
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    mapping = load_mapping(args.mapping)
    excel = ExcelHandler()
    configure_console_logging(args.verbose)
    quiet_call(args.verbose, excel.load_file, str(input_path))
    quiet_call(args.verbose, excel.set_column_mapping, mapping)
    if not args.no_filter:
        quiet_call(args.verbose, excel.apply_column_filter)

    search = HybridSearch(lazy_load=True)
    configure_console_logging(args.verbose)
    quiet_call(args.verbose, search._ensure_loaded)

    start_idx = max(args.start - 1, 0)
    end_idx = len(excel.df) if args.limit == 0 else min(len(excel.df), start_idx + args.limit)
    rows = []

    for row_idx in range(start_idx, end_idx):
        address = excel.get_address_from_row(row_idx)
        rows.append(quiet_call(args.verbose, analyze_row, row_idx, address, search, args.max_results))
        if len(rows) % 25 == 0:
            print(f"Analyzed {len(rows)} rows...", flush=True)

    output_path = Path(args.output) if args.output else default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=REPORT_COLUMNS).to_csv(output_path, index=False, encoding="utf-8-sig")

    summary = summarize(rows)
    summary_path = output_path.with_suffix(".summary.json")
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Report: {output_path}")
    print(f"Summary: {summary_path}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
