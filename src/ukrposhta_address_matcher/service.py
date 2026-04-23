from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ukrposhta_address_matcher.ai import GeminiFallbackClient
from ukrposhta_address_matcher.cache import CacheStore
from ukrposhta_address_matcher.classifier import UkrposhtaClassifierClient
from ukrposhta_address_matcher.config import Settings
from ukrposhta_address_matcher.matcher import AddressMatcher
from ukrposhta_address_matcher.registry import read_registry, write_registry, write_report


def process_registry(
    input_path: str | Path,
    output_path: str | Path,
    report_path: str | Path,
    cache_path: str | Path,
    settings: Settings,
    use_ai: bool = True,
) -> dict[str, int]:
    document = read_registry(input_path)
    rows = document.rows
    cache_store = CacheStore(cache_path)
    classifier = UkrposhtaClassifierClient(settings.ukrposhta_bearer_token, cache_store)
    ai_client = GeminiFallbackClient(settings.gemini_api_key)
    matcher = AddressMatcher(classifier, cache_store=cache_store, ai_client=ai_client, use_ai=use_ai)
    results = {row.line_no: matcher.match(row.raw_address, row.postcode) for row in rows}
    write_registry(output_path, rows, results, encoding=document.encoding)
    write_report(report_path, rows, results)
    cache_store.close()
    return {
        "rows": len(rows),
        "review_rows": sum(1 for item in results.values() if item.status.endswith("review")),
    }


def refresh_cached_entries(cache_path: str | Path, settings: Settings) -> int:
    cache_store = CacheStore(cache_path)
    classifier = UkrposhtaClassifierClient(settings.ukrposhta_bearer_token, cache_store)
    refreshed = classifier.refresh_cached_requests()
    cache_store.set_metadata("last_refresh", datetime.now(timezone.utc).isoformat())
    cache_store.close()
    return refreshed
