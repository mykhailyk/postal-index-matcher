from __future__ import annotations

from dataclasses import asdict
import hashlib
from pathlib import Path
import time
from typing import Iterable
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from ukrposhta_address_matcher.cache import CacheStore
from ukrposhta_address_matcher.models import AddressCandidate, CityCandidate, StreetCandidate


BASE_URL = "https://www.ukrposhta.ua/address-classifier-ws"


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _to_dict(entry: ET.Element) -> dict[str, str]:
    data: dict[str, str] = {}
    for child in entry:
        data[_strip_ns(child.tag)] = (child.text or "").strip()
    return data


class UkrposhtaClassifierClient:
    def __init__(self, bearer_token: str, cache_store: CacheStore, ttl_days: int = 30, max_retries: int = 4) -> None:
        self.bearer_token = bearer_token
        self.cache_store = cache_store
        self.ttl_days = ttl_days
        self.max_retries = max_retries

    def _build_cache_key(self, endpoint: str, params: dict[str, str]) -> str:
        payload = f"{endpoint}|{urlencode(sorted(params.items()))}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _request(self, endpoint: str, params: dict[str, str], refresh: bool = False) -> str:
        cache_key = self._build_cache_key(endpoint, params)
        if not refresh:
            cached = self.cache_store.get_response(cache_key, ttl_days=self.ttl_days)
            if cached is not None:
                return cached

        url = f"{BASE_URL}/{endpoint}?{urlencode(params)}"
        request = Request(url, headers={"Authorization": f"Bearer {self.bearer_token}"})
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                with urlopen(request, timeout=60) as response:
                    body = response.read().decode("utf-8")
                break
            except HTTPError as error:
                last_error = error
                if error.code not in (429, 500, 502, 503, 504) or attempt + 1 >= self.max_retries:
                    raise
                time.sleep(1.5 * (attempt + 1))
            except URLError as error:
                last_error = error
                if attempt + 1 >= self.max_retries:
                    raise
                time.sleep(1.5 * (attempt + 1))
        else:
            raise RuntimeError(f"Classifier request failed after retries: {endpoint} {params}") from last_error
        self.cache_store.set_response(cache_key, endpoint, params, body)
        return body

    def _entries(self, endpoint: str, params: dict[str, str], refresh: bool = False) -> list[dict[str, str]]:
        xml_text = self._request(endpoint, params, refresh=refresh)
        root = ET.fromstring(xml_text)
        entries: list[dict[str, str]] = []
        for child in root:
            if _strip_ns(child.tag) != "Entry":
                continue
            entries.append(_to_dict(child))
        return entries

    def get_addresses_by_postcode(self, postcode: str, refresh: bool = False) -> list[AddressCandidate]:
        entries = self._entries("get_address_by_postcode", {"postcode": postcode, "lang": "UA"}, refresh=refresh)
        return [
            AddressCandidate(
                postcode=item.get("POSTCODE", ""),
                region=item.get("REGION_NAME", item.get("REGION_UA", "")),
                district=item.get("DISTRICT_NAME", item.get("DISTRICT_UA", "")),
                city=item.get("CITY_NAME", item.get("CITY_UA", "")),
                city_type_short=item.get("CITYTYPE_NAME", item.get("SHORTCITYTYPE_UA", "")),
                city_type_full=item.get("CITYTYPE_UA", ""),
                street=item.get("STREET_NAME", item.get("STREET_UA", "")),
                street_type_short=item.get("SHORTSTREETTYPE_NAME", ""),
                street_type_full=item.get("STREETTYPE_NAME", ""),
                house_number=item.get("HOUSENUMBER", item.get("HOUSENUMBER_UA", "")),
                old_street=item.get("OLDSTREET_NAME", ""),
                old_city=item.get("OLDCITY_NAME", item.get("OLDCITY_UA", "")),
                city_id=item.get("CITY_ID", ""),
                street_id=item.get("STREET_ID", ""),
            )
            for item in entries
        ]

    def get_cities_by_name(self, city_name: str, refresh: bool = False) -> list[CityCandidate]:
        entries = self._entries(
            "get_city_by_region_id_and_district_id_and_city_ua",
            {"city_ua": city_name},
            refresh=refresh,
        )
        return [
            CityCandidate(
                region_id=item.get("REGION_ID", ""),
                district_id=item.get("DISTRICT_ID", ""),
                city_id=item.get("CITY_ID", ""),
                region=item.get("REGION_UA", item.get("REGION_NAME", "")),
                district=item.get("DISTRICT_UA", item.get("DISTRICT_NAME", "")),
                city=item.get("CITY_UA", item.get("CITY_NAME", "")),
                city_type_short=item.get("SHORTCITYTYPE_UA", item.get("CITYTYPE_NAME", "")),
                city_type_full=item.get("CITYTYPE_UA", ""),
                population=int(item.get("POPULATION", "0") or "0"),
                old_city=item.get("OLDCITY_UA", item.get("OLDCITY_NAME", "")),
            )
            for item in entries
        ]

    def get_streets_by_name(self, city_id: str, street_name: str, refresh: bool = False) -> list[StreetCandidate]:
        entries = self._entries(
            "get_street_by_name",
            {"city_id": city_id, "street_name": street_name, "lang": "UA", "fuzzy": "1"},
            refresh=refresh,
        )
        return [
            StreetCandidate(
                region_id=item.get("REGION_ID", ""),
                district_id=item.get("DISTRICT_ID", ""),
                city_id=item.get("CITY_ID", ""),
                street_id=item.get("STREET_ID", ""),
                region=item.get("REGION_NAME", item.get("REGION_UA", "")),
                district=item.get("DISTRICT_NAME", item.get("DISTRICT_UA", "")),
                city=item.get("CITY_NAME", item.get("CITY_UA", "")),
                city_type_short=item.get("CITYTYPE_NAME", item.get("SHORTCITYTYPE_UA", "")),
                city_type_full=item.get("CITYTYPE_UA", ""),
                street=item.get("STREET_NAME", item.get("STREET_UA", "")),
                street_type_short=item.get("SHORTSTREETTYPE_NAME", ""),
                street_type_full=item.get("STREETTYPE_NAME", ""),
                old_street=item.get("OLDSTREET_NAME", ""),
            )
            for item in entries
        ]

    def get_houses_by_street_id(self, street_id: str, refresh: bool = False) -> list[tuple[str, str]]:
        entries = self._entries("get_addr_house_by_street_id", {"street_id": street_id}, refresh=refresh)
        return [
            (
                item.get("HOUSENUMBER_UA", item.get("HOUSENUMBER", "")),
                item.get("POSTCODE", ""),
            )
            for item in entries
        ]

    def refresh_cached_requests(self) -> int:
        refreshed = 0
        for _, endpoint, params in self.cache_store.iter_cached_requests():
            self._request(endpoint, params, refresh=True)
            refreshed += 1
        return refreshed
