from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class StructuredAddress:
    postcode: str = ""
    region: str = ""
    district: str = ""
    city: str = ""
    street: str = ""
    house_number: str = ""
    apartment_number: str = ""

    def to_json_dict(self) -> dict[str, str]:
        return {
            "postcode": self.postcode,
            "region": self.region,
            "district": self.district,
            "city": self.city,
            "street": self.street,
            "houseNumber": self.house_number,
            "apartmentNumber": self.apartment_number,
        }


@dataclass(slots=True)
class RegistryRow:
    line_no: int
    raw_line: str
    fields: list[str]

    @property
    def postcode(self) -> str:
        return self.fields[2].strip() if len(self.fields) > 2 else ""

    @property
    def raw_address(self) -> str:
        return self.fields[3].strip() if len(self.fields) > 3 else ""


@dataclass(slots=True)
class RegistryDocument:
    rows: list[RegistryRow]
    encoding: str


@dataclass(slots=True)
class AddressCandidate:
    postcode: str
    region: str
    district: str
    city: str
    city_type_short: str
    city_type_full: str
    street: str
    street_type_short: str
    street_type_full: str
    house_number: str
    old_street: str = ""
    old_city: str = ""
    city_id: str = ""
    street_id: str = ""


@dataclass(slots=True)
class CityCandidate:
    region_id: str
    district_id: str
    city_id: str
    region: str
    district: str
    city: str
    city_type_short: str
    city_type_full: str
    population: int = 0
    old_city: str = ""


@dataclass(slots=True)
class StreetCandidate:
    region_id: str
    district_id: str
    city_id: str
    street_id: str
    region: str
    district: str
    city: str
    city_type_short: str
    city_type_full: str
    street: str
    street_type_short: str
    street_type_full: str
    old_street: str = ""


@dataclass(slots=True)
class MatchResult:
    structured_address: StructuredAddress
    status: str
    deviation_percent: int
    postcode_state: str
    warnings: list[str] = field(default_factory=list)
    candidate_count: int = 0
    input_postcode: str = ""
    resolved_postcode: str = ""
    used_ai: bool = False
    forced_fill: bool = False


@dataclass(slots=True)
class ParsedAddress:
    postcode: str
    region: str = ""
    district: str = ""
    city: str = ""
    street: str = ""
    house_number: str = ""
    apartment_number: str = ""
    extras: list[str] = field(default_factory=list)
