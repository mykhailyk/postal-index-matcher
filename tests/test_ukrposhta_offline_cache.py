from models.address import Address
from search.hybrid_search import HybridSearch
from search.ukrposhta_offline_cache import UkrposhtaOfflineCacheClient, init_ukrposhta_cache_schema


def seed_classifier_cache(db_path):
    init_ukrposhta_cache_schema(str(db_path))
    import sqlite3

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO cities (
                city_id, region_id, district_id, region, district, city,
                city_type_short, old_city, population
            )
            VALUES ('29713', '286', '412', 'Київ', 'Київ', 'Київ', 'м.', '', 2827400)
            """
        )
        conn.execute(
            """
            INSERT INTO streets (street_id, city_id, street, street_type_short, old_street)
            VALUES ('street-1', '29713', 'Пасхаліна Юрія', 'вул.', 'Ілліча')
            """
        )
        conn.execute(
            """
            INSERT INTO houses (street_id, house_number, normalized_house_number, postcode)
            VALUES ('street-1', '23', '23', '02096')
            """
        )


def test_offline_cache_finds_current_street_by_old_street_name(tmp_path):
    db_path = tmp_path / "classifier.sqlite"
    seed_classifier_cache(db_path)
    client = UkrposhtaOfflineCacheClient(str(db_path))

    cities = client.get_cities_by_name("Київ")
    streets = client.get_streets_by_name(cities[0].city_id, "вул.Ілліча")
    houses = client.get_houses_by_street_id(streets[0].street_id, "23")

    assert cities[0].city_id == "29713"
    assert streets[0].street == "Пасхаліна Юрія"
    assert streets[0].old_street == "Ілліча"
    assert houses == [("23", "02096")]


def test_hybrid_search_uses_offline_classifier_for_old_street_name(tmp_path):
    db_path = tmp_path / "classifier.sqlite"
    seed_classifier_cache(db_path)
    search = HybridSearch(lazy_load=True)
    search.classifier = UkrposhtaOfflineCacheClient(str(db_path))

    results = search._get_classifier_results(Address(city="Київ", street="вул.Ілліча", building="23"))

    assert results
    assert results[0]["index"] == "02096"
    assert results[0]["street"] == "вул. Пасхаліна Юрія"
    assert results[0]["source"] == "ukrposhta_classifier"
