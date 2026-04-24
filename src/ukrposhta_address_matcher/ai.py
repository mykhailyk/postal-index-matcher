from __future__ import annotations

from http.client import IncompleteRead
import json
import re
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ukrposhta_address_matcher.models import ParsedAddress, StreetCandidate
from ukrposhta_address_matcher.utils import normalize_spaces


class GeminiFallbackClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.max_retries = 3
        self.min_request_interval_seconds = 0.35
        self._last_request_at = 0.0
        self.models = ("gemini-2.5-flash", "gemini-2.5-flash-lite")

    def normalize_address(self, raw_address: str, postcode: str) -> ParsedAddress | None:
        if not self.api_key:
            return None
        prompt = (
            "Role: експерт з адрес України та перейменувань.\n"
            "Task: перетвори raw_address у classifier-compatible компоненти.\n"
            "Rules: використовуй сучасні українські назви; не вигадуй індекс; "
            "ігноруй ЖК, офіси, службові хвости; нормалізуй російські форми; "
            "якщо вулиця названа на честь людини, зберігай природний порядок слів; "
            "якщо не впевнений, повертай порожнє поле.\n"
            "Examples:\n"
            "raw=ул Кирилловская, 69-В, комната 117, місто Київ\n"
            'json={"postcode":"","region":"","district":"","city":"Київ","street":"Кирилівська","houseNumber":"69-В","apartmentNumber":"117","confidence":92}\n'
            "raw=вул.Комінтерна, 41, м.Васильків, Київська область\n"
            'json={"postcode":"","region":"Київська","district":"","city":"Васильків","street":"Комінтерна","houseNumber":"41","apartmentNumber":"","confidence":86}\n'
            "Output only JSON:\n"
            '{"postcode":"","region":"","district":"","city":"","street":"","houseNumber":"","apartmentNumber":"","confidence":0}\n'
            f"postcode={postcode}\n"
            f"raw_address={raw_address}"
        )
        parsed = self._generate_json(prompt)
        if parsed is None:
            return None
        return self._to_parsed_address(parsed, fallback_postcode=postcode)

    def rescue_postcode(
        self,
        raw_address: str,
        parsed: ParsedAddress,
        postcode: str,
        failure_reason: str,
    ) -> ParsedAddress | None:
        if not self.api_key:
            return None
        prompt = (
            "Role: експерт з адрес України та індексів Укрпошти.\n"
            "Task: якщо classifier lookup не знайшов індекс, спробуй виправити адресу для пошуку "
            "або запропонувати найкращий postcode guess.\n"
            "Rules: не вигадуй область чи місто без підстав; пріоритет - знайти індекс; "
            "можна виправляти відмінки, старі назви, порядок слів, російські форми; "
            "якщо не впевнений, залиш postcode порожнім; "
            "якщо знаєш перейменування, збережи сучасну назву в street і стару логіку врахуй неявно.\n"
            "Examples:\n"
            "raw=коминтерна 41 васильков киевская обл\n"
            'json={"postcode":"08602","region":"Київська","district":"","city":"Васильків","street":"Гончарна","houseNumber":"41","apartmentNumber":"","confidence":83,"notes":"Комінтерна -> Гончарна"}\n'
            "raw=ул кирилловская 69-в киев\n"
            'json={"postcode":"04080","region":"","district":"","city":"Київ","street":"Кирилівська","houseNumber":"69-В","apartmentNumber":"","confidence":79,"notes":"російська форма"}\n'
            "Output only JSON:\n"
            '{"postcode":"","region":"","district":"","city":"","street":"","houseNumber":"","apartmentNumber":"","confidence":0,"notes":""}\n'
            f"input_postcode={postcode}\n"
            f"failure_reason={failure_reason}\n"
            f"parsed_region={parsed.region}\n"
            f"parsed_district={parsed.district}\n"
            f"parsed_city={parsed.city}\n"
            f"parsed_street={parsed.street}\n"
            f"parsed_house={parsed.house_number}\n"
            f"parsed_apartment={parsed.apartment_number}\n"
            f"raw_address={raw_address}"
        )
        repaired = self._generate_json(prompt)
        if repaired is None:
            return None
        return self._to_parsed_address(repaired, fallback_postcode=postcode)

    def select_street_candidate(
        self,
        raw_address: str,
        postcode: str,
        parsed_city: str,
        parsed_street: str,
        candidates: list[StreetCandidate],
    ) -> StreetCandidate | None:
        if not self.api_key or not candidates:
            return None
        limited = candidates[:20]
        candidate_lines = []
        for idx, candidate in enumerate(limited):
            candidate_lines.append(
                json.dumps(
                    {
                        "index": idx,
                        "city": candidate.city,
                        "district": candidate.district,
                        "region": candidate.region,
                        "street": candidate.street,
                        "old_street": candidate.old_street,
                        "street_type": candidate.street_type_full,
                    },
                    ensure_ascii=False,
                )
            )
        prompt = (
            "Role: експерт з адрес України та перейменувань.\n"
            "Task: вибери найкращий classifier street candidate для вхідної адреси.\n"
            "Rules: використовуй лише надані candidates; old_street може бути старою назвою; "
            "якщо впевненого збігу немає, поверни index -1.\n"
            "Output only JSON:\n"
            '{"index":-1,"confidence":0,"reason":""}\n'
            f"postcode={postcode}\n"
            f"parsed_city={parsed_city}\n"
            f"parsed_street={parsed_street}\n"
            f"raw_address={raw_address}\n"
            "candidates:\n"
            + "\n".join(candidate_lines)
        )
        response = self._generate_json(prompt)
        if response is None:
            return None
        try:
            index = int(response.get("index", -1))
            confidence = int(response.get("confidence", 0))
        except (TypeError, ValueError):
            return None
        if index < 0 or index >= len(limited) or confidence < 50:
            return None
        return limited[index]

    def _to_parsed_address(self, payload: dict[str, object], fallback_postcode: str) -> ParsedAddress:
        return ParsedAddress(
            postcode=_clean_postcode(str(payload.get("postcode", ""))) or fallback_postcode,
            region=_clean_region(str(payload.get("region", ""))),
            district=_clean_district(str(payload.get("district", ""))),
            city=_clean_city(str(payload.get("city", ""))),
            street=_clean_street(str(payload.get("street", ""))),
            house_number=_clean_house_number(str(payload.get("houseNumber", ""))),
            apartment_number=_clean_apartment_number(str(payload.get("apartmentNumber", ""))),
        )

    def _generate_json(self, prompt: str) -> dict[str, object] | None:
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0},
        }
        for model_name in self.models:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model_name}:generateContent?"
                + urlencode({"key": self.api_key})
            )
            request = Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            payload: dict[str, object] | None = None
            for attempt in range(self.max_retries):
                try:
                    self._wait_for_request_slot()
                    with urlopen(request, timeout=60) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                    self._last_request_at = time.monotonic()
                    break
                except HTTPError as error:
                    if error.code == 404:
                        payload = None
                        break
                    if error.code not in (429, 500, 502, 503, 504) or attempt + 1 >= self.max_retries:
                        payload = None
                        break
                    time.sleep(1.5 * (attempt + 1))
                except (URLError, TimeoutError, socket.timeout, IncompleteRead):
                    if attempt + 1 >= self.max_retries:
                        payload = None
                        break
                    time.sleep(1.5 * (attempt + 1))
            if payload is None:
                continue

            text = ""
            for candidate in payload.get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    if "text" in part:
                        text += part["text"]
            text = text.strip().strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    def _wait_for_request_slot(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.min_request_interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)


def _clean_postcode(value: str) -> str:
    value = normalize_spaces(value)
    match = re.search(r"\b\d{5}\b", value)
    return match.group(0) if match else ""


def _clean_region(value: str) -> str:
    value = normalize_spaces(value)
    value = re.sub(r"\s+обл(?:\.|асть)?$", "", value, flags=re.IGNORECASE)
    return normalize_spaces(value)


def _clean_district(value: str) -> str:
    value = normalize_spaces(value)
    value = re.sub(r"\s+район$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+р-н$", "", value, flags=re.IGNORECASE)
    return normalize_spaces(value)


def _clean_city(value: str) -> str:
    value = normalize_spaces(value)
    value = re.sub(
        r"^(місто|селище|село|смт\.?|м\.?|с\.?)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return normalize_spaces(value)


def _clean_street(value: str) -> str:
    value = normalize_spaces(value)
    value = re.sub(
        r"^(вулиця|вул\.?|улица|ул\.?|проспект|просп\.?|провулок|пров\.?)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return normalize_spaces(value)


def _clean_house_number(value: str) -> str:
    return normalize_spaces(value).upper()


def _clean_apartment_number(value: str) -> str:
    value = normalize_spaces(value).upper()
    if not value:
        return ""
    if not re.fullmatch(r"[0-9][0-9A-ZА-ЯІЇЄҐ/-]*", value):
        return ""
    return value
