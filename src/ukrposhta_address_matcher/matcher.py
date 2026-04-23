from __future__ import annotations

from collections import Counter

from ukrposhta_address_matcher.ai import GeminiFallbackClient
from ukrposhta_address_matcher.cache import CacheStore
from ukrposhta_address_matcher.classifier import UkrposhtaClassifierClient
from ukrposhta_address_matcher.models import AddressCandidate, MatchResult, ParsedAddress, StructuredAddress, StreetCandidate
from ukrposhta_address_matcher.parser import parse_raw_address
from ukrposhta_address_matcher.utils import normalize_for_compare, normalize_house_number, normalize_house_number_loose


class AddressMatcher:
    def __init__(
        self,
        classifier_client: UkrposhtaClassifierClient,
        cache_store: CacheStore,
        ai_client: GeminiFallbackClient | None = None,
        use_ai: bool = True,
    ) -> None:
        self.classifier_client = classifier_client
        self.cache_store = cache_store
        self.ai_client = ai_client
        self.use_ai = use_ai and ai_client is not None

    def match(self, raw_address: str, input_postcode: str) -> MatchResult:
        cached = self._load_cached_result(raw_address, input_postcode)
        if cached is not None:
            return cached

        parsed = parse_raw_address(raw_address, postcode=input_postcode)
        ai_parsed: ParsedAddress | None = None
        postcode_candidates = self.classifier_client.get_addresses_by_postcode(input_postcode) if input_postcode else []
        postcode_state = "postcode_invalid"
        warnings: list[str] = []
        used_ai = False

        if postcode_candidates:
            best_locked = self._best_from_postcode(parsed, postcode_candidates)
            if best_locked is not None:
                result = self._result_from_candidate(
                    parsed=parsed,
                    candidate=best_locked,
                    status=self._status_from_candidate(parsed, best_locked, locked=True),
                    postcode_state="postcode_verified_locked",
                    warnings=warnings,
                    candidate_count=len(postcode_candidates),
                    input_postcode=input_postcode,
                )
                self._store_cached_result(raw_address, input_postcode, result)
                return result
            refined_locked = self._search_with_locked_postcode(parsed, input_postcode, postcode_candidates, raw_address)
            if refined_locked is not None:
                result = self._result_from_candidate(
                    parsed=parsed,
                    candidate=refined_locked,
                    status=self._status_from_candidate(parsed, refined_locked, locked=True),
                    postcode_state="postcode_verified_locked",
                    warnings=warnings,
                    candidate_count=len(postcode_candidates),
                    input_postcode=input_postcode,
                )
                self._store_cached_result(raw_address, input_postcode, result)
                return result
            postcode_state = "postcode_suspect"
            warnings.append("postcode does not align with parsed city/street/house")
        else:
            warnings.append("postcode not found in classifier")

        expanded_parsed = parsed
        if self.use_ai and (not parsed.city or not parsed.street):
            ai_parsed = self.ai_client.normalize_address(raw_address, input_postcode) if self.ai_client else None
            if ai_parsed:
                expanded_parsed = self._merge_parsed(parsed, ai_parsed)
                used_ai = True
                warnings.append("ai fallback used for normalization")

        recovered = self._search_without_locked_postcode(expanded_parsed, raw_address)
        if recovered is None and self.use_ai and self.ai_client:
            if ai_parsed is None:
                ai_parsed = self.ai_client.normalize_address(raw_address, input_postcode)
            if ai_parsed:
                retry_parsed = self._prefer_ai_parsed(expanded_parsed, ai_parsed)
                if self._parsed_changed(expanded_parsed, retry_parsed):
                    expanded_parsed = retry_parsed
                    used_ai = True
                    if "ai fallback used for normalization" not in warnings:
                        warnings.append("ai fallback used for normalization")
                    if postcode_candidates:
                        recovered = self._search_with_locked_postcode(
                            expanded_parsed,
                            input_postcode,
                            postcode_candidates,
                            raw_address,
                        )
                    if recovered is None:
                        recovered = self._search_without_locked_postcode(expanded_parsed, raw_address)
        if recovered is not None:
            status = "postcode_corrected" if recovered.postcode != input_postcode else "verified_fuzzy"
            result = self._result_from_candidate(
                parsed=expanded_parsed,
                candidate=recovered,
                status=status,
                postcode_state="postcode_corrected" if recovered.postcode != input_postcode else postcode_state,
                warnings=warnings,
                candidate_count=1,
                input_postcode=input_postcode,
            )
            result.used_ai = used_ai
            if used_ai and result.status.startswith("verified"):
                result.status = "ai_assisted_verified"
                result.deviation_percent = min(100, result.deviation_percent + 10)
            self._store_cached_result(raw_address, input_postcode, result)
            return result

        forced_fill = self._forced_fill(expanded_parsed)
        if forced_fill is not None:
            result = self._result_from_candidate(
                parsed=expanded_parsed,
                candidate=forced_fill,
                status="forced_fill_review",
                postcode_state=postcode_state,
                warnings=warnings + ["forced fill used due to missing street or house"],
                candidate_count=1,
                input_postcode=input_postcode,
                forced_fill=True,
            )
            result.used_ai = used_ai
            result.deviation_percent = max(result.deviation_percent, 60)
            self._store_cached_result(raw_address, input_postcode, result)
            return result

        fallback = self._best_guess(postcode_candidates)
        if fallback is None:
            result = MatchResult(
                structured_address=StructuredAddress(
                    postcode=input_postcode,
                    region=expanded_parsed.region or "\u041d\u0435\u0432\u0438\u0437\u043d\u0430\u0447\u0435\u043d\u043e",
                    district=expanded_parsed.district,
                    city=expanded_parsed.city or "\u041d\u0435\u0432\u0438\u0437\u043d\u0430\u0447\u0435\u043d\u043e",
                    street=expanded_parsed.street or "\u0426\u0435\u043d\u0442\u0440\u0430\u043b\u044c\u043d\u0430",
                    house_number=expanded_parsed.house_number or "1",
                    apartment_number=expanded_parsed.apartment_number,
                ),
                status="unresolved_review",
                deviation_percent=100,
                postcode_state=postcode_state,
                warnings=warnings + ["no classifier candidate resolved"],
                candidate_count=len(postcode_candidates),
                input_postcode=input_postcode,
                resolved_postcode=input_postcode,
                used_ai=used_ai,
            )
            self._store_cached_result(raw_address, input_postcode, result)
            return result

        result = self._result_from_candidate(
            parsed=expanded_parsed,
            candidate=fallback,
            status="best_guess_review",
            postcode_state=postcode_state,
            warnings=warnings + ["best guess selected"],
            candidate_count=len(postcode_candidates),
            input_postcode=input_postcode,
        )
        result.deviation_percent = max(result.deviation_percent, 50)
        result.used_ai = used_ai
        self._store_cached_result(raw_address, input_postcode, result)
        return result

    def _merge_parsed(self, base: ParsedAddress, ai_value: ParsedAddress) -> ParsedAddress:
        return ParsedAddress(
            postcode=base.postcode or ai_value.postcode,
            region=base.region or ai_value.region,
            district=base.district or ai_value.district,
            city=base.city or ai_value.city,
            street=base.street or ai_value.street,
            house_number=base.house_number or ai_value.house_number,
            apartment_number=base.apartment_number or ai_value.apartment_number,
            extras=base.extras,
        )

    def _prefer_ai_parsed(self, base: ParsedAddress, ai_value: ParsedAddress) -> ParsedAddress:
        return ParsedAddress(
            postcode=base.postcode or ai_value.postcode,
            region=ai_value.region or base.region,
            district=ai_value.district or base.district,
            city=ai_value.city or base.city,
            street=ai_value.street or base.street,
            house_number=ai_value.house_number or base.house_number,
            apartment_number=base.apartment_number or ai_value.apartment_number,
            extras=base.extras,
        )

    def _parsed_changed(self, left: ParsedAddress, right: ParsedAddress) -> bool:
        return (
            left.region != right.region
            or left.district != right.district
            or left.city != right.city
            or left.street != right.street
            or left.house_number != right.house_number
            or left.apartment_number != right.apartment_number
        )

    def _best_from_postcode(self, parsed: ParsedAddress, candidates: list[AddressCandidate]) -> AddressCandidate | None:
        scored = [(self._score_candidate(parsed, candidate, locked=True), candidate) for candidate in candidates]
        scored.sort(key=lambda item: item[0], reverse=True)
        if not scored:
            return None
        min_score = 90 if parsed.house_number else 60
        if scored[0][0] < min_score:
            return None
        return scored[0][1]

    def _search_without_locked_postcode(self, parsed: ParsedAddress, raw_address: str) -> AddressCandidate | None:
        if not parsed.city:
            return None
        city_candidates = self.classifier_client.get_cities_by_name(parsed.city)
        scored_cities = []
        for city in city_candidates:
            score = 0
            if normalize_for_compare(city.city) == normalize_for_compare(parsed.city):
                score += 45
            elif normalize_for_compare(city.old_city) == normalize_for_compare(parsed.city):
                score += 38
            if parsed.region and normalize_for_compare(city.region) == normalize_for_compare(parsed.region):
                score += 20
            if parsed.district and normalize_for_compare(city.district) == normalize_for_compare(parsed.district):
                score += 15
            score += min(city.population // 100000, 10)
            scored_cities.append((score, city))
        scored_cities.sort(key=lambda item: item[0], reverse=True)

        for _, city in scored_cities[:5]:
            if not parsed.street:
                continue
            streets = self.classifier_client.get_streets_by_name(city.city_id, parsed.street)
            street = self._pick_best_street(parsed, streets)
            if street is None and self.use_ai and self.ai_client and streets:
                street = self.ai_client.select_street_candidate(
                    raw_address=raw_address,
                    postcode=parsed.postcode,
                    parsed_city=parsed.city,
                    parsed_street=parsed.street,
                    candidates=streets,
                )
            if street is None:
                continue
            houses = self.classifier_client.get_houses_by_street_id(street.street_id)
            house = self._pick_best_house(parsed.house_number, houses)
            if house is None and parsed.house_number:
                continue
            chosen_house, chosen_postcode = house if house else self._fallback_house(houses)
            if not chosen_house or not chosen_postcode:
                continue
            return AddressCandidate(
                postcode=chosen_postcode,
                region=street.region,
                district=street.district,
                city=street.city,
                city_type_short=street.city_type_short,
                city_type_full=street.city_type_full,
                street=street.street,
                street_type_short=street.street_type_short,
                street_type_full=street.street_type_full,
                house_number=chosen_house,
                old_street=street.old_street,
                city_id=street.city_id,
                street_id=street.street_id,
            )
        return None

    def _search_with_locked_postcode(
        self,
        parsed: ParsedAddress,
        input_postcode: str,
        postcode_candidates: list[AddressCandidate],
        raw_address: str,
    ) -> AddressCandidate | None:
        if not postcode_candidates:
            return None

        city_groups: dict[str, list[AddressCandidate]] = {}
        for candidate in postcode_candidates:
            city_groups.setdefault(candidate.city_id or f"{candidate.city}|{candidate.district}", []).append(candidate)

        ranked_groups: list[tuple[int, list[AddressCandidate]]] = []
        for group in city_groups.values():
            sample = group[0]
            score = 0
            if parsed.city and normalize_for_compare(sample.city) == normalize_for_compare(parsed.city):
                score += 50
            elif parsed.city and normalize_for_compare(sample.old_city) == normalize_for_compare(parsed.city):
                score += 45
            if parsed.region and normalize_for_compare(sample.region) == normalize_for_compare(parsed.region):
                score += 20
            if parsed.district and normalize_for_compare(sample.district) == normalize_for_compare(parsed.district):
                score += 20
            if not parsed.city:
                score += len(group)
            ranked_groups.append((score, group))
        ranked_groups.sort(key=lambda item: item[0], reverse=True)

        for _, group in ranked_groups[:5]:
            sample = group[0]
            if not sample.city_id or not parsed.street:
                continue
            streets = self.classifier_client.get_streets_by_name(sample.city_id, parsed.street)
            street = self._pick_best_street(parsed, streets)
            if street is None and self.use_ai and self.ai_client and streets:
                street = self.ai_client.select_street_candidate(
                    raw_address=raw_address,
                    postcode=input_postcode,
                    parsed_city=sample.city,
                    parsed_street=parsed.street,
                    candidates=streets,
                )
            if street is None:
                continue
            houses = self.classifier_client.get_houses_by_street_id(street.street_id)
            house = self._pick_best_house(parsed.house_number, houses)
            if house is None:
                if parsed.house_number:
                    fallback_house = self._house_with_same_postcode(houses, input_postcode)
                    if fallback_house is None:
                        continue
                    house = fallback_house
                else:
                    house = self._house_with_same_postcode(houses, input_postcode) or self._fallback_house(houses)
            if not house or not house[0]:
                continue
            if house[1] and house[1] != input_postcode:
                continue
            return AddressCandidate(
                postcode=house[1] or input_postcode,
                region=street.region,
                district=street.district,
                city=street.city,
                city_type_short=street.city_type_short,
                city_type_full=street.city_type_full,
                street=street.street,
                street_type_short=street.street_type_short,
                street_type_full=street.street_type_full,
                house_number=house[0],
                old_street=street.old_street,
                city_id=street.city_id,
                street_id=street.street_id,
            )
        return None

    def _forced_fill(self, parsed: ParsedAddress) -> AddressCandidate | None:
        if not parsed.city:
            return None
        city_candidates = self.classifier_client.get_cities_by_name(parsed.city)
        if not city_candidates:
            return None
        city = city_candidates[0]
        street_names = [parsed.street] if parsed.street else [
            "\u0426\u0435\u043d\u0442\u0440\u0430\u043b\u044c\u043d\u0430",
            "\u0428\u0435\u0432\u0447\u0435\u043d\u043a\u0430",
            "\u0421\u043e\u0431\u043e\u0440\u043d\u0430",
        ]
        seen: list[AddressCandidate] = []
        for name in street_names:
            streets = self.classifier_client.get_streets_by_name(city.city_id, name)
            for street in streets:
                houses = self.classifier_client.get_houses_by_street_id(street.street_id)
                house_number, postcode = self._fallback_house(houses)
                if house_number and postcode:
                    seen.append(
                        AddressCandidate(
                            postcode=postcode,
                            region=street.region,
                            district=street.district,
                            city=street.city,
                            city_type_short=street.city_type_short,
                            city_type_full=street.city_type_full,
                            street=street.street,
                            street_type_short=street.street_type_short,
                            street_type_full=street.street_type_full,
                            house_number=house_number,
                            old_street=street.old_street,
                            city_id=street.city_id,
                            street_id=street.street_id,
                        )
                    )
        if not seen:
            return None
        preferred = [
            item
            for item in seen
            if normalize_for_compare(item.street) == normalize_for_compare("\u0426\u0435\u043d\u0442\u0440\u0430\u043b\u044c\u043d\u0430")
        ]
        if preferred:
            return sorted(preferred, key=lambda item: normalize_house_number(item.house_number))[0]
        grouped = Counter(candidate.street for candidate in seen)
        common_street = grouped.most_common(1)[0][0]
        matches = [item for item in seen if item.street == common_street]
        return sorted(matches, key=lambda item: normalize_house_number(item.house_number))[0]

    def _best_guess(self, postcode_candidates: list[AddressCandidate]) -> AddressCandidate | None:
        if not postcode_candidates:
            return None
        grouped = Counter((candidate.city, candidate.street) for candidate in postcode_candidates)
        (city, street), _ = grouped.most_common(1)[0]
        matches = [candidate for candidate in postcode_candidates if candidate.city == city and candidate.street == street]
        return sorted(matches, key=lambda item: normalize_house_number(item.house_number))[0]

    def _pick_best_street(self, parsed: ParsedAddress, streets: list[StreetCandidate]) -> StreetCandidate | None:
        if not streets:
            return None
        scored = []
        for street in streets:
            score = 0
            if normalize_for_compare(street.street) == normalize_for_compare(parsed.street):
                score += 80
            elif normalize_for_compare(street.old_street) == normalize_for_compare(parsed.street):
                score += 75
            elif self._contains_same_street(street.street, parsed.street):
                score += 70
            elif self._contains_same_street(street.old_street, parsed.street):
                score += 68
            if parsed.city and normalize_for_compare(street.city) == normalize_for_compare(parsed.city):
                score += 20
            scored.append((score, street))
        scored.sort(key=lambda item: item[0], reverse=True)
        if scored and scored[0][0] >= 50:
            return scored[0][1]
        return None

    def _pick_best_house(self, raw_house: str, houses: list[tuple[str, str]]) -> tuple[str, str] | None:
        if not houses or not raw_house:
            return None
        normalized_input = normalize_house_number(raw_house)
        exact = [item for item in houses if normalize_house_number(item[0]) == normalized_input]
        if exact:
            return exact[0]
        loose_input = normalize_house_number_loose(raw_house)
        loose = [item for item in houses if normalize_house_number_loose(item[0]) == loose_input]
        if loose:
            return loose[0]
        stripped = "".join(char for char in normalized_input if char.isdigit() or char == "/")
        near = [
            item
            for item in houses
            if "".join(char for char in normalize_house_number(item[0]) if char.isdigit() or char == "/") == stripped
        ]
        if near:
            return near[0]
        base_input = self._house_base_number(normalized_input)
        same_base = [
            item
            for item in houses
            if self._house_base_number(normalize_house_number(item[0])) == base_input
        ]
        if same_base:
            return sorted(same_base, key=lambda item: normalize_house_number(item[0]))[0]
        return None

    def _fallback_house(self, houses: list[tuple[str, str]]) -> tuple[str, str]:
        if not houses:
            return "", ""
        ordered = sorted(houses, key=lambda item: normalize_house_number(item[0]))
        return ordered[0]

    def _house_with_same_postcode(self, houses: list[tuple[str, str]], postcode: str) -> tuple[str, str] | None:
        matching = [item for item in houses if item[1] == postcode]
        if not matching:
            return None
        return sorted(matching, key=lambda item: normalize_house_number(item[0]))[0]

    def _score_candidate(self, parsed: ParsedAddress, candidate: AddressCandidate, locked: bool) -> int:
        score = 35 if locked else 0
        if parsed.city and normalize_for_compare(candidate.city) == normalize_for_compare(parsed.city):
            score += 25
        elif parsed.city and normalize_for_compare(candidate.old_city) == normalize_for_compare(parsed.city):
            score += 20
        if parsed.street and normalize_for_compare(candidate.street) == normalize_for_compare(parsed.street):
            score += 25
        elif parsed.street and normalize_for_compare(candidate.old_street) == normalize_for_compare(parsed.street):
            score += 22
        elif parsed.street and self._contains_same_street(candidate.street, parsed.street):
            score += 22
        elif parsed.street and self._contains_same_street(candidate.old_street, parsed.street):
            score += 20
        if parsed.house_number and normalize_house_number(candidate.house_number) == normalize_house_number(parsed.house_number):
            score += 15
        elif parsed.house_number and normalize_house_number_loose(candidate.house_number) == normalize_house_number_loose(parsed.house_number):
            score += 15
        elif parsed.house_number:
            house_match = self._pick_best_house(parsed.house_number, [(candidate.house_number, candidate.postcode)])
            if house_match is not None:
                score += 10
        return score

    def _status_from_candidate(self, parsed: ParsedAddress, candidate: AddressCandidate, locked: bool) -> str:
        if candidate.old_street and (
            normalize_for_compare(candidate.old_street) == normalize_for_compare(parsed.street)
            or self._contains_same_street(candidate.old_street, parsed.street)
        ):
            return "verified_old_name"
        if locked:
            return "postcode_verified"
        return "verified_exact"

    def _result_from_candidate(
        self,
        parsed: ParsedAddress,
        candidate: AddressCandidate,
        status: str,
        postcode_state: str,
        warnings: list[str],
        candidate_count: int,
        input_postcode: str,
        forced_fill: bool = False,
    ) -> MatchResult:
        structured = StructuredAddress(
            postcode=candidate.postcode,
            region=candidate.region,
            district=candidate.district,
            city=candidate.city,
            street=candidate.street,
            house_number=candidate.house_number,
            apartment_number=parsed.apartment_number,
        )
        return MatchResult(
            structured_address=structured,
            status=status,
            deviation_percent=self._deviation_percent(parsed, candidate, forced_fill=forced_fill),
            postcode_state=postcode_state,
            warnings=warnings,
            candidate_count=candidate_count,
            input_postcode=input_postcode,
            resolved_postcode=candidate.postcode,
            forced_fill=forced_fill,
        )

    def _deviation_percent(self, parsed: ParsedAddress, candidate: AddressCandidate, forced_fill: bool = False) -> int:
        deviation = 0
        if parsed.postcode and parsed.postcode != candidate.postcode:
            deviation += 35
        if parsed.city and normalize_for_compare(parsed.city) != normalize_for_compare(candidate.city):
            if normalize_for_compare(parsed.city) != normalize_for_compare(candidate.old_city):
                deviation += 25
        if parsed.street and normalize_for_compare(parsed.street) != normalize_for_compare(candidate.street):
            if (
                normalize_for_compare(parsed.street) != normalize_for_compare(candidate.old_street)
                and not self._contains_same_street(candidate.street, parsed.street)
                and not self._contains_same_street(candidate.old_street, parsed.street)
            ):
                deviation += 25
        if parsed.house_number and normalize_house_number(parsed.house_number) != normalize_house_number(candidate.house_number):
            if normalize_house_number_loose(parsed.house_number) != normalize_house_number_loose(candidate.house_number):
                deviation += 15
        if forced_fill:
            deviation = max(deviation, 60)
        return min(100, deviation)

    def _contains_same_street(self, left: str, right: str) -> bool:
        normalized_left = normalize_for_compare(left)
        normalized_right = normalize_for_compare(right)
        if not normalized_left or not normalized_right:
            return False
        return normalized_left in normalized_right or normalized_right in normalized_left

    def _house_base_number(self, value: str) -> str:
        digits = []
        for char in value:
            if char.isdigit():
                digits.append(char)
                continue
            if digits:
                break
        return "".join(digits)

    def _load_cached_result(self, raw_address: str, input_postcode: str) -> MatchResult | None:
        fingerprint = self.cache_store.build_final_fingerprint(raw_address, input_postcode)
        payload = self.cache_store.get_final_result(fingerprint)
        if payload is None:
            return None
        structured = payload["structured_address"]
        return MatchResult(
            structured_address=StructuredAddress(
                postcode=str(structured["postcode"]),
                region=str(structured["region"]),
                district=str(structured["district"]),
                city=str(structured["city"]),
                street=str(structured["street"]),
                house_number=str(structured["houseNumber"]),
                apartment_number=str(structured["apartmentNumber"]),
            ),
            status=str(payload["status"]),
            deviation_percent=int(payload["deviation_percent"]),
            postcode_state=str(payload["postcode_state"]),
            warnings=[str(item) for item in payload.get("warnings", [])],
            candidate_count=int(payload.get("candidate_count", 0)),
            input_postcode=str(payload.get("input_postcode", "")),
            resolved_postcode=str(payload.get("resolved_postcode", "")),
            used_ai=bool(payload.get("used_ai", False)),
            forced_fill=bool(payload.get("forced_fill", False)),
        )

    def _store_cached_result(self, raw_address: str, input_postcode: str, result: MatchResult) -> None:
        fingerprint = self.cache_store.build_final_fingerprint(raw_address, input_postcode)
        self.cache_store.set_final_result(
            fingerprint,
            {
                "structured_address": result.structured_address.to_json_dict(),
                "status": result.status,
                "deviation_percent": result.deviation_percent,
                "postcode_state": result.postcode_state,
                "warnings": result.warnings,
                "candidate_count": result.candidate_count,
                "input_postcode": result.input_postcode,
                "resolved_postcode": result.resolved_postcode,
                "used_ai": result.used_ai,
                "forced_fill": result.forced_fill,
            },
        )
