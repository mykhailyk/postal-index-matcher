from pathlib import Path

from ukrposhta_address_matcher.cache import CacheStore
from ukrposhta_address_matcher.classifier import UkrposhtaClassifierClient


def test_classifier_reuses_full_street_snapshot_for_targeted_house_lookup(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.sqlite"
    cache_store = CacheStore(cache_path)
    client = UkrposhtaClassifierClient("token", cache_store)
    calls: list[tuple[str, dict[str, str]]] = []

    def fake_entries(endpoint: str, params: dict[str, str], refresh: bool = False) -> list[dict[str, str]]:
        calls.append((endpoint, dict(params)))
        return [
            {"HOUSENUMBER_UA": "10", "POSTCODE": "04116"},
            {"HOUSENUMBER_UA": "12", "POSTCODE": "04116"},
        ]

    client._entries = fake_entries  # type: ignore[method-assign]
    assert client.get_houses_by_street_id("street-1") == [("10", "04116"), ("12", "04116")]
    assert calls == [("get_addr_house_by_street_id", {"street_id": "street-1"})]
    cache_store.close()

    cache_store = CacheStore(cache_path)
    client = UkrposhtaClassifierClient("token", cache_store)

    def no_network(*args, **kwargs):
        raise AssertionError("network call was not expected")

    client._entries = no_network  # type: ignore[method-assign]
    assert client.get_houses_by_street_id("street-1", house_number="10") == [("10", "04116")]
    cache_store.close()


def test_classifier_uses_full_street_snapshot_for_missing_house_without_network(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.sqlite"
    cache_store = CacheStore(cache_path)
    client = UkrposhtaClassifierClient("token", cache_store)

    def fake_entries(endpoint: str, params: dict[str, str], refresh: bool = False) -> list[dict[str, str]]:
        return [
            {"HOUSENUMBER_UA": "10", "POSTCODE": "04116"},
            {"HOUSENUMBER_UA": "12", "POSTCODE": "04116"},
        ]

    client._entries = fake_entries  # type: ignore[method-assign]
    client.get_houses_by_street_id("street-1")
    cache_store.close()

    cache_store = CacheStore(cache_path)
    client = UkrposhtaClassifierClient("token", cache_store)

    def no_network(*args, **kwargs):
        raise AssertionError("network call was not expected")

    client._entries = no_network  # type: ignore[method-assign]
    assert client.get_houses_by_street_id("street-1", house_number="999") == []
    cache_store.close()
