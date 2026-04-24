from __future__ import annotations

from dataclasses import asdict
import hashlib
from http.client import IncompleteRead
from pathlib import Path
import random
import socket
import time
from typing import Iterable
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from ukrposhta_address_matcher.cache import CacheStore
from ukrposhta_address_matcher.models import AddressCandidate, CityCandidate, PostOfficeCandidate, StreetCandidate
from ukrposhta_address_matcher.stats import RuntimeStats


BASE_URL = "https://www.ukrposhta.ua/address-classifier-ws"


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _to_dict(entry: ET.Element) -> dict[str, str]:
    data: dict[str, str] = {}
    for child in entry:
        data[_strip_ns(child.tag)] = (child.text or "").strip()
    return data


class UkrposhtaClassifierClient:
    def __init__(
        self,
        bearer_token: str,
        cache_store: CacheStore,
        ttl_days: int = 30,
        max_retries: int = 5,
        stats: RuntimeStats | None = None,
    ) -> None:
        self.bearer_token = bearer_token
        self.cache_store = cache_store
        self.ttl_days = ttl_days
        self.max_retries = max_retries
        self.stats = stats or RuntimeStats()
        self.request_timeout_seconds = 90
        self.min_request_interval_seconds = 0.2
        self._last_request_at = 0.0
        self._memory_response_cache: dict[str, str] = {}

    def _build_cache_key(self, endpoint: str, params: dict[str, str]) -> str:
        payload = f"{endpoint}|{urlencode(sorted(params.items()))}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _request(self, endpoint: str, params: dict[str, str], refresh: bool = False) -> str:
        cache_key = self._build_cache_key(endpoint, params)
        if not refresh:
            self.stats.response_cache_lookups += 1
            memory_cached = self._memory_response_cache.get(cache_key)
            if memory_cached is not None:
                self.stats.response_memory_hits += 1
                return memory_cached
            cached = self.cache_store.get_response(cache_key, ttl_days=self.ttl_days)
            if cached is not None:
                self.stats.response_sqlite_hits += 1
                self._memory_response_cache[cache_key] = cached
                return cached

        url = f"{BASE_URL}/{endpoint}?{urlencode(params)}"
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {self.bearer_token}",
                "Accept": "application/xml, text/xml;q=0.9, */*;q=0.1",
                "User-Agent": "ukrposhta-address-matcher/0.1",
                "Connection": "close",
            },
        )
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                self._wait_for_request_slot()
                self.stats.classifier_http_requests += 1
                with urlopen(request, timeout=self.request_timeout_seconds) as response:
                    body = response.read().decode("utf-8")
                self._last_request_at = time.monotonic()
                if not _looks_like_xml(body):
                    raise ValueError(f"Classifier returned non-XML payload for {endpoint}")
                break
            except HTTPError as error:
                last_error = error
                if error.code not in (429, 500, 502, 503, 504) or attempt + 1 >= self.max_retries:
                    raise
                time.sleep(self._retry_delay(attempt))
            except (URLError, TimeoutError, socket.timeout, IncompleteRead, ValueError) as error:
                last_error = error
                if attempt + 1 >= self.max_retries:
                    raise
                time.sleep(self._retry_delay(attempt))
        else:
            raise RuntimeError(f"Classifier request failed after retries: {endpoint} {params}") from last_error
        self.cache_store.set_response(cache_key, endpoint, params, body)
        self._memory_response_cache[cache_key] = body
        return body

    def _entries(self, endpoint: str, params: dict[str, str], refresh: bool = False) -> list[dict[str, str]]:
        xml_text = self._request(endpoint, params, refresh=refresh)
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            if refresh:
                raise
            xml_text = self._request(endpoint, params, refresh=True)
            root = ET.fromstring(xml_text)
        entries: list[dict[str, str]] = []
        for child in root:
            if _strip_ns(child.tag) != "Entry":
                continue
            entries.append(_to_dict(child))
        return entries

    def _retry_delay(self, attempt: int) -> float:
        base_delay = 1.5 * (attempt + 1)
        jitter = random.uniform(0.0, 0.35)
        return base_delay + jitter

    def _wait_for_request_slot(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.min_request_interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

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
        if not refresh:
            self.stats.city_cache_lookups += 1
            cached_candidates = self.cache_store.get_cached_city_candidates(city_name, ttl_days=self.ttl_days)
            if cached_candidates is not None:
                self.stats.city_cache_hits += 1
                return [CityCandidate(**item) for item in cached_candidates]
        entries = self._entries(
            "get_city_by_region_id_and_district_id_and_city_ua",
            {"city_ua": city_name},
            refresh=refresh,
        )
        candidates = [
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
        self.cache_store.set_cached_city_candidates(city_name, [asdict(item) for item in candidates])
        return candidates

    def get_streets_by_name(self, city_id: str, street_name: str, refresh: bool = False) -> list[StreetCandidate]:
        if not refresh:
            self.stats.street_cache_lookups += 1
            cached_candidates = self.cache_store.get_cached_street_candidates(
                city_id,
                street_name,
                ttl_days=self.ttl_days,
            )
            if cached_candidates is not None:
                self.stats.street_cache_hits += 1
                return [StreetCandidate(**item) for item in cached_candidates]
        entries = self._entries(
            "get_street_by_name",
            {"city_id": city_id, "street_name": street_name, "lang": "UA", "fuzzy": "1"},
            refresh=refresh,
        )
        candidates = [
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
        self.cache_store.set_cached_street_candidates(city_id, street_name, [asdict(item) for item in candidates])
        return candidates

    def get_houses_by_street_id(
        self,
        street_id: str,
        house_number: str = "",
        refresh: bool = False,
    ) -> list[tuple[str, str]]:
        if not refresh:
            self.stats.street_house_cache_lookups += 1
            cached_houses = self.cache_store.get_cached_houses(
                street_id,
                house_number=house_number,
                ttl_days=self.ttl_days,
            )
            if cached_houses is not None:
                self.stats.street_house_cache_hits += 1
                return cached_houses
        params = {"street_id": street_id}
        if house_number:
            params["housenumber"] = house_number
        entries = self._entries("get_addr_house_by_street_id", params, refresh=refresh)
        houses = [
            (
                item.get("HOUSENUMBER_UA", item.get("HOUSENUMBER", "")),
                item.get("POSTCODE", ""),
            )
            for item in entries
        ]
        if house_number:
            self.cache_store.upsert_street_houses(street_id, houses)
        else:
            self.cache_store.replace_street_houses(street_id, houses)
        return houses

    def get_post_offices_by_city_id(self, city_id: str, refresh: bool = False) -> list[PostOfficeCandidate]:
        entries = self._entries(
            "get_postoffices_by_postcode_cityid_cityvpzid",
            {"city_id": city_id},
            refresh=refresh,
        )
        return [
            PostOfficeCandidate(
                postoffice_id=item.get("POSTOFFICE_ID", ""),
                postcode=item.get("POSTCODE", ""),
                city_id=item.get("CITY_ID", ""),
                city=item.get("CITY_UA_VPZ", item.get("CITY_UA", "")),
                city_type_short=item.get("CITY_UA_TYPE", item.get("SHORTCITYTYPE_UA", "")),
                street=item.get("STREET_UA_VPZ", item.get("STREET_UA", "")),
                house_number=item.get("HOUSENUMBER", item.get("HOUSENUMBER_UA", "")),
                lock_code=item.get("LOCK_CODE", ""),
                is_security=item.get("IS_SECURITY", "0") == "1",
                type_acronym=item.get("TYPE_ACRONYM", ""),
                type_long=item.get("TYPE_LONG", ""),
            )
            for item in entries
        ]

    def refresh_cached_requests(self) -> int:
        refreshed = 0
        for _, endpoint, params in self.cache_store.iter_cached_requests():
            self._request(endpoint, params, refresh=True)
            refreshed += 1
        return refreshed


def _looks_like_xml(value: str) -> bool:
    stripped = value.lstrip()
    return stripped.startswith("<?xml") or stripped.startswith("<")
