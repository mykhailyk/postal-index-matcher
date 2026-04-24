from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from ukrposhta_address_matcher.ai import GeminiFallbackClient
from ukrposhta_address_matcher.cache import CacheStore
from ukrposhta_address_matcher.classifier import UkrposhtaClassifierClient
from ukrposhta_address_matcher.config import Settings
from ukrposhta_address_matcher.matcher import AddressMatcher
from ukrposhta_address_matcher.models import MatchResult
from ukrposhta_address_matcher.registry import (
    read_registry,
    write_postcode_unresolved_report,
    write_registry,
    write_report,
)
from ukrposhta_address_matcher.stats import RuntimeStats


def _match_unique_request(
    raw_address: str,
    postcode: str,
    cache_path: str | Path,
    settings: Settings,
    use_ai: bool,
) -> tuple[MatchResult, RuntimeStats]:
    cache_store = CacheStore(cache_path)
    stats = RuntimeStats()
    try:
        classifier = UkrposhtaClassifierClient(settings.ukrposhta_bearer_token, cache_store, stats=stats)
        ai_client = GeminiFallbackClient(settings.gemini_api_key)
        matcher = AddressMatcher(classifier, cache_store=cache_store, ai_client=ai_client, use_ai=use_ai, stats=stats)
        return matcher.match(raw_address, postcode), stats
    finally:
        cache_store.close()


def _run_batch_matches(
    rows,
    cache_path: str | Path,
    settings: Settings,
    use_ai: bool,
    match_workers: int,
) -> tuple[dict[int, MatchResult], RuntimeStats]:
    unique_requests: dict[tuple[str, str], list[int]] = {}
    for row in rows:
        unique_requests.setdefault((row.raw_address, row.postcode), []).append(row.line_no)

    deduped_results: dict[tuple[str, str], MatchResult] = {}
    aggregate_stats = RuntimeStats()
    request_keys = list(unique_requests.keys())
    worker_count = max(1, min(match_workers, len(request_keys)))

    if worker_count == 1:
        for raw_address, postcode in request_keys:
            result, stats = _match_unique_request(
                raw_address,
                postcode,
                cache_path=cache_path,
                settings=settings,
                use_ai=use_ai,
            )
            deduped_results[(raw_address, postcode)] = result
            aggregate_stats.merge(stats)
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_key = {
                executor.submit(
                    _match_unique_request,
                    raw_address,
                    postcode,
                    cache_path,
                    settings,
                    use_ai,
                ): (raw_address, postcode)
                for raw_address, postcode in request_keys
            }
            for future, key in future_to_key.items():
                result, stats = future.result()
                deduped_results[key] = result
                aggregate_stats.merge(stats)

    results: dict[int, MatchResult] = {}
    for key, line_numbers in unique_requests.items():
        result = deduped_results[key]
        for line_no in line_numbers:
            results[line_no] = result
    return results, aggregate_stats


def process_registry(
    input_path: str | Path,
    output_path: str | Path,
    report_path: str | Path,
    cache_path: str | Path,
    settings: Settings,
    use_ai: bool = True,
    match_workers: int | None = None,
) -> dict[str, object]:
    document = read_registry(input_path)
    rows = document.rows
    results, stats = _run_batch_matches(
        rows,
        cache_path=cache_path,
        settings=settings,
        use_ai=use_ai,
        match_workers=match_workers or settings.classifier_match_workers,
    )
    write_registry(output_path, rows, results, encoding=document.encoding)
    write_report(report_path, rows, results)
    unresolved_report_path = Path(report_path).with_name(f"{Path(report_path).stem}_postcode_unresolved.csv")
    unresolved_count = write_postcode_unresolved_report(unresolved_report_path, rows, results)
    return {
        "rows": len(rows),
        "review_rows": sum(1 for item in results.values() if item.status.endswith("review")),
        "postcode_unresolved_rows": unresolved_count,
        "postcode_unresolved_report": str(unresolved_report_path),
        "stats": stats.to_summary(len({(row.raw_address, row.postcode) for row in rows})),
    }


def warm_cache_for_registry(
    input_path: str | Path,
    cache_path: str | Path,
    settings: Settings,
    use_ai: bool = True,
    match_workers: int | None = None,
) -> dict[str, object]:
    document = read_registry(input_path)
    rows = document.rows
    results, stats = _run_batch_matches(
        rows,
        cache_path=cache_path,
        settings=settings,
        use_ai=use_ai,
        match_workers=match_workers or settings.classifier_match_workers,
    )
    unique_requests = len({(row.raw_address, row.postcode) for row in rows})
    unresolved_count = sum(1 for item in results.values() if item.postcode_state == "postcode_unresolved")
    return {
        "rows": len(rows),
        "unique_requests": unique_requests,
        "review_rows": sum(1 for item in results.values() if item.status.endswith("review")),
        "postcode_unresolved_rows": unresolved_count,
        "stats": stats.to_summary(unique_requests),
    }


def refresh_cached_entries(cache_path: str | Path, settings: Settings) -> int:
    cache_store = CacheStore(cache_path)
    classifier = UkrposhtaClassifierClient(settings.ukrposhta_bearer_token, cache_store)
    refreshed = classifier.refresh_cached_requests()
    cache_store.set_metadata("last_refresh", datetime.now(timezone.utc).isoformat())
    cache_store.close()
    return refreshed
