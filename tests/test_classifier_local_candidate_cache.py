from pathlib import Path

from ukrposhta_address_matcher.cache import CacheStore
from ukrposhta_address_matcher.classifier import UkrposhtaClassifierClient


def test_classifier_reuses_cached_city_candidates_across_normalized_query(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.sqlite"
    cache_store = CacheStore(cache_path)
    client = UkrposhtaClassifierClient("token", cache_store)
    calls: list[tuple[str, dict[str, str]]] = []

    def fake_entries(endpoint: str, params: dict[str, str], refresh: bool = False) -> list[dict[str, str]]:
        calls.append((endpoint, dict(params)))
        return [
            {
                "REGION_ID": "1",
                "DISTRICT_ID": "1",
                "CITY_ID": "city-1",
                "REGION_UA": "Київ",
                "DISTRICT_UA": "Київ",
                "CITY_UA": "Київ",
                "SHORTCITYTYPE_UA": "м.",
                "CITYTYPE_UA": "місто",
                "POPULATION": "1000",
            }
        ]

    client._entries = fake_entries  # type: ignore[method-assign]
    first = client.get_cities_by_name("Київ")
    assert len(first) == 1
    assert calls == [("get_city_by_region_id_and_district_id_and_city_ua", {"city_ua": "Київ"})]
    cache_store.close()

    cache_store = CacheStore(cache_path)
    client = UkrposhtaClassifierClient("token", cache_store)

    def no_network(*args, **kwargs):
        raise AssertionError("network call was not expected")

    client._entries = no_network  # type: ignore[method-assign]
    second = client.get_cities_by_name("київ")
    assert len(second) == 1
    assert second[0].city_id == "city-1"
    cache_store.close()


def test_classifier_reuses_cached_street_candidates_across_normalized_query(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.sqlite"
    cache_store = CacheStore(cache_path)
    client = UkrposhtaClassifierClient("token", cache_store)
    calls: list[tuple[str, dict[str, str]]] = []

    def fake_entries(endpoint: str, params: dict[str, str], refresh: bool = False) -> list[dict[str, str]]:
        calls.append((endpoint, dict(params)))
        return [
            {
                "REGION_ID": "1",
                "DISTRICT_ID": "1",
                "CITY_ID": "city-1",
                "STREET_ID": "street-1",
                "REGION_UA": "Київ",
                "DISTRICT_UA": "Київ",
                "CITY_UA": "Київ",
                "SHORTCITYTYPE_UA": "м.",
                "CITYTYPE_UA": "місто",
                "STREET_UA": "Тестова",
                "SHORTSTREETTYPE_NAME": "вул.",
                "STREETTYPE_NAME": "вулиця",
            }
        ]

    client._entries = fake_entries  # type: ignore[method-assign]
    first = client.get_streets_by_name("city-1", "Тестова")
    assert len(first) == 1
    assert calls == [("get_street_by_name", {"city_id": "city-1", "street_name": "Тестова", "lang": "UA", "fuzzy": "1"})]
    cache_store.close()

    cache_store = CacheStore(cache_path)
    client = UkrposhtaClassifierClient("token", cache_store)

    def no_network(*args, **kwargs):
        raise AssertionError("network call was not expected")

    client._entries = no_network  # type: ignore[method-assign]
    second = client.get_streets_by_name("city-1", "тестова")
    assert len(second) == 1
    assert second[0].street_id == "street-1"
    cache_store.close()
