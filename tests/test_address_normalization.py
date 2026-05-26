from models.address import Address
from search.hybrid_search import HybridSearch
from search.normalizer import TextNormalizer


def test_extracts_lettered_building():
    normalizer = TextNormalizer()

    building, street = normalizer.try_extract_building("ВАСИЛЯ СТУСА 5-А")

    assert building == "5-А"
    assert street == "ВАСИЛЯ СТУСА"


def test_extracts_building_before_corpus_and_apartment():
    normalizer = TextNormalizer()

    building, street = normalizer.try_extract_building("Святошинська 27-КОРП1, #63")

    assert building == "27"
    assert street == "Святошинська"


def test_ignores_placeholder_query_indexes():
    assert HybridSearch._normalize_query_index("01000") == ""
    assert HybridSearch._normalize_query_index("00000") == ""
    assert HybridSearch._normalize_query_index("*") == ""


def test_keeps_real_query_indexes():
    assert HybridSearch._normalize_query_index(" 01024 ") == "1024"


def test_normalizes_russian_city_aliases():
    normalizer = TextNormalizer()

    assert normalizer.normalize_city("г. Киев") == normalizer.normalize_city("Київ")
    assert normalizer.normalize_city("Пятихатки") == normalizer.normalize_city("П'ятихатки")
    assert normalizer.normalize_city("Сєвєродонецьк") == normalizer.normalize_city("Сіверськодонецьк")


def test_normalizes_city_prefixes_without_dot():
    normalizer = TextNormalizer()

    assert normalizer.normalize_city("с Крюківщина") == normalizer.normalize_city("Крюківщина")
    assert normalizer.normalize_city("сел. БОРОДЯНКА") == normalizer.normalize_city("Бородянка")
    assert normalizer.normalize_city("смт ГРАДИЗЬК") == normalizer.normalize_city("Градизьк")


def test_normalizes_extra_street_prefixes():
    normalizer = TextNormalizer()

    assert normalizer.normalize_street("пр. Гвардійський") == normalizer.normalize_street("Гвардійський")
    assert normalizer.normalize_street("пр-т Гвардійський") == normalizer.normalize_street("Гвардійський")
    assert normalizer.normalize_street("прт.Г.Сталінграда") == normalizer.normalize_street("Г.Сталінграда")


def test_normalizes_trailing_road_type_after_generic_street_prefix():
    normalizer = TextNormalizer()

    assert normalizer.normalize_street("вул. Харківське шосе") == normalizer.normalize_street("шосе Харківське")
    assert normalizer.detect_street_type("вул. Харківське шосе") == "highway"


def test_city_specific_street_rename_aliases():
    normalizer = TextNormalizer()

    aliases = normalizer.normalize_street_aliases("ВУЛ.ГОРЬКОГО", "Бахмут")

    assert normalizer.normalize_street("Горького") in aliases
    assert normalizer.normalize_street("Олекси Тихого") in aliases


def test_street_rename_aliases_load_from_csv():
    normalizer = TextNormalizer()

    aliases = normalizer.normalize_street_aliases("Горького", "Бахмут")

    assert normalizer.normalize_street("Олекси Тихого") in aliases


def test_global_street_rename_aliases():
    normalizer = TextNormalizer()

    aliases = normalizer.normalize_street_aliases("БЕЗ НАЗВИ", "Голубине")

    assert normalizer.normalize_street("відсутня") in aliases


def test_detects_street_type():
    normalizer = TextNormalizer()

    assert normalizer.detect_street_type("вул. Шевченка") == "street"
    assert normalizer.detect_street_type("пров. Шевченка") == "lane"
    assert normalizer.detect_street_type("пр-т Перемоги") == "avenue"


def test_preprocesses_full_address_from_street_field():
    search = HybridSearch(lazy_load=True)
    address = Address(street="01032, м. Київ, вул. Жильянська, буд. 59, кв. 1009")

    search._preprocess_full_address(address)

    assert address.city == "м. Київ"
    assert address.street == "вул. Жильянська"
    assert address.building == "59"


def test_preprocesses_full_address_without_prefixes():
    search = HybridSearch(lazy_load=True)
    address = Address(street="01001, Київ, Будівельників, 12а, 61")

    search._preprocess_full_address(address)

    assert address.city == "Київ"
    assert address.street == "Будівельників"
    assert address.building == "12а"


def test_preprocesses_full_address_with_inline_index():
    search = HybridSearch(lazy_load=True)
    address = Address(street="79040 м. Львів, вул. Городоцька, буд. 357")

    search._preprocess_full_address(address)

    assert address.city == "м. Львів"
    assert address.street == "вул. Городоцька"
    assert address.building == "357"


def test_preprocesses_street_building_apartment_when_city_is_mapped_separately():
    search = HybridSearch(lazy_load=True)
    address = Address(
        city="Київ",
        street="вул.Саксаганського, буд.27, кв.47",
        building="вул.Саксаганського, буд.27, кв.47",
    )

    if search.normalizer.normalize_text(address.street) == search.normalizer.normalize_text(address.building):
        address.building = ""
    search._preprocess_full_address(address)

    assert address.city == "Київ"
    assert address.street == "вул.Саксаганського"
    assert address.building == "27"


def test_extract_building_ignores_apartment_part():
    assert HybridSearch._extract_building_from_full_address_parts(["буд.27", "кв.47"]) == "27"
    assert HybridSearch._extract_building_from_full_address_parts(["кв.47"]) == ""


def test_swaps_region_and_district_when_mapping_is_reversed():
    address = Address(region="Києво-Святошинський р-н", district="Київська обл.")

    HybridSearch._preprocess_region_district(address)

    assert address.region == "Київська обл."
    assert address.district == "Києво-Святошинський р-н"


def test_moves_bare_district_out_of_region_field():
    address = Address(region="Святошинський", district="")

    HybridSearch._preprocess_region_district(address)

    assert address.region == ""
    assert address.district == "Святошинський"


def test_extracts_building_before_corpus_from_full_address_parts():
    assert HybridSearch._extract_building_from_full_address_parts(["буд.4корпус 6", "кв.58"]) == "4"


def test_building_base_matches_letter_suffix_only():
    assert HybridSearch._building_base("117-А") == "117"
    assert HybridSearch._building_base("117А") == "117"
    assert HybridSearch._building_base("88-2") == ""
    assert HybridSearch._has_letter_suffix("117-А")
    assert not HybridSearch._has_letter_suffix("117")
    assert not HybridSearch._has_letter_suffix("88-2")
