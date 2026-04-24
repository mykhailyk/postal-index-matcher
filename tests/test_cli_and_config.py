from pathlib import Path

from ukrposhta_address_matcher.cache import CacheStore
from ukrposhta_address_matcher import cli
from ukrposhta_address_matcher.cli import _format_stats, _resolve_cache_path, _resolve_match_workers, _resolve_review_data_dir
from ukrposhta_address_matcher.config import Settings


def test_resolve_cache_path_prefers_explicit_cli_value(tmp_path: Path) -> None:
    settings = Settings(
        ukrposhta_bearer_token="token",
        gemini_api_key="",
        classifier_cache_path=str(tmp_path / "shared.sqlite"),
        classifier_match_workers=4,
        classifier_refresh_hour=3,
        classifier_refresh_minute=0,
        classifier_refresh_tz="Europe/Kyiv",
        github_username="mykhailyk",
    )

    resolved = _resolve_cache_path(str(tmp_path / "explicit.sqlite"), settings)

    assert resolved == str(tmp_path / "explicit.sqlite")


def test_resolve_cache_path_uses_shared_default_from_settings(tmp_path: Path) -> None:
    settings = Settings(
        ukrposhta_bearer_token="token",
        gemini_api_key="",
        classifier_cache_path=str(tmp_path / "shared.sqlite"),
        classifier_match_workers=4,
        classifier_refresh_hour=3,
        classifier_refresh_minute=0,
        classifier_refresh_tz="Europe/Kyiv",
        github_username="mykhailyk",
    )

    resolved = _resolve_cache_path(None, settings)

    assert resolved == str(tmp_path / "shared.sqlite")


def test_resolve_match_workers_prefers_explicit_cli_value(tmp_path: Path) -> None:
    settings = Settings(
        ukrposhta_bearer_token="token",
        gemini_api_key="",
        classifier_cache_path=str(tmp_path / "shared.sqlite"),
        classifier_match_workers=4,
        classifier_refresh_hour=3,
        classifier_refresh_minute=0,
        classifier_refresh_tz="Europe/Kyiv",
        github_username="mykhailyk",
    )

    resolved = _resolve_match_workers(6, settings)

    assert resolved == 6


def test_resolve_match_workers_uses_settings_default(tmp_path: Path) -> None:
    settings = Settings(
        ukrposhta_bearer_token="token",
        gemini_api_key="",
        classifier_cache_path=str(tmp_path / "shared.sqlite"),
        classifier_match_workers=4,
        classifier_refresh_hour=3,
        classifier_refresh_minute=0,
        classifier_refresh_tz="Europe/Kyiv",
        github_username="mykhailyk",
    )

    resolved = _resolve_match_workers(None, settings)

    assert resolved == 4


def test_cache_store_creates_parent_directory_for_shared_cache(tmp_path: Path) -> None:
    cache_path = tmp_path / "nested" / "cache" / "classifier-cache.sqlite"

    cache_store = CacheStore(cache_path)
    cache_store.close()

    assert cache_path.parent.exists()


def test_format_stats_renders_compact_summary() -> None:
    rendered = _format_stats(
        {
            "unique_requests": 10,
            "classifier_http_requests": 6,
            "final_cache": {"lookups": 10, "hits": 4, "hit_rate_percent": 40.0},
            "city_cache": {"lookups": 8, "hits": 3, "hit_rate_percent": 37.5},
            "street_cache": {"lookups": 8, "hits": 2, "hit_rate_percent": 25.0},
            "street_house_cache": {"lookups": 5, "hits": 1, "hit_rate_percent": 20.0},
            "response_cache": {
                "lookups": 7,
                "hits": 5,
                "memory_hits": 2,
                "sqlite_hits": 3,
                "hit_rate_percent": 71.4,
            },
        }
    )

    assert "unique=10" in rendered
    assert "http=6" in rendered
    assert "final=4/10" in rendered


def test_resolve_review_data_dir_uses_absolute_default_when_not_provided() -> None:
    resolved = _resolve_review_data_dir(None)

    assert resolved.endswith(".review-ui-data")


def test_review_ui_main_prepends_subcommand(monkeypatch) -> None:
    captured = {}

    def fake_main(argv):
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(cli, "main", fake_main)

    exit_code = cli.review_ui_main(["--port", "9000"])

    assert exit_code == 0
    assert captured["argv"] == ["review-ui", "--port", "9000"]


def test_main_passes_no_open_browser_flag_to_review_ui(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        ukrposhta_bearer_token="token",
        gemini_api_key="",
        classifier_cache_path=str(tmp_path / "shared.sqlite"),
        classifier_match_workers=4,
        classifier_refresh_hour=3,
        classifier_refresh_minute=0,
        classifier_refresh_tz="Europe/Kyiv",
        github_username="mykhailyk",
    )
    captured = {}

    monkeypatch.setattr(cli.Settings, "load", lambda env_path: settings)

    def fake_run_review_ui(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(cli, "run_review_ui", fake_run_review_ui)

    exit_code = cli.main(["review-ui", "--no-open-browser"])

    assert exit_code == 0
    assert captured["open_browser"] is False
