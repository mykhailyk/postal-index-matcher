from pathlib import Path

from ukrposhta_address_matcher.cache import CacheStore
from ukrposhta_address_matcher.matcher import AddressMatcher
from ukrposhta_address_matcher.models import (
    AddressCandidate,
    CityCandidate,
    ParsedAddress,
    PostOfficeCandidate,
    StreetCandidate,
)


class RegressionClassifier:
    def __init__(self) -> None:
        self.street_queries: list[str] = []

    def get_addresses_by_postcode(self, postcode: str, refresh: bool = False) -> list[AddressCandidate]:
        data = {
            "02218": [
                AddressCandidate(
                    postcode="02218",
                    region="Київ",
                    district="Київ",
                    city="Київ",
                    city_type_short="м.",
                    city_type_full="місто",
                    street="Кибальчича Миколи",
                    street_type_short="вул.",
                    street_type_full="вулиця",
                    house_number="2А",
                    city_id="kyiv",
                    street_id="kibal",
                )
            ],
            "04080": [
                AddressCandidate(
                    postcode="04080",
                    region="Київ",
                    district="Київ",
                    city="Київ",
                    city_type_short="м.",
                    city_type_full="місто",
                    street="Кирилівська",
                    street_type_short="вул.",
                    street_type_full="вулиця",
                    house_number="69-В",
                    old_street="Фрунзе",
                    city_id="kyiv",
                    street_id="kyrylivska",
                )
            ],
            "04053": [
                AddressCandidate(
                    postcode="04053",
                    region="Київ",
                    district="Київ",
                    city="Київ",
                    city_type_short="м.",
                    city_type_full="місто",
                    street="Несторівський",
                    street_type_short="пров.",
                    street_type_full="провулок",
                    house_number="6",
                    city_id="kyiv",
                    street_id="nestorivskyi",
                )
            ],
            "79010": [
                AddressCandidate(
                    postcode="79010",
                    region="Львівська",
                    district="Львівський",
                    city="Львів",
                    city_type_short="м.",
                    city_type_full="місто",
                    street="Личаківська",
                    street_type_short="вул.",
                    street_type_full="вулиця",
                    house_number="1",
                    city_id="lviv",
                    street_id="lych",
                )
            ],
            "82300": [
                AddressCandidate(
                    postcode="82300",
                    region="Львівська",
                    district="Дрогобицький",
                    city="Борислав",
                    city_type_short="м.",
                    city_type_full="місто",
                    street="Воїнів УПА",
                    street_type_short="вул.",
                    street_type_full="вулиця",
                    house_number="20",
                    city_id="boryslav",
                    street_id="upa",
                )
            ],
        }
        return data.get(postcode, [])

    def get_cities_by_name(self, city_name: str, refresh: bool = False) -> list[CityCandidate]:
        mapping = {
            "Васильків": CityCandidate(
                region_id="1",
                district_id="1",
                city_id="vasylkiv",
                region="Київська",
                district="Обухівський",
                city="Васильків",
                city_type_short="м.",
                city_type_full="місто",
                population=1000,
            ),
            "Львів": CityCandidate(
                region_id="2",
                district_id="2",
                city_id="lviv",
                region="Львівська",
                district="Львівський",
                city="Львів",
                city_type_short="м.",
                city_type_full="місто",
                population=1000,
            ),
            "Київ": CityCandidate(
                region_id="3",
                district_id="3",
                city_id="kyiv",
                region="Київ",
                district="Київ",
                city="Київ",
                city_type_short="м.",
                city_type_full="місто",
                population=1000,
            ),
        }
        return [mapping[city_name]] if city_name in mapping else []

    def get_streets_by_name(self, city_id: str, street_name: str, refresh: bool = False) -> list[StreetCandidate]:
        self.street_queries.append(street_name)
        if city_id == "vasylkiv" and street_name == "Комінтерну":
            return [
                StreetCandidate(
                    region_id="1",
                    district_id="1",
                    city_id="vasylkiv",
                    street_id="honcharna",
                    region="Київська",
                    district="Обухівський",
                    city="Васильків",
                    city_type_short="м.",
                    city_type_full="місто",
                    street="Гончарна",
                    street_type_short="вул.",
                    street_type_full="вулиця",
                    old_street="Комінтерну",
                )
            ]
        if city_id == "odessa" and street_name == "Дальницька":
            return [
                StreetCandidate(
                    region_id="2",
                    district_id="2",
                    city_id="odessa",
                    street_id="dalnytska",
                    region="Одеська",
                    district="Одеський",
                    city="Одеса",
                    city_type_short="м.",
                    city_type_full="місто",
                    street="Дальницька",
                    street_type_short="вул.",
                    street_type_full="вулиця",
                )
            ]
        return []

    def get_houses_by_street_id(
        self,
        street_id: str,
        house_number: str = "",
        refresh: bool = False,
    ) -> list[tuple[str, str]]:
        if street_id == "honcharna":
            return [("41", "08602")]
        if street_id == "dalnytska":
            return [("25", "65005"), ("25/1", "65005")]
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
                    type_long="Міське відділення поштового зв'язку",
                )
            ]
        if city_id == "lviv":
            return [
                PostOfficeCandidate(
                    postoffice_id="office-2",
                    postcode="79010",
                    city_id="lviv",
                    city="Львів",
                    city_type_short="м.",
                    street="Личаківська",
                    house_number="1",
                    lock_code="0",
                    is_security=False,
                    type_acronym="МВПЗ",
                    type_long="Міське відділення поштового зв'язку",
                )
            ]
        return []


def _build_matcher(tmp_path: Path, classifier: RegressionClassifier) -> AddressMatcher:
    return AddressMatcher(classifier, cache_store=CacheStore(tmp_path / "cache.sqlite"), ai_client=None, use_ai=False)


def test_best_from_postcode_matches_reordered_street_name(tmp_path: Path) -> None:
    matcher = _build_matcher(tmp_path, RegressionClassifier())
    candidate = matcher._best_from_postcode(
        ParsedAddress(postcode="02218", city="Київ", street="Миколи Кибальчича", house_number="2А"),
        matcher.classifier_client.get_addresses_by_postcode("02218"),
    )
    assert candidate is not None
    assert candidate.street == "Кибальчича Миколи"


def test_best_from_postcode_matches_close_ukrainian_street_spelling(tmp_path: Path) -> None:
    matcher = _build_matcher(tmp_path, RegressionClassifier())
    candidate = matcher._best_from_postcode(
        ParsedAddress(postcode="04080", city="Київ", street="Кирилловская", house_number="69-В"),
        matcher.classifier_client.get_addresses_by_postcode("04080"),
    )
    assert candidate is not None
    assert candidate.street == "Кирилівська"


def test_search_without_locked_postcode_tries_case_variant_for_old_street_name(tmp_path: Path) -> None:
    classifier = RegressionClassifier()
    matcher = _build_matcher(tmp_path, classifier)
    candidate = matcher._search_without_locked_postcode(
        ParsedAddress(
            postcode="08600",
            city="Васильків",
            region="Київська",
            street="Комінтерна",
            house_number="41",
        ),
        raw_address="вул. Комінтерна, 41, м.Васильків",
    )
    assert candidate is not None
    assert candidate.street == "Гончарна"
    assert candidate.postcode == "08602"
    assert classifier.street_queries[:2] == ["Комінтерна", "Комінтерну"]


def test_po_box_returns_review_result_with_post_office_address(tmp_path: Path) -> None:
    matcher = _build_matcher(tmp_path, RegressionClassifier())
    result = matcher.match("а/с 5283, Львів, Львівська область", "79010")
    assert result.status == "po_box_review"
    assert result.structured_address.postcode == "79010"
    assert result.structured_address.city == "Львів"
    assert result.structured_address.street == "Личаківська"
    assert result.structured_address.house_number == "1"


def test_match_uses_postcode_anchor_instead_of_forced_fill_when_full_address_cannot_be_confirmed(tmp_path: Path) -> None:
    matcher = _build_matcher(tmp_path, RegressionClassifier())
    result = matcher.match("вул. Невідома 99, місто Київ", "99999")
    assert result.status == "postcode_anchor_review"
    assert result.forced_fill is False


def test_pick_best_house_does_not_collapse_fractional_house_to_base_number(tmp_path: Path) -> None:
    matcher = _build_matcher(tmp_path, RegressionClassifier())
    house = matcher._pick_best_house("25/2", [("25", "65005"), ("25/1", "65005")])
    assert house is None


def test_search_with_locked_postcode_uses_nearest_house_when_exact_house_missing(tmp_path: Path) -> None:
    classifier = RegressionClassifier()
    matcher = _build_matcher(tmp_path, classifier)
    candidate = matcher._search_with_locked_postcode(
        ParsedAddress(
            postcode="65005",
            city="Одеса",
            region="Одеська",
            street="Дальницька",
            house_number="25/2",
        ),
        "65005",
        [
            AddressCandidate(
                postcode="65005",
                region="Одеська",
                district="Одеський",
                city="Одеса",
                city_type_short="м.",
                city_type_full="місто",
                street="Дальницька",
                street_type_short="вул.",
                street_type_full="вулиця",
                house_number="25",
                city_id="odessa",
                street_id="dalnytska",
            )
        ],
        raw_address="вул. Дальницька 25/2",
    )
    assert candidate is not None
    assert candidate.house_number == "25/1"


def test_match_does_not_use_best_guess_when_user_provided_street_and_house(tmp_path: Path) -> None:
    matcher = _build_matcher(tmp_path, RegressionClassifier())
    result = matcher.match(
        "вул. Дальницька 25/2, місто Одеса",
        "65005",
    )
    assert result.status == "unresolved_review"


def test_match_uses_post_office_address_when_postcode_is_known_but_street_unresolved(tmp_path: Path) -> None:
    matcher = _build_matcher(tmp_path, RegressionClassifier())
    result = matcher.match("вул. Невідома 99, місто Київ", "04053")
    assert result.status == "postcode_anchor_review"
    assert result.structured_address.postcode == "04053"
    assert result.structured_address.street == "Січових Стрільців"
    assert result.structured_address.house_number == "15"


def test_match_prefers_nearest_classifier_address_within_postcode_candidates_before_post_office(tmp_path: Path) -> None:
    matcher = _build_matcher(tmp_path, RegressionClassifier())
    result = matcher.match(
        "Героїв ОУН-УПА 20/3, Борислав, Львівська область",
        "82300",
    )
    assert result.status == "postcode_candidate_review"
    assert result.structured_address.postcode == "82300"
    assert result.structured_address.city == "Борислав"
    assert result.structured_address.street == "Воїнів УПА"
    assert result.structured_address.house_number == "20"
