from pathlib import Path

from ukrposhta_address_matcher.cache import CacheStore
from ukrposhta_address_matcher.config import Settings
from ukrposhta_address_matcher.matcher import AddressMatcher
from ukrposhta_address_matcher.models import CityCandidate, MatchResult, ParsedAddress, RegistryDocument, RegistryRow, StreetCandidate, StructuredAddress
from ukrposhta_address_matcher import service


class FakeClassifier:
    def __init__(self, targeted_houses: list[tuple[str, str]], fallback_houses: list[tuple[str, str]] | None = None) -> None:
        self.targeted_houses = targeted_houses
        self.fallback_houses = fallback_houses if fallback_houses is not None else targeted_houses
        self.house_calls: list[tuple[str, str]] = []

    def get_cities_by_name(self, city_name: str, refresh: bool = False) -> list[CityCandidate]:
        return [
            CityCandidate(
                region_id="1",
                district_id="1",
                city_id="city-1",
                region="Київ",
                district="Київ",
                city="Київ",
                city_type_short="м.",
                city_type_full="місто",
                population=1000,
            )
        ]

    def get_streets_by_name(self, city_id: str, street_name: str, refresh: bool = False) -> list[StreetCandidate]:
        return [
            StreetCandidate(
                region_id="1",
                district_id="1",
                city_id=city_id,
                street_id="street-1",
                region="Київ",
                district="Київ",
                city="Київ",
                city_type_short="м.",
                city_type_full="місто",
                street="Тестова",
                street_type_short="вул.",
                street_type_full="вулиця",
            )
        ]

    def get_houses_by_street_id(
        self,
        street_id: str,
        house_number: str = "",
        refresh: bool = False,
    ) -> list[tuple[str, str]]:
        self.house_calls.append((street_id, house_number))
        if house_number:
            return self.targeted_houses
        return self.fallback_houses


def _build_matcher(tmp_path: Path, classifier: FakeClassifier) -> AddressMatcher:
    cache_store = CacheStore(tmp_path / "cache.sqlite")
    return AddressMatcher(classifier, cache_store=cache_store, ai_client=None, use_ai=False)


def test_matcher_uses_targeted_house_lookup_before_full_street_scan(tmp_path: Path) -> None:
    classifier = FakeClassifier(targeted_houses=[("10", "04116")])
    matcher = _build_matcher(tmp_path, classifier)

    candidate = matcher._search_without_locked_postcode(
        ParsedAddress(city="Київ", street="Тестова", house_number="10", postcode="04116"),
        raw_address="м. Київ, вул. Тестова, буд. 10",
    )

    assert candidate is not None
    assert classifier.house_calls == [("street-1", "10")]


def test_matcher_falls_back_to_full_street_scan_when_targeted_lookup_is_empty(tmp_path: Path) -> None:
    classifier = FakeClassifier(targeted_houses=[], fallback_houses=[("10", "04116"), ("12", "04116")])
    matcher = _build_matcher(tmp_path, classifier)

    candidate = matcher._search_without_locked_postcode(
        ParsedAddress(city="Київ", street="Тестова", house_number="10", postcode="04116"),
        raw_address="м. Київ, вул. Тестова, буд. 10",
    )

    assert candidate is not None
    assert classifier.house_calls == [("street-1", "10"), ("street-1", "")]


def test_process_registry_deduplicates_identical_addresses_within_batch(tmp_path: Path, monkeypatch) -> None:
    rows = [
        RegistryRow(
            line_no=1,
            raw_line="1;0;04116;м. Київ, вул. Тестова, буд. 10;n;s;10;m;5;110x220",
            fields=["1", "0", "04116", "м. Київ, вул. Тестова, буд. 10", "n", "s", "10", "m", "5", "110x220"],
        ),
        RegistryRow(
            line_no=2,
            raw_line="2;0;04116;м. Київ, вул. Тестова, буд. 10;n;s;10;m;5;110x220",
            fields=["2", "0", "04116", "м. Київ, вул. Тестова, буд. 10", "n", "s", "10", "m", "5", "110x220"],
        ),
    ]
    document = RegistryDocument(rows=rows, encoding="utf-8")
    match_calls: list[tuple[str, str]] = []
    result = MatchResult(
        structured_address=StructuredAddress(
            postcode="04116",
            region="Київ",
            district="Київ",
            city="Київ",
            street="Тестова",
            house_number="10",
        ),
        status="postcode_verified",
        deviation_percent=0,
        postcode_state="postcode_verified_locked",
        input_postcode="04116",
        resolved_postcode="04116",
    )

    class DummyCacheStore:
        def __init__(self, db_path: str | Path) -> None:
            self.db_path = db_path

        def close(self) -> None:
            return None

    class DummyMatcher:
        def __init__(self, classifier_client, cache_store, ai_client=None, use_ai: bool = True, stats=None) -> None:
            self.classifier_client = classifier_client
            self.cache_store = cache_store

        def match(self, raw_address: str, postcode: str) -> MatchResult:
            match_calls.append((raw_address, postcode))
            return result

    monkeypatch.setattr(service, "read_registry", lambda input_path: document)
    monkeypatch.setattr(service, "write_registry", lambda output_path, rows, results, encoding: None)
    monkeypatch.setattr(service, "write_report", lambda report_path, rows, results: None)
    monkeypatch.setattr(service, "CacheStore", DummyCacheStore)
    monkeypatch.setattr(service, "UkrposhtaClassifierClient", lambda bearer_token, cache_store, stats=None: object())
    monkeypatch.setattr(service, "GeminiFallbackClient", lambda api_key: None)
    monkeypatch.setattr(service, "AddressMatcher", DummyMatcher)

    summary = service.process_registry(
        input_path=tmp_path / "input.txt",
        output_path=tmp_path / "output.txt",
        report_path=tmp_path / "report.csv",
        cache_path=tmp_path / "cache.sqlite",
        settings=Settings(
            ukrposhta_bearer_token="token",
            gemini_api_key="",
            classifier_cache_path=str(tmp_path / "cache.sqlite"),
            classifier_match_workers=1,
            classifier_refresh_hour=3,
            classifier_refresh_minute=0,
            classifier_refresh_tz="Europe/Kyiv",
            github_username="mykhailyk",
        ),
        use_ai=False,
    )

    assert match_calls == [("м. Київ, вул. Тестова, буд. 10", "04116")]
    assert summary["rows"] == 2
    assert summary["review_rows"] == 0
    assert summary["stats"]["unique_requests"] == 1


def test_warm_cache_for_registry_returns_unique_request_count(tmp_path: Path, monkeypatch) -> None:
    rows = [
        RegistryRow(
            line_no=1,
            raw_line="1;0;04116;м. Київ, вул. Тестова, буд. 10;n;s;10;m;5;110x220",
            fields=["1", "0", "04116", "м. Київ, вул. Тестова, буд. 10", "n", "s", "10", "m", "5", "110x220"],
        ),
        RegistryRow(
            line_no=2,
            raw_line="2;0;04116;м. Київ, вул. Тестова, буд. 10;n;s;10;m;5;110x220",
            fields=["2", "0", "04116", "м. Київ, вул. Тестова, буд. 10", "n", "s", "10", "m", "5", "110x220"],
        ),
        RegistryRow(
            line_no=3,
            raw_line="3;0;04210;м. Київ, вул. Інша, буд. 1;n;s;10;m;5;110x220",
            fields=["3", "0", "04210", "м. Київ, вул. Інша, буд. 1", "n", "s", "10", "m", "5", "110x220"],
        ),
    ]
    document = RegistryDocument(rows=rows, encoding="utf-8")
    result = MatchResult(
        structured_address=StructuredAddress(
            postcode="04116",
            region="Київ",
            district="Київ",
            city="Київ",
            street="Тестова",
            house_number="10",
        ),
        status="postcode_verified",
        deviation_percent=0,
        postcode_state="postcode_verified_locked",
        input_postcode="04116",
        resolved_postcode="04116",
    )

    monkeypatch.setattr(service, "read_registry", lambda input_path: document)
    monkeypatch.setattr(
        service,
        "_run_batch_matches",
        lambda rows, cache_path, settings, use_ai, match_workers: (
            {row.line_no: result for row in rows},
            service.RuntimeStats(),
        ),
    )

    summary = service.warm_cache_for_registry(
        input_path=tmp_path / "input.txt",
        cache_path=tmp_path / "cache.sqlite",
        settings=Settings(
            ukrposhta_bearer_token="token",
            gemini_api_key="",
            classifier_cache_path=str(tmp_path / "cache.sqlite"),
            classifier_match_workers=1,
            classifier_refresh_hour=3,
            classifier_refresh_minute=0,
            classifier_refresh_tz="Europe/Kyiv",
            github_username="mykhailyk",
        ),
        use_ai=False,
    )

    assert summary["rows"] == 3
    assert summary["unique_requests"] == 2
    assert summary["review_rows"] == 0
    assert summary["stats"]["unique_requests"] == 2
