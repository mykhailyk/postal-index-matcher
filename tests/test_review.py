from pathlib import Path

import pytest

from ukrposhta_address_matcher.config import Settings
from ukrposhta_address_matcher.models import AddressCandidate, CityCandidate, MatchResult, PostOfficeCandidate, StructuredAddress
from ukrposhta_address_matcher.review import ReviewBatchStore, route_match_result


class DummyStats:
    def to_summary(self, unique_requests: int) -> dict[str, object]:
        return {
            "unique_requests": unique_requests,
            "classifier_http_requests": 0,
            "final_cache": {"lookups": 0, "hits": 0, "hit_rate_percent": 0.0},
            "city_cache": {"lookups": 0, "hits": 0, "hit_rate_percent": 0.0},
            "street_cache": {"lookups": 0, "hits": 0, "hit_rate_percent": 0.0},
            "street_house_cache": {"lookups": 0, "hits": 0, "hit_rate_percent": 0.0},
            "response_cache": {
                "lookups": 0,
                "hits": 0,
                "memory_hits": 0,
                "sqlite_hits": 0,
                "hit_rate_percent": 0.0,
            },
        }


class DummyCacheStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = db_path

    def close(self) -> None:
        return None


class DummyClassifier:
    def __init__(self, bearer_token: str, cache_store: DummyCacheStore) -> None:
        self.bearer_token = bearer_token
        self.cache_store = cache_store

    def get_addresses_by_postcode(self, postcode: str, refresh: bool = False) -> list[AddressCandidate]:
        if postcode == "04053":
            return [
                AddressCandidate(
                    postcode="04053",
                    region="Київ",
                    district="Київ",
                    city="Київ",
                    city_type_short="м.",
                    city_type_full="місто",
                    street="Велика Житомирська",
                    street_type_short="вул.",
                    street_type_full="вулиця",
                    house_number="30",
                    city_id="kyiv",
                    street_id="street-1",
                )
            ]
        return []

    def get_cities_by_name(self, city_name: str, refresh: bool = False) -> list[CityCandidate]:
        if city_name == "Київ":
            return [
                CityCandidate(
                    region_id="1",
                    district_id="1",
                    city_id="kyiv",
                    region="Київ",
                    district="Київ",
                    city="Київ",
                    city_type_short="м.",
                    city_type_full="місто",
                    population=1000,
                )
            ]
        return []

    def get_post_offices_by_city_id(self, city_id: str, refresh: bool = False) -> list[PostOfficeCandidate]:
        if city_id == "kyiv":
            return [
                PostOfficeCandidate(
                    postoffice_id="office-1",
                    postcode="04053",
                    city_id="kyiv",
                    city="Київ",
                    city_type_short="м.",
                    street="Січових Стрільців",
                    house_number="15",
                    lock_code="0",
                    is_security=False,
                    type_acronym="МВПЗ",
                    type_long="Міське відділення",
                )
            ]
        return []


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        ukrposhta_bearer_token="token",
        gemini_api_key="",
        classifier_cache_path=str(tmp_path / "cache.sqlite"),
        classifier_match_workers=1,
        classifier_refresh_hour=3,
        classifier_refresh_minute=0,
        classifier_refresh_tz="Europe/Kyiv",
        github_username="mykhailyk",
    )


def _match_result(
    *,
    status: str,
    deviation_percent: int,
    warnings: list[str] | None = None,
    input_postcode: str = "04053",
    resolved_postcode: str = "04053",
    used_ai: bool = False,
) -> MatchResult:
    return MatchResult(
        structured_address=StructuredAddress(
            postcode=resolved_postcode,
            region="Київ",
            district="Київ",
            city="Київ",
            street="Велика Житомирська",
            house_number="30",
            apartment_number="",
        ),
        status=status,
        deviation_percent=deviation_percent,
        postcode_state="postcode_verified_locked",
        warnings=warnings or [],
        candidate_count=1,
        input_postcode=input_postcode,
        resolved_postcode=resolved_postcode,
        used_ai=used_ai,
    )


def test_route_match_result_auto_accepts_low_risk_result() -> None:
    routed = route_match_result(
        _match_result(
            status="postcode_corrected",
            deviation_percent=10,
            warnings=[],
        )
    )

    assert routed["queue"] == "auto_accept"
    assert routed["needs_review"] is False


def test_route_match_result_sends_post_office_fallback_to_hard_stop() -> None:
    routed = route_match_result(
        _match_result(
            status="postcode_anchor_review",
            deviation_percent=55,
            warnings=["classifier street unresolved; post office address used for resolved postcode"],
        )
    )

    assert routed["queue"] == "hard_stop"
    assert "Використано fallback на адресу відділення" in routed["reasons"]


def test_route_match_result_sends_nearest_house_to_review() -> None:
    routed = route_match_result(
        _match_result(
            status="postcode_corrected",
            deviation_percent=25,
            warnings=["nearest available house used"],
            used_ai=True,
        )
    )

    assert routed["queue"] == "review"
    assert "Підібрано найближчий будинок" in routed["reasons"]


def test_review_batch_store_requires_operator_decision_before_final_export(tmp_path: Path) -> None:
    input_bytes = (
        "1;0;04053;м. Київ, вул. Велика Житомирська, 30;n;s;10;m;5;110x220\n"
        "2;0;04053;м. Київ, вул. Невідома, 99;n;s;10;m;5;110x220"
    ).encode("utf-8")

    def batch_runner(rows, cache_path, settings, use_ai, match_workers):
        results = {
            1: _match_result(status="postcode_corrected", deviation_percent=10),
            2: _match_result(
                status="postcode_anchor_review",
                deviation_percent=55,
                warnings=["classifier street unresolved; post office address used for resolved postcode"],
            ),
        }
        return results, DummyStats()

    store = ReviewBatchStore(
        data_dir=tmp_path / "review-data",
        cache_path=tmp_path / "cache.sqlite",
        settings=_settings(tmp_path),
        use_ai=False,
        match_workers=1,
        batch_runner=batch_runner,
        cache_store_cls=DummyCacheStore,
        classifier_cls=DummyClassifier,
    )

    batch = store.create_batch_from_upload("sample.txt", input_bytes)

    assert batch["summary"]["auto_accept"] == 1
    assert batch["summary"]["hard_stop"] == 1
    with pytest.raises(ValueError):
        store.export_final_result(batch["batch_id"])


def test_review_batch_store_applies_candidate_decision_and_exports_final_file(tmp_path: Path) -> None:
    input_bytes = "1;0;04053;м. Київ, вул. Невідома, 99;n;s;10;m;5;110x220".encode("utf-8")

    def batch_runner(rows, cache_path, settings, use_ai, match_workers):
        results = {
            1: _match_result(
                status="postcode_anchor_review",
                deviation_percent=55,
                warnings=["classifier street unresolved; post office address used for resolved postcode"],
            )
        }
        return results, DummyStats()

    store = ReviewBatchStore(
        data_dir=tmp_path / "review-data",
        cache_path=tmp_path / "cache.sqlite",
        settings=_settings(tmp_path),
        use_ai=False,
        match_workers=1,
        batch_runner=batch_runner,
        cache_store_cls=DummyCacheStore,
        classifier_cls=DummyClassifier,
    )

    batch = store.create_batch_from_upload("sample.txt", input_bytes)
    detail = store.load_row_detail(batch["batch_id"], 1)

    sources = {candidate["source"] for candidate in detail["candidates"]}
    assert "address_by_postcode" in sources
    assert "post_office" in sources

    store.apply_decision(
        batch["batch_id"],
        1,
        {
            "action": "select_candidate",
            "reason_code": "selected_candidate",
            "comment": "",
            "final_address": {
                "postcode": "04053",
                "region": "Київ",
                "district": "Київ",
                "city": "Київ",
                "street": "Велика Житомирська",
                "houseNumber": "30",
                "apartmentNumber": "",
            },
        },
    )

    filename, payload = store.export_final_result(batch["batch_id"])
    assert filename.endswith("_final.txt")
    assert '"street":"Велика Житомирська"' in payload.decode("utf-8")


def test_review_batch_store_applies_decision_to_similar_rows(tmp_path: Path) -> None:
    input_bytes = (
        "1;0;04053;м. Київ, вул. Невідома, 99;n;s;10;m;5;110x220\n"
        "2;0;04053;м. Київ, вул. Невідома, 99;n;s;10;m;5;110x220"
    ).encode("utf-8")

    def batch_runner(rows, cache_path, settings, use_ai, match_workers):
        result = _match_result(
            status="postcode_anchor_review",
            deviation_percent=55,
            warnings=["classifier street unresolved; post office address used for resolved postcode"],
        )
        return {row.line_no: result for row in rows}, DummyStats()

    store = ReviewBatchStore(
        data_dir=tmp_path / "review-data",
        cache_path=tmp_path / "cache.sqlite",
        settings=_settings(tmp_path),
        use_ai=False,
        match_workers=1,
        batch_runner=batch_runner,
        cache_store_cls=DummyCacheStore,
        classifier_cls=DummyClassifier,
    )

    batch = store.create_batch_from_upload("sample.txt", input_bytes)
    detail = store.load_row_detail(batch["batch_id"], 1)
    assert len(detail["similar_rows"]) == 1

    updated = store.apply_decision(
        batch["batch_id"],
        1,
        {
            "action": "accept_suggested",
            "reason_code": "accepted_suggested",
            "comment": "",
            "apply_to_similar": True,
        },
    )

    assert updated["applied_to_similar_line_nos"] == [2]
    batch_after = store.load_batch(batch["batch_id"])
    decisions = {row["line_no"]: row["decision"] for row in batch_after["rows"]}
    assert decisions[1]["action"] == "accept_suggested"
    assert decisions[2]["action"] == "accept_suggested"
