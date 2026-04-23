from __future__ import annotations

import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ukrposhta_address_matcher.models import ParsedAddress, StreetCandidate
from ukrposhta_address_matcher.utils import normalize_spaces


class GeminiFallbackClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def normalize_address(self, raw_address: str, postcode: str) -> ParsedAddress | None:
        if not self.api_key:
            return None
        prompt = (
            "Role: експерт з адрес України та перейменувань.\n"
            "Task: перетвори raw_address у classifier-compatible компоненти.\n"
            "Rules: використовуй сучасні українські назви; не вигадуй індекс; "
            "ігноруй ЖК/офіси/службові хвости; якщо не впевнений - повертай порожні поля.\n"
            "Output only JSON:\n"
            '{"region":"","district":"","city":"","street":"","houseNumber":"","apartmentNumber":"","renameHints":[],"confidence":""}\n'
            f"postcode={postcode}\n"
            f"raw_address={raw_address}"
        )
        parsed = self._generate_json(prompt)
        if parsed is None:
            return None
        return ParsedAddress(
            postcode=postcode,
            region=_clean_region(str(parsed.get("region", ""))),
            district=_clean_district(str(parsed.get("district", ""))),
            city=_clean_city(str(parsed.get("city", ""))),
            street=_clean_street(str(parsed.get("street", ""))),
            house_number=_clean_house_number(str(parsed.get("houseNumber", ""))),
            apartment_number=_clean_apartment_number(str(parsed.get("apartmentNumber", ""))),
        )

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
            "якщо впевненого збігу немає - поверни index -1.\n"
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

    def _generate_json(self, prompt: str) -> dict[str, object] | None:
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0},
        }
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.5-flash-lite:generateContent?"
            + urlencode({"key": self.api_key})
        )
        request = Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))

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
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed


def _clean_region(value: str) -> str:
    value = normalize_spaces(value)
    value = re.sub(r"\s+\u043e\u0431\u043b(?:\.|\u0430\u0441\u0442\u044c)?$", "", value, flags=re.IGNORECASE)
    return normalize_spaces(value)


def _clean_district(value: str) -> str:
    value = normalize_spaces(value)
    value = re.sub(r"\s+\u0440\u0430\u0439\u043e\u043d$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+\u0440-\u043d$", "", value, flags=re.IGNORECASE)
    return normalize_spaces(value)


def _clean_city(value: str) -> str:
    value = normalize_spaces(value)
    value = re.sub(
        r"^(\u043c\u0456\u0441\u0442\u043e|\u0441\u0435\u043b\u0438\u0449\u0435|\u0441\u0435\u043b\u043e|\u0441\u043c\u0442\.?|\u043c\.?|\u0441\.?)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return normalize_spaces(value)


def _clean_street(value: str) -> str:
    value = normalize_spaces(value)
    value = re.sub(
        r"^(\u0432\u0443\u043b\u0438\u0446\u044f|\u0432\u0443\u043b\.?|\u043f\u0440\u043e\u0441\u043f\u0435\u043a\u0442|\u043f\u0440\u043e\u0441\u043f\.?|\u043f\u0440\u043e\u0432\u0443\u043b\u043e\u043a|\u043f\u0440\u043e\u0432\.?)\s+",
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
    if not re.fullmatch(r"[0-9][0-9A-Z\u0410-\u042f/-]*", value):
        return ""
    return value
