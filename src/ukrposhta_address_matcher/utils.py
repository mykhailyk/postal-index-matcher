from __future__ import annotations

import json
import re
from collections import Counter

from ukrposhta_address_matcher.models import StructuredAddress


RU_TO_UA_MAP = {
    "\u043e\u0431\u043b\u0430\u0441\u0442\u044c": "\u043e\u0431\u043b\u0430\u0441\u0442\u044c",
    "\u043e\u0431\u043b.": "\u043e\u0431\u043b.",
    "\u0433.": "\u043c.",
    "\u0433\u043e\u0440\u043e\u0434": "\u043c\u0456\u0441\u0442\u043e",
    "\u0443\u043b\u0438\u0446\u0430": "\u0432\u0443\u043b\u0438\u0446\u044f",
    "\u0443\u043b.": "\u0432\u0443\u043b.",
    "\u0434\u043e\u043c": "\u0431\u0443\u0434.",
    "\u0434.": "\u0431\u0443\u0434.",
    "\u043a\u0432.": "\u043a\u0432.",
    "\u043f\u0435\u0440\u0435\u0443\u043b\u043e\u043a": "\u043f\u0440\u043e\u0432\u0443\u043b\u043e\u043a",
    "\u043f\u0440\u043e\u0441\u043f\u0435\u043a\u0442": "\u043f\u0440\u043e\u0441\u043f\u0435\u043a\u0442",
    "\u0448\u043e\u0441\u0441\u0435": "\u0448\u043e\u0441\u0435",
}

CITY_MARKERS = [
    "\u043c\u0456\u0441\u0442\u043e",
    "\u043c.",
    "\u0441\u0435\u043b\u043e",
    "\u0441.",
    "\u0441\u043c\u0442",
    "\u0441\u0435\u043b\u0438\u0449\u0435",
]

EXTRA_PATTERNS = [
    r"\b\u0416\u041a\b.*$",
    r"\b\u043a\u0430\u0431\.?\s*\d+\b.*$",
    r"#\S+",
    r"\b\u043e\u0444\u0456\u0441\b.*$",
    r"\b\u0441\u0435\u043a\u0446(?:\u0456\u044f|\u0438\u044f)?\b.*$",
    r"\b\u043f\u0456\u0434[']?\u0457\u0437\u0434\b.*$",
]


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u00a0", " ")).strip(" ,;")


def normalize_for_compare(value: str) -> str:
    value = normalize_spaces(value).lower().replace("\u0451", "\u0435")
    value = value.replace("\u2019", "'").replace("`", "'")
    value = value.replace("-", "")
    value = re.sub(r"[^\w\u0430-\u0449\u044c\u044e\u044f\u0456\u0457\u0454\u0491']", "", value, flags=re.IGNORECASE)
    return value


def normalize_ru_to_ua_tokens(value: str) -> str:
    result = value
    for source, target in sorted(RU_TO_UA_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        pattern = rf"(?<![\w\u0400-\u04FF]){re.escape(source)}(?![\w\u0400-\u04FF])"
        result = re.sub(pattern, target, result, flags=re.IGNORECASE)
    return normalize_spaces(result)


def normalize_house_number(value: str) -> str:
    value = normalize_spaces(value).upper()
    value = value.replace("-", "")
    value = value.replace(" ", "")
    value = value.replace("\u041a\u041e\u0420\u041f.", "\u041a\u041e\u0420\u041f")
    value = value.replace("\u041a\u041e\u0420\u041f\u0423\u0421", "\u041a\u041e\u0420\u041f")
    return value


def normalize_house_number_loose(value: str) -> str:
    value = normalize_house_number(value)
    return value.replace("/", "")


def sanitize_extras(value: str) -> tuple[str, list[str]]:
    extras: list[str] = []
    cleaned = value
    for pattern in EXTRA_PATTERNS:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            extras.append(match.group(0).strip())
            cleaned = cleaned.replace(match.group(0), " ")
    return normalize_spaces(cleaned), extras


def tokenize_address(value: str) -> list[str]:
    value = normalize_spaces(value)
    parts = re.split(r"[,;]", value)
    return [normalize_spaces(part) for part in parts if normalize_spaces(part)]


def extract_apartment(value: str) -> tuple[str, str]:
    match = re.search(
        r"\b(?:\u043a\u0432\.?|\u043a\u0432\u0430\u0440\u0442\u0438\u0440\u0430)\s*([0-9][0-9A-Za-z\u0410-\u042f\u0430-\u044f\u0406\u0456\u0407\u0457\u0404\u0454\u0490\u0491/-]*)",
        value,
        flags=re.IGNORECASE,
    )
    if not match:
        return value, ""
    apartment = normalize_spaces(match.group(1)).upper()
    cleaned = (value[: match.start()] + " " + value[match.end() :]).strip()
    return normalize_spaces(cleaned), apartment


def choose_most_common(values: list[str]) -> str:
    filtered = [value for value in values if value]
    if not filtered:
        return ""
    return Counter(filtered).most_common(1)[0][0]


def compact_json(address: StructuredAddress) -> str:
    return json.dumps(address.to_json_dict(), ensure_ascii=False, separators=(",", ":"))
