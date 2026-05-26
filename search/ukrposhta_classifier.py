from dataclasses import dataclass
import hashlib
import json
import os
import time
from typing import Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import config


@dataclass
class ClassifierAddress:
    postcode: str = ""
    region: str = ""
    district: str = ""
    city: str = ""
    city_type_short: str = ""
    street: str = ""
    street_type_short: str = ""
    house_number: str = ""
    old_city: str = ""
    old_street: str = ""
    city_id: str = ""
    street_id: str = ""


@dataclass
class ClassifierCity:
    region: str = ""
    district: str = ""
    city: str = ""
    city_type_short: str = ""
    city_id: str = ""
    population: int = 0
    old_city: str = ""


@dataclass
class ClassifierStreet:
    region: str = ""
    district: str = ""
    city: str = ""
    city_type_short: str = ""
    street: str = ""
    street_type_short: str = ""
    city_id: str = ""
    street_id: str = ""
    old_street: str = ""


@dataclass
class PostOffice:
    postoffice_id: str = ""
    postcode: str = ""
    city_id: str = ""
    city: str = ""
    city_type_short: str = ""
    street: str = ""
    house_number: str = ""
    lock_code: str = ""
    is_security: bool = False
    type_acronym: str = ""
    type_long: str = ""

    def is_working(self) -> bool:
        return self.lock_code in ("", "0") and not self.is_security


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _entry_to_dict(entry: ET.Element) -> Dict[str, str]:
    return {_strip_ns(child.tag): (child.text or "").strip() for child in entry}


class UkrposhtaClassifierClient:
    def __init__(
        self,
        token: str = None,
        base_url: str = None,
        cache_path: str = None,
        timeout_seconds: int = None,
    ):
        self.token = token if token is not None else config.UKRPOSHTA_BEARER_TOKEN
        self.base_url = (base_url or config.UKRPOSHTA_CLASSIFIER_BASE_URL).rstrip("/")
        self.cache_path = cache_path or config.UKRPOSHTA_CLASSIFIER_CACHE_PATH
        self.timeout_seconds = timeout_seconds or config.UKRPOSHTA_CLASSIFIER_TIMEOUT_SECONDS
        self._memory_cache: Dict[str, str] = {}
        self._disk_cache_loaded = False
        self._disk_cache: Dict[str, str] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def get_addresses_by_postcode(self, postcode: str) -> List[ClassifierAddress]:
        entries = self._entries("get_address_by_postcode", {"postcode": postcode, "lang": "UA"})
        return [
            ClassifierAddress(
                postcode=item.get("POSTCODE", ""),
                region=item.get("REGION_NAME", item.get("REGION_UA", "")),
                district=item.get("DISTRICT_NAME", item.get("DISTRICT_UA", "")),
                city=item.get("CITY_NAME", item.get("CITY_UA", "")),
                city_type_short=item.get("CITYTYPE_NAME", item.get("SHORTCITYTYPE_UA", "")),
                street=item.get("STREET_NAME", item.get("STREET_UA", "")),
                street_type_short=item.get("SHORTSTREETTYPE_NAME", ""),
                house_number=item.get("HOUSENUMBER", item.get("HOUSENUMBER_UA", "")),
                old_city=item.get("OLDCITY_NAME", item.get("OLDCITY_UA", "")),
                old_street=item.get("OLDSTREET_NAME", ""),
                city_id=item.get("CITY_ID", ""),
                street_id=item.get("STREET_ID", ""),
            )
            for item in entries
        ]

    def get_cities_by_name(self, city_name: str) -> List[ClassifierCity]:
        entries = self._entries(
            "get_city_by_region_id_and_district_id_and_city_ua",
            {"city_ua": city_name},
        )
        return [
            ClassifierCity(
                region=item.get("REGION_UA", item.get("REGION_NAME", "")),
                district=item.get("DISTRICT_UA", item.get("DISTRICT_NAME", "")),
                city=item.get("CITY_UA", item.get("CITY_NAME", "")),
                city_type_short=item.get("SHORTCITYTYPE_UA", item.get("CITYTYPE_NAME", "")),
                city_id=item.get("CITY_ID", ""),
                population=int(item.get("POPULATION", "0") or "0"),
                old_city=item.get("OLDCITY_UA", item.get("OLDCITY_NAME", "")),
            )
            for item in entries
        ]

    def get_streets_by_name(self, city_id: str, street_name: str) -> List[ClassifierStreet]:
        entries = self._entries(
            "get_street_by_name",
            {"city_id": city_id, "street_name": street_name, "lang": "UA", "fuzzy": "1"},
        )
        return [
            ClassifierStreet(
                region=item.get("REGION_NAME", item.get("REGION_UA", "")),
                district=item.get("DISTRICT_NAME", item.get("DISTRICT_UA", "")),
                city=item.get("CITY_NAME", item.get("CITY_UA", "")),
                city_type_short=item.get("CITYTYPE_NAME", item.get("SHORTCITYTYPE_UA", "")),
                street=item.get("STREET_NAME", item.get("STREET_UA", "")),
                street_type_short=item.get("SHORTSTREETTYPE_NAME", ""),
                city_id=item.get("CITY_ID", ""),
                street_id=item.get("STREET_ID", ""),
                old_street=item.get("OLDSTREET_NAME", ""),
            )
            for item in entries
        ]

    def get_houses_by_street_id(self, street_id: str, house_number: str = "") -> List[tuple]:
        params = {"street_id": street_id}
        if house_number:
            params["housenumber"] = house_number
        entries = self._entries("get_addr_house_by_street_id", params)
        return [
            (
                item.get("HOUSENUMBER_UA", item.get("HOUSENUMBER", "")),
                item.get("POSTCODE", ""),
            )
            for item in entries
        ]

    def get_post_offices_by_city_id(self, city_id: str) -> List[PostOffice]:
        entries = self._entries(
            "get_postoffices_by_postcode_cityid_cityvpzid",
            {"city_id": city_id},
        )
        return [
            PostOffice(
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

    def _entries(self, endpoint: str, params: Dict[str, str]) -> List[Dict[str, str]]:
        if not self.enabled:
            return []
        try:
            xml_text = self._request(endpoint, params)
            root = ET.fromstring(xml_text)
        except (ET.ParseError, HTTPError, URLError, TimeoutError, OSError, ValueError):
            return []
        return [_entry_to_dict(child) for child in root if _strip_ns(child.tag) == "Entry"]

    def _request(self, endpoint: str, params: Dict[str, str]) -> str:
        cache_key = self._cache_key(endpoint, params)
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]

        self._load_disk_cache()
        cached = self._disk_cache.get(cache_key)
        if cached is not None:
            self._memory_cache[cache_key] = cached
            return cached

        url = f"{self.base_url}/{endpoint}?{urlencode(params)}"
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/xml, text/xml;q=0.9, */*;q=0.1",
                "User-Agent": "postal-index-matcher/1.0",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8")

        if not body.lstrip().startswith("<"):
            raise ValueError("Ukrposhta classifier returned non-XML response")

        self._memory_cache[cache_key] = body
        self._disk_cache[cache_key] = body
        self._save_disk_cache()
        return body

    def _load_disk_cache(self) -> None:
        if self._disk_cache_loaded:
            return
        self._disk_cache_loaded = True
        if not os.path.exists(self.cache_path):
            return
        try:
            with open(self.cache_path, "r", encoding="utf-8") as cache_file:
                payload = json.load(cache_file)
            self._disk_cache = dict(payload.get("responses", {}))
        except (OSError, json.JSONDecodeError):
            self._disk_cache = {}

    def _save_disk_cache(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            payload = {"updated_at": int(time.time()), "responses": self._disk_cache}
            with open(self.cache_path, "w", encoding="utf-8") as cache_file:
                json.dump(payload, cache_file, ensure_ascii=False)
        except OSError:
            return

    @staticmethod
    def _cache_key(endpoint: str, params: Dict[str, str]) -> str:
        payload = f"{endpoint}|{urlencode(sorted(params.items()))}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
