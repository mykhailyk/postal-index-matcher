from __future__ import annotations

import re

from ukrposhta_address_matcher.models import ParsedAddress
from ukrposhta_address_matcher.utils import (
    CITY_MARKERS,
    extract_apartment,
    normalize_ru_to_ua_tokens,
    normalize_spaces,
    sanitize_extras,
    tokenize_address,
)


HOUSE_PATTERN = re.compile(
    r"\b(?:\u0431\u0443\u0434\.?|\u0431\u0443\u0434\u0438\u043d\u043e\u043a|\u0434\.?|\u0434\u043e\u043c)?\s*([0-9]+[0-9A-Za-z\u0410-\u042f\u0430-\u044f\u0406\u0456\u0407\u0457\u0404\u0454\u0490\u0491/-]*)",
    flags=re.IGNORECASE,
)
POSTCODE_PATTERN = re.compile(r"\b(\d{5})\b")
STREET_PREFIXES = [
    "\u0432\u0443\u043b",
    "\u043f\u0440\u043e\u0441\u043f",
    "\u043f\u0440\u043e\u0432",
    "\u043f\u0440\u0432",
    "\u0443\u0437\u0432",
    "\u0431\u0443\u043b\u044c\u0432\u0430\u0440",
    "\u0448\u043e\u0441\u0435",
    "\u043d\u0430\u0431",
]


def parse_raw_address(raw_address: str, postcode: str = "") -> ParsedAddress:
    cleaned = normalize_ru_to_ua_tokens(raw_address)
    cleaned, extras = sanitize_extras(cleaned)
    cleaned, apartment = extract_apartment(cleaned)
    tokens = tokenize_address(cleaned)

    city = ""
    street = ""
    house_number = ""
    region = ""
    district = ""

    for token in tokens:
        lowered = token.lower()
        if not region and _is_region_token(token):
            region = token.replace("\u043e\u0431\u043b.", "").replace("\u043e\u0431\u043b\u0430\u0441\u0442\u044c", "").strip()
            continue
        if not district and not _is_street_token(token) and _is_district_token(token):
            district = token.replace("\u0440\u0430\u0439\u043e\u043d", "").replace("\u0440-\u043d", "").strip(" ,")
            continue
        if not city and _has_explicit_city_marker(token):
            city = re.sub(
                r"^(\u043c\u0456\u0441\u0442\u043e|\u0441\u0435\u043b\u0438\u0449\u0435|\u0441\u0435\u043b\u043e|\u0441\u043c\u0442\.?|\u043c\.?|\u0441\.?)\s*",
                "",
                token,
                flags=re.IGNORECASE,
            )
            continue

    for token in tokens:
        if not street and _is_street_token(token):
            street = token
            continue
        if not house_number:
            match = HOUSE_PATTERN.search(token)
            if match:
                house_number = match.group(1)

    if not city:
        city, district, region = _parse_location_tail(tokens, city=city, district=district, region=region, street=street)

    if not street:
        for token in tokens:
            if token == city:
                continue
            if any(part in token.lower() for part in ["\u043e\u0431\u043b", "\u0440\u0430\u0439\u043e\u043d", "\u0440-\u043d"]):
                continue
            if token.lower().startswith(("\u043a\u0432", "\u043a\u0432\u0430\u0440\u0442")):
                continue
            if HOUSE_PATTERN.search(token) and len(tokens) == 1:
                continue
            street = token
            break

    if not city:
        for token in reversed(tokens):
            lowered = token.lower()
            if any(prefix in lowered for prefix in STREET_PREFIXES):
                continue
            if HOUSE_PATTERN.search(token):
                continue
            if any(part in lowered for part in ["\u043e\u0431\u043b", "\u0440\u0430\u0439\u043e\u043d", "\u0440-\u043d"]):
                continue
            city = token
            break

    if not house_number:
        match = HOUSE_PATTERN.search(cleaned)
        if match:
            house_number = match.group(1)

    street = _strip_street_prefix(street)
    city = normalize_spaces(city)
    region = normalize_spaces(region)
    district = normalize_spaces(district)
    house_number = normalize_spaces(house_number)
    if house_number:
        house_number = house_number.upper()

    return ParsedAddress(
        postcode=postcode or _extract_postcode(cleaned),
        region=region,
        district=district,
        city=city,
        street=street,
        house_number=house_number,
        apartment_number=apartment,
        extras=extras,
    )


def _extract_postcode(value: str) -> str:
    match = POSTCODE_PATTERN.search(value)
    return match.group(1) if match else ""


def _strip_street_prefix(value: str) -> str:
    value = re.sub(
        r"^(\u0432\u0443\u043b\u0438\u0446\u044f|\u0432\u0443\u043b\.?|\u0443\u043b\u0438\u0446\u0430|\u0443\u043b\.?|\u043f\u0440\u043e\u0441\u043f\u0435\u043a\u0442|\u043f\u0440\u043e\u0441\u043f\.?|\u043f\u0440\u043e\u0432\u0443\u043b\u043e\u043a|\u043f\u0440\u043e\u0432\.?|\u043f\u0440\u0432\.?|\u0431\u0443\u043b\u044c\u0432\u0430\u0440|\u0431\u0443\u043b\.?|\u0443\u0437\u0432\u0456\u0437|\u0448\u043e\u0441\u0435|\u043d\u0430\u0431\u0435\u0440\u0435\u0436\u043d\u0430)[\s.]*",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"(?:,\s*|\s+)(\u0431\u0443\u0434\.?|\u0434\.?)\s*[0-9A-Za-z\u0410-\u042f\u0430-\u044f\u0406\u0456\u0407\u0457\u0404\u0454\u0490\u0491/-]+.*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\s+[0-9]+[0-9A-Za-z\u0410-\u042f\u0430-\u044f\u0406\u0456\u0407\u0457\u0404\u0454\u0490\u0491/-]*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return normalize_spaces(value)


def _parse_location_tail(
    tokens: list[str],
    city: str,
    district: str,
    region: str,
    street: str,
) -> tuple[str, str, str]:
    if city and district and region:
        return city, district, region
    for token in reversed(tokens):
        lowered = token.lower()
        if street and token == street:
            continue
        if any(prefix in lowered for prefix in STREET_PREFIXES):
            continue
        if HOUSE_PATTERN.search(token):
            continue
        cleaned = re.sub(r"^(?:\u043a\u0432\.?|\u043a\u0432\u0430\u0440\u0442\u0438\u0440\u0430)\s*", "", token, flags=re.IGNORECASE)
        cleaned = normalize_spaces(cleaned)
        if not cleaned:
            continue
        words = cleaned.split()
        if not words:
            continue

        local_region = region
        local_district = district
        local_city = city

        if len(words) >= 2 and words[-1].lower() in ("\u043e\u0431\u043b.", "\u043e\u0431\u043b\u0430\u0441\u0442\u044c"):
            local_region = words[-2] if not local_region else local_region
            words = words[:-2]
        elif words[-1].lower().endswith("\u0441\u044c\u043a\u0430") and not local_region:
            local_region = words[-1]
            words = words[:-1]

        if len(words) >= 2 and words[-1].lower() in ("\u0440\u0430\u0439\u043e\u043d", "\u0440-\u043d"):
            local_district = words[-2] if not local_district else local_district
            words = words[:-2]
        elif words and (
            words[-1].lower().endswith("\u0441\u044c\u043a\u0438\u0439")
            or words[-1].lower().endswith("\u0446\u044c\u043a\u0438\u0439")
            or words[-1].lower().endswith("\u0437\u044c\u043a\u0438\u0439")
        ):
            if not local_district:
                local_district = words[-1]
                words = words[:-1]

        if words and not local_city:
            local_city = _collapse_duplicate_tail_words(words)

        if local_city or local_district or local_region:
            return local_city, local_district, local_region

    return city, district, region


def _has_explicit_city_marker(token: str) -> bool:
    return bool(
        re.match(
            r"^\s*(\u043c\u0456\u0441\u0442\u043e|\u0441\u0435\u043b\u0438\u0449\u0435|\u0441\u0435\u043b\u043e|\u0441\u043c\u0442\.?|\u043c\.?|\u0441\.?)\s+",
            token,
            flags=re.IGNORECASE,
        )
    )


def _is_street_token(token: str) -> bool:
    lowered = token.lower().lstrip()
    return any(
        lowered.startswith(prefix)
        or lowered.startswith(f"{prefix}.")
        or lowered.startswith(f"{prefix} ")
        for prefix in STREET_PREFIXES
    )


def _is_region_token(token: str) -> bool:
    lowered = normalize_spaces(token).lower()
    words = lowered.split()
    if "\u043e\u0431\u043b" in lowered:
        return len(words) <= 2
    return len(words) == 1 and words[-1].endswith("\u0441\u044c\u043a\u0430")


def _is_district_token(token: str) -> bool:
    lowered = normalize_spaces(token).lower()
    words = lowered.split()
    if "\u0440\u0430\u0439\u043e\u043d" in lowered or "\u0440-\u043d" in lowered:
        return len(words) <= 2
    if len(words) != 1:
        return False
    last_word = words[-1]
    return (
        last_word.endswith("\u0441\u044c\u043a\u0438\u0439")
        or last_word.endswith("\u0446\u044c\u043a\u0438\u0439")
        or last_word.endswith("\u0437\u044c\u043a\u0438\u0439")
    )


def _collapse_duplicate_tail_words(words: list[str]) -> str:
    if len(words) >= 2 and all(word.lower() == words[0].lower() for word in words):
        return words[0]
    return " ".join(words)
