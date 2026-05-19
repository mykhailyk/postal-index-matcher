from models.address import Address
from search.hybrid_search import HybridSearch
from tools.analyze_search_quality import build_issue_tags, compact_result, summarize


def test_compact_result_handles_missing_result():
    result = compact_result(None)

    assert result["index"] == ""
    assert result["confidence"] == ""


def test_build_issue_tags_detects_placeholder_and_same_source():
    search = HybridSearch(lazy_load=True)
    original = Address(city="Вишневе", street="Святошинська 27", building="Святошинська 27", index="01000")
    processed = Address(city="Вишневе", street="Святошинська", building="27", index="01000")
    result = {"search_mode": "manual", "total_found": 51, "manual": [{"confidence": 89, "is_general": True}]}

    tags = build_issue_tags(original, processed, result, search)

    assert "placeholder_index" in tags
    assert "street_building_same_source" in tags
    assert "building_extracted" in tags
    assert "many_candidates" in tags
    assert "general_index_top" in tags


def test_summarize_counts_modes_and_tags():
    summary = summarize([
        {"mode": "auto", "issue_tags": "placeholder_index,building_extracted"},
        {"mode": "manual", "issue_tags": "placeholder_index"},
    ])

    assert summary["rows_analyzed"] == 2
    assert summary["modes"] == {"auto": 1, "manual": 1}
    assert summary["issue_tags"]["placeholder_index"] == 2
