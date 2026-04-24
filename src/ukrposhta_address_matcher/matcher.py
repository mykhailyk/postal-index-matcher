from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
import re

from ukrposhta_address_matcher.ai import GeminiFallbackClient
from ukrposhta_address_matcher.cache import CacheStore
from ukrposhta_address_matcher.classifier import UkrposhtaClassifierClient
from ukrposhta_address_matcher.models import AddressCandidate, MatchResult, ParsedAddress, StructuredAddress, StreetCandidate
from ukrposhta_address_matcher.parser import parse_raw_address
from ukrposhta_address_matcher.stats import RuntimeStats
from ukrposhta_address_matcher.utils import normalize_for_compare, normalize_house_number, normalize_house_number_loose


class AddressMatcher:
    def __init__(
        self,
        classifier_client: UkrposhtaClassifierClient,
        cache_store: CacheStore,
        ai_client: GeminiFallbackClient | None = None,
        use_ai: bool = True,
        stats: RuntimeStats | None = None,
    ) -> None:
        self.classifier_client = classifier_client
        self.cache_store = cache_store
        self.ai_client = ai_client
        self.use_ai = use_ai and ai_client is not None
        self.stats = stats or RuntimeStats()

    def match(self, raw_address: str, input_postcode: str) -> MatchResult:
        cached = self._load_cached_result(raw_address, input_postcode)
        if cached is not None:
            return cached

        parsed = parse_raw_address(raw_address, postcode=input_postcode)
        warnings: list[str] = []
        used_ai = False
        expanded_parsed = parsed
        postcode_candidates = self.classifier_client.get_addresses_by_postcode(input_postcode) if input_postcode else []
        resolved_postcode = input_postcode if postcode_candidates else ""
        postcode_state = "postcode_verified_locked" if postcode_candidates else "postcode_invalid"

        if self.use_ai and (not parsed.city or not parsed.street or not parsed.house_number):
            normalized = self.ai_client.normalize_address(raw_address, input_postcode) if self.ai_client else None
            if normalized:
                expanded_parsed = self._merge_parsed(parsed, normalized)
                used_ai = True
                warnings.append("ai fallback used for normalization")

        if postcode_candidates:
            if parsed.po_box_number:
                result = self._build_po_box_result(expanded_parsed, postcode_candidates, postcode_state, warnings, input_postcode)
                result.used_ai = used_ai
                self._store_cached_result(raw_address, input_postcode, result)
                return result
            else:
                best_locked = self._best_from_postcode(expanded_parsed, postcode_candidates)
                if best_locked is not None:
                    result = self._result_from_candidate(
                        parsed=expanded_parsed,
                        candidate=best_locked,
                        status=self._status_from_candidate(expanded_parsed, best_locked, locked=True),
                        postcode_state="postcode_verified_locked",
                        warnings=warnings,
                        candidate_count=len(postcode_candidates),
                        input_postcode=input_postcode,
                    )
                    result.used_ai = used_ai
                    self._store_cached_result(raw_address, input_postcode, result)
                    return result
                refined_locked = self._search_with_locked_postcode(
                    expanded_parsed,
                    input_postcode,
                    postcode_candidates,
                    raw_address,
                )
                if refined_locked is not None:
                    result = self._result_from_candidate(
                        parsed=expanded_parsed,
                        candidate=refined_locked,
                        status=self._status_from_candidate(expanded_parsed, refined_locked, locked=True),
                        postcode_state="postcode_verified_locked",
                        warnings=warnings,
                        candidate_count=len(postcode_candidates),
                        input_postcode=input_postcode,
                    )
                    result.used_ai = used_ai
                    self._store_cached_result(raw_address, input_postcode, result)
                    return result
                postcode_state = "postcode_suspect"
                warnings.append("postcode does not align with parsed city/street/house")
        else:
            warnings.append("postcode not found in classifier")

        recovered = self._search_without_locked_postcode(expanded_parsed, raw_address)
        if recovered is not None:
            resolved_postcode = recovered.postcode
            postcode_state = self._resolved_postcode_state(input_postcode, recovered.postcode)

        if recovered is None and self.use_ai and self.ai_client:
            repaired = self.ai_client.rescue_postcode(
                raw_address=raw_address,
                parsed=expanded_parsed,
                postcode=input_postcode,
                failure_reason=postcode_state,
            )
            if repaired:
                retry_parsed = self._prefer_ai_parsed(expanded_parsed, repaired)
                if self._parsed_changed(expanded_parsed, retry_parsed) or repaired.postcode != expanded_parsed.postcode:
                    expanded_parsed = retry_parsed
                    used_ai = True
                    warnings.append("ai fallback used for postcode rescue")

                    rescue_postcode_candidates = (
                        self.classifier_client.get_addresses_by_postcode(expanded_parsed.postcode)
                        if expanded_parsed.postcode and expanded_parsed.postcode != input_postcode
                        else []
                    )
                    if rescue_postcode_candidates:
                        rescue_locked = self._best_from_postcode(expanded_parsed, rescue_postcode_candidates)
                        if rescue_locked is None:
                            rescue_locked = self._search_with_locked_postcode(
                                expanded_parsed,
                                expanded_parsed.postcode,
                                rescue_postcode_candidates,
                                raw_address,
                            )
                        if rescue_locked is not None:
                            result = self._result_from_candidate(
                                parsed=expanded_parsed,
                                candidate=rescue_locked,
                                status="postcode_corrected",
                                postcode_state="postcode_ai_resolved",
                                warnings=warnings,
                                candidate_count=len(rescue_postcode_candidates),
                                input_postcode=input_postcode,
                            )
                            result.used_ai = True
                            self._store_cached_result(raw_address, input_postcode, result)
                            return result
                        postcode_candidates = rescue_postcode_candidates
                        resolved_postcode = expanded_parsed.postcode
                        postcode_state = "postcode_ai_resolved"

                    recovered = self._search_without_locked_postcode(expanded_parsed, raw_address)
                    if recovered is not None:
                        resolved_postcode = recovered.postcode
                        postcode_state = self._resolved_postcode_state(input_postcode, recovered.postcode, ai_resolved=True)
        if recovered is not None:
            status = "postcode_corrected" if recovered.postcode != input_postcode else "verified_fuzzy"
            if not input_postcode and recovered.postcode:
                status = "postcode_resolved"
            result = self._result_from_candidate(
                parsed=expanded_parsed,
                candidate=recovered,
                status="ai_assisted_verified" if used_ai and status.startswith("verified") else status,
                postcode_state=postcode_state,
                warnings=warnings,
                candidate_count=1,
                input_postcode=input_postcode,
            )
            result.used_ai = used_ai
            if used_ai and result.status == "postcode_resolved":
                result.deviation_percent = min(100, result.deviation_percent + 10)
            self._store_cached_result(raw_address, input_postcode, result)
            return result

        postcode_for_fallback = resolved_postcode or expanded_parsed.postcode
        if expanded_parsed.po_box_number:
            po_box_candidates = postcode_candidates
            if not po_box_candidates and postcode_for_fallback:
                po_box_candidates = self.classifier_client.get_addresses_by_postcode(postcode_for_fallback)
            result = self._build_po_box_result(
                expanded_parsed,
                po_box_candidates,
                postcode_state if postcode_for_fallback else "postcode_unresolved",
                warnings,
                postcode_for_fallback,
            )
            result.used_ai = used_ai
            self._store_cached_result(raw_address, input_postcode, result)
            return result

        if postcode_for_fallback:
            fallback_candidates = postcode_candidates
            if not fallback_candidates:
                fallback_candidates = self.classifier_client.get_addresses_by_postcode(postcode_for_fallback)
            postcode_candidate_result = self._best_from_postcode_candidates(expanded_parsed, fallback_candidates)
            if postcode_candidate_result is not None:
                result = self._result_from_candidate(
                    parsed=expanded_parsed,
                    candidate=postcode_candidate_result,
                    status="postcode_candidate_review",
                    postcode_state=postcode_state,
                    warnings=warnings + ["resolved from nearest classifier address within postcode candidates"],
                    candidate_count=len(fallback_candidates),
                    input_postcode=input_postcode,
                )
                result.used_ai = used_ai
                self._store_cached_result(raw_address, input_postcode, result)
                return result
            post_office_result = self._build_post_office_fallback_result(
                expanded_parsed,
                fallback_candidates,
                postcode_for_fallback,
                input_postcode,
                postcode_state,
                warnings,
            )
            if post_office_result is not None:
                post_office_result.used_ai = used_ai
                self._store_cached_result(raw_address, input_postcode, post_office_result)
                return post_office_result

        forced_fill = self._forced_fill(expanded_parsed)
        if forced_fill is not None:
            result = self._result_from_candidate(
                parsed=expanded_parsed,
                candidate=forced_fill,
                status="forced_fill_review",
                postcode_state=postcode_state if postcode_for_fallback else "postcode_unresolved",
                warnings=warnings + ["forced fill used due to missing street or house"],
                candidate_count=1,
                input_postcode=input_postcode,
                forced_fill=True,
            )
            result.used_ai = used_ai
            result.deviation_percent = max(result.deviation_percent, 60)
            self._store_cached_result(raw_address, input_postcode, result)
            return result

        result = self._build_unresolved_result(
            parsed=expanded_parsed,
            warnings=warnings + ["no classifier candidate resolved"],
            input_postcode=input_postcode,
            postcode_for_fallback=postcode_for_fallback,
            postcode_state="postcode_unresolved" if not postcode_for_fallback else postcode_state,
            candidate_count=len(postcode_candidates),
            used_ai=used_ai,
        )
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
            po_box_number=base.po_box_number or ai_value.po_box_number,
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
            po_box_number=base.po_box_number or ai_value.po_box_number,
        )

    def _parsed_changed(self, left: ParsedAddress, right: ParsedAddress) -> bool:
        return (
            left.region != right.region
            or left.district != right.district
            or left.city != right.city
            or left.street != right.street
            or left.house_number != right.house_number
            or left.apartment_number != right.apartment_number
            or left.postcode != right.postcode
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
        scored_cities = self._rank_city_candidates(parsed)

        for _, city in scored_cities[:5]:
            if not parsed.street:
                continue
            streets = self._get_street_candidates(city.city_id, parsed.street)
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
            houses = self._get_candidate_houses(street.street_id, parsed.house_number)
            house = self._pick_best_house(parsed.house_number, houses)
            if house is None and parsed.house_number:
                house = self._pick_nearest_house(parsed.house_number, houses)
                if house is None:
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
            streets = self._get_street_candidates(sample.city_id, parsed.street)
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
            houses = self._get_candidate_houses(street.street_id, parsed.house_number)
            house = self._pick_best_house(parsed.house_number, houses)
            if house is None:
                if parsed.house_number:
                    house = self._pick_nearest_house(parsed.house_number, houses, postcode=input_postcode)
                    if house is None:
                        continue
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

    def _get_candidate_houses(self, street_id: str, house_number: str) -> list[tuple[str, str]]:
        if not house_number:
            return self.classifier_client.get_houses_by_street_id(street_id)
        houses = self.classifier_client.get_houses_by_street_id(street_id, house_number=house_number)
        if houses:
            return houses
        return self.classifier_client.get_houses_by_street_id(street_id)

    def _forced_fill(self, parsed: ParsedAddress) -> AddressCandidate | None:
        if not parsed.city or parsed.po_box_number:
            return None
        if parsed.street and parsed.house_number:
            return None
        scored_cities = self._rank_city_candidates(parsed)
        if not scored_cities:
            return None
        preferred_names = [
            "\u0426\u0435\u043d\u0442\u0440\u0430\u043b\u044c\u043d\u0430",
            "\u0428\u0435\u0432\u0447\u0435\u043d\u043a\u0430",
            "\u0421\u043e\u0431\u043e\u0440\u043d\u0430",
            "\u041c\u043e\u043b\u043e\u0434\u0456\u0436\u043d\u0430",
            "\u041f\u043e\u043b\u044c\u043e\u0432\u0430",
            "\u041c\u0438\u0440\u043d\u0430",
        ]
        street_names = self._dedupe_strings(([parsed.street] if parsed.street else []) + preferred_names)

        for _, city in scored_cities[:5]:
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
                continue
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
        return None

    def _best_guess(self, postcode_candidates: list[AddressCandidate]) -> AddressCandidate | None:
        if not postcode_candidates:
            return None
        grouped = Counter((candidate.city, candidate.street) for candidate in postcode_candidates)
        (city, street), _ = grouped.most_common(1)[0]
        matches = [candidate for candidate in postcode_candidates if candidate.city == city and candidate.street == street]
        return sorted(matches, key=lambda item: normalize_house_number(item.house_number))[0]

    def _best_from_postcode_candidates(self, parsed: ParsedAddress, candidates: list[AddressCandidate]) -> AddressCandidate | None:
        if not candidates or not parsed.street:
            return None
        groups: dict[str, list[AddressCandidate]] = {}
        for candidate in candidates:
            key = candidate.street_id or f"{candidate.city_id}|{candidate.street}"
            groups.setdefault(key, []).append(candidate)

        scored: list[tuple[int, AddressCandidate]] = []
        for group in groups.values():
            sample = group[0]
            city_score = self._score_po_box_candidate(parsed, sample)
            if parsed.city and city_score < 35:
                continue
            street_score = max(
                self._street_match_score(sample.street, parsed.street),
                max(0, self._street_match_score(sample.old_street, parsed.street) - 5),
                self._street_token_overlap_score(sample.street, parsed.street),
                max(0, self._street_token_overlap_score(sample.old_street, parsed.street) - 3),
            )
            if street_score < 12:
                continue
            chosen = sample
            score = city_score + street_score
            if parsed.house_number:
                houses = [(candidate.house_number, candidate.postcode) for candidate in group if candidate.house_number]
                best_house = self._pick_best_house(parsed.house_number, houses)
                if best_house is None:
                    best_house = self._pick_nearest_house(parsed.house_number, houses, postcode=sample.postcode)
                if best_house is None:
                    continue
                for candidate in group:
                    if candidate.house_number == best_house[0] and candidate.postcode == best_house[1]:
                        chosen = candidate
                        break
                if normalize_house_number_loose(best_house[0]) == normalize_house_number_loose(parsed.house_number):
                    score += 20
                else:
                    score += 10
            scored.append((score, chosen))

        if not scored:
            return None
        scored.sort(key=lambda item: item[0], reverse=True)
        if scored[0][0] < 55:
            return None
        return scored[0][1]

    def _should_use_best_guess(self, parsed: ParsedAddress) -> bool:
        return not parsed.po_box_number and not parsed.street and not parsed.house_number

    def _pick_best_street(self, parsed: ParsedAddress, streets: list[StreetCandidate]) -> StreetCandidate | None:
        if not streets:
            return None
        scored = []
        for street in streets:
            score = 0
            score += self._street_match_score(street.street, parsed.street)
            score = max(score, self._street_match_score(street.old_street, parsed.street) - 5)
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
        if "/" in normalized_input or any(char.isalpha() for char in normalized_input):
            return None
        base_input = self._house_base_number(normalized_input)
        same_base = [
            item
            for item in houses
            if self._house_base_number(normalize_house_number(item[0])) == base_input
        ]
        if same_base:
            return sorted(same_base, key=lambda item: normalize_house_number(item[0]))[0]
        return None

    def _pick_nearest_house(
        self,
        raw_house: str,
        houses: list[tuple[str, str]],
        postcode: str = "",
    ) -> tuple[str, str] | None:
        if not raw_house or not houses:
            return None
        filtered = [item for item in houses if not postcode or item[1] == postcode]
        if not filtered:
            filtered = houses
        input_metrics = self._house_metrics(raw_house)
        if input_metrics is None:
            return None
        ranked: list[tuple[tuple[int, int, str], tuple[str, str]]] = []
        for house in filtered:
            candidate_metrics = self._house_metrics(house[0])
            if candidate_metrics is None:
                continue
            ranked.append((self._house_distance(input_metrics, candidate_metrics), house))
        if not ranked:
            return None
        ranked.sort(key=lambda item: item[0])
        return ranked[0][1]

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
        if parsed.street:
            score += max(
                self._street_match_score(candidate.street, parsed.street) // 3,
                max(0, self._street_match_score(candidate.old_street, parsed.street) - 5) // 3,
            )
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
            self._street_match_score(candidate.old_street, parsed.street) >= 52
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
        result_warnings = list(warnings)
        if (
            parsed.house_number
            and candidate.house_number
            and normalize_house_number_loose(parsed.house_number) != normalize_house_number_loose(candidate.house_number)
        ):
            result_warnings.append("nearest available house used")
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
            warnings=result_warnings,
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
                self._street_match_score(candidate.street, parsed.street) < 52
                and self._street_match_score(candidate.old_street, parsed.street) < 52
            ):
                deviation += 25
        if parsed.house_number and normalize_house_number(parsed.house_number) != normalize_house_number(candidate.house_number):
            if normalize_house_number_loose(parsed.house_number) != normalize_house_number_loose(candidate.house_number):
                deviation += 15
        if forced_fill:
            deviation = max(deviation, 60)
        return min(100, deviation)

    def _contains_same_street(self, left: str, right: str) -> bool:
        return self._street_match_score(left, right) >= 52

    def _rank_city_candidates(self, parsed: ParsedAddress) -> list[tuple[int, object]]:
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
        return scored_cities

    def _dedupe_strings(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalized = normalize_for_compare(value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(value)
        return result

    def _house_base_number(self, value: str) -> str:
        digits = []
        for char in value:
            if char.isdigit():
                digits.append(char)
                continue
            if digits:
                break
        return "".join(digits)

    def _house_metrics(self, value: str) -> tuple[int, str, str] | None:
        normalized = normalize_house_number(value)
        number_match = re.match(r"^(\d+)(.*)$", normalized)
        if not number_match:
            return None
        suffix = number_match.group(2)
        return int(number_match.group(1)), suffix.replace("/", ""), normalized

    def _house_distance(
        self,
        left: tuple[int, str, str],
        right: tuple[int, str, str],
    ) -> tuple[int, int, str]:
        number_gap = abs(left[0] - right[0])
        suffix_gap = abs(len(left[1]) - len(right[1]))
        lexical = right[2]
        return number_gap, suffix_gap, lexical

    def _resolved_postcode_state(self, input_postcode: str, resolved_postcode: str, ai_resolved: bool = False) -> str:
        if ai_resolved:
            return "postcode_ai_resolved"
        if not input_postcode and resolved_postcode:
            return "postcode_resolved"
        if input_postcode and resolved_postcode and input_postcode != resolved_postcode:
            return "postcode_corrected"
        if input_postcode and resolved_postcode == input_postcode:
            return "postcode_verified_locked"
        return "postcode_unresolved"

    def _build_post_office_fallback_result(
        self,
        parsed: ParsedAddress,
        postcode_candidates: list[AddressCandidate],
        postcode: str,
        input_postcode: str,
        postcode_state: str,
        warnings: list[str],
    ) -> MatchResult | None:
        if not postcode:
            return None
        office_context = self._resolve_post_office_context(parsed, postcode_candidates)
        if office_context is None:
            return None
        office, region, district, city = office_context
        office_street, office_house = self._normalize_post_office_address(office)
        structured = StructuredAddress(
            postcode=postcode,
            region=region,
            district=district,
            city=city or office.city,
            street=office_street,
            house_number=office_house,
            apartment_number="",
        )
        return MatchResult(
            structured_address=structured,
            status="postcode_anchor_review",
            deviation_percent=55,
            postcode_state=postcode_state,
            warnings=warnings + ["classifier street unresolved; post office address used for resolved postcode"],
            candidate_count=len(postcode_candidates),
            input_postcode=input_postcode,
            resolved_postcode=postcode,
        )

    def _resolve_post_office_context(
        self,
        parsed: ParsedAddress,
        postcode_candidates: list[AddressCandidate],
    ):
        city_id = ""
        region = parsed.region
        district = parsed.district
        city = parsed.city
        postcode = parsed.postcode
        if postcode_candidates:
            best = max(postcode_candidates, key=lambda candidate: self._score_po_box_candidate(parsed, candidate))
            city_id = best.city_id
            region = best.region or region
            district = best.district or district
            city = best.city or city
            postcode = best.postcode or postcode
        if not city_id and parsed.city:
            ranked = self._rank_city_candidates(parsed)
            if ranked:
                best_city = ranked[0][1]
                city_id = best_city.city_id
                region = best_city.region or region
                district = best_city.district or district
                city = best_city.city or city
        if not city_id:
            return None
        offices = self.classifier_client.get_post_offices_by_city_id(city_id)
        office = self._pick_post_office(offices, postcode)
        if office is None:
            return None
        return office, region, district, city

    def _pick_post_office(self, offices, postcode: str):
        active = [item for item in offices if item.lock_code == "0" and not item.is_security and item.street]
        matching = [item for item in active if item.postcode == postcode]
        if matching:
            return sorted(matching, key=lambda item: (item.street, normalize_house_number(item.house_number)))[0]
        if active:
            return sorted(active, key=lambda item: (item.postcode != postcode, item.street, normalize_house_number(item.house_number)))[0]
        return None

    def _build_unresolved_result(
        self,
        parsed: ParsedAddress,
        warnings: list[str],
        input_postcode: str,
        postcode_for_fallback: str,
        postcode_state: str,
        candidate_count: int,
        used_ai: bool,
    ) -> MatchResult:
        return MatchResult(
            structured_address=StructuredAddress(
                postcode=postcode_for_fallback,
                region=parsed.region,
                district=parsed.district,
                city=parsed.city,
                street=parsed.street,
                house_number=parsed.house_number,
                apartment_number=parsed.apartment_number,
            ),
            status="unresolved_review",
            deviation_percent=100,
            postcode_state=postcode_state,
            warnings=warnings,
            candidate_count=candidate_count,
            input_postcode=input_postcode,
            resolved_postcode=postcode_for_fallback if postcode_state != "postcode_unresolved" else "",
            used_ai=used_ai,
        )

    def _get_street_candidates(self, city_id: str, street_name: str) -> list[StreetCandidate]:
        seen_ids: set[str] = set()
        collected: list[StreetCandidate] = []
        for variant in self._street_query_variants(street_name):
            streets = self.classifier_client.get_streets_by_name(city_id, variant)
            for street in streets:
                key = street.street_id or f"{street.street}|{street.old_street}"
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                collected.append(street)
            if collected:
                break
        return collected

    def _score_po_box_candidate(self, parsed: ParsedAddress, candidate: AddressCandidate) -> int:
        score = 0
        if parsed.city and normalize_for_compare(candidate.city) == normalize_for_compare(parsed.city):
            score += 40
        elif parsed.city and normalize_for_compare(candidate.old_city) == normalize_for_compare(parsed.city):
            score += 35
        if parsed.region and normalize_for_compare(candidate.region) == normalize_for_compare(parsed.region):
            score += 20
        if parsed.district and normalize_for_compare(candidate.district) == normalize_for_compare(parsed.district):
            score += 20
        return score

    def _street_token_overlap_score(self, left: str, right: str) -> int:
        left_tokens = self._street_tokens(left)
        right_tokens = self._street_tokens(right)
        if not left_tokens or not right_tokens:
            return 0
        overlap = left_tokens & right_tokens
        if not overlap:
            return 0
        return min(24, len(overlap) * 18)

    def _street_tokens(self, value: str) -> set[str]:
        raw_parts = re.split(r"[\s,./()\\-]+", value.lower())
        tokens: set[str] = set()
        for part in raw_parts:
            normalized_part = normalize_for_compare(part)
            if not normalized_part:
                continue
            if len(normalized_part) >= 3 or normalized_part in {"упа", "оун"}:
                tokens.add(normalized_part)
        return tokens

    def _build_po_box_result(
        self,
        parsed: ParsedAddress,
        postcode_candidates: list[AddressCandidate],
        postcode_state: str,
        warnings: list[str],
        input_postcode: str,
    ) -> MatchResult:
        office_context = self._resolve_post_office_context(parsed, postcode_candidates)
        if office_context is not None:
            office, region, district, city = office_context
            resolved_postcode = input_postcode or parsed.postcode or office.postcode
            office_street, office_house = self._normalize_post_office_address(office)
            return MatchResult(
                structured_address=StructuredAddress(
                    postcode=resolved_postcode,
                    region=region,
                    district=district,
                    city=city or office.city,
                    street=office_street,
                    house_number=office_house,
                    apartment_number="",
                ),
                status="po_box_review",
                deviation_percent=10 if postcode_candidates else 35,
                postcode_state=postcode_state,
                warnings=warnings + ["po box mapped to post office address"],
                candidate_count=len(postcode_candidates),
                input_postcode=input_postcode,
                resolved_postcode=resolved_postcode,
            )
        return MatchResult(
            structured_address=StructuredAddress(
                postcode=input_postcode or parsed.postcode,
                region=parsed.region,
                district=parsed.district,
                city=parsed.city,
                street="А/С",
                house_number=parsed.po_box_number,
                apartment_number="",
            ),
            status="po_box_review",
            deviation_percent=10 if postcode_candidates else 35,
            postcode_state=postcode_state,
            warnings=warnings + ["po box preserved; post office address not resolved"],
            candidate_count=len(postcode_candidates),
            input_postcode=input_postcode,
            resolved_postcode=input_postcode or parsed.postcode,
        )

    def _normalize_post_office_address(self, office) -> tuple[str, str]:
        parsed = parse_raw_address(office.street, postcode=office.postcode)
        street = parsed.street or office.street
        house_number = office.house_number or parsed.house_number or "1"
        return street, house_number

    def _street_match_score(self, left: str, right: str) -> int:
        normalized_left = normalize_for_compare(left)
        normalized_right = normalize_for_compare(right)
        if not normalized_left or not normalized_right:
            return 0
        if normalized_left == normalized_right:
            return 80
        if self._street_signature(left) == self._street_signature(right):
            return 74
        if normalized_left in normalized_right or normalized_right in normalized_left:
            return 70
        ratio = SequenceMatcher(None, normalized_left, normalized_right).ratio()
        if ratio >= 0.9:
            return 68
        if ratio >= 0.82:
            return 60
        if ratio >= 0.75:
            return 52
        return 0

    def _street_signature(self, value: str) -> tuple[str, ...]:
        words = [normalize_for_compare(item) for item in value.replace("-", " ").split()]
        return tuple(sorted(word for word in words if word))

    def _street_query_variants(self, street_name: str) -> list[str]:
        variants = self._dedupe_strings([street_name])
        parts = street_name.split()
        if len(parts) >= 2:
            variants = self._dedupe_strings(variants + [" ".join(reversed(parts))])
        if street_name.endswith("а"):
            variants = self._dedupe_strings(variants + [f"{street_name[:-1]}у"])
        if street_name.endswith("я"):
            variants = self._dedupe_strings(variants + [f"{street_name[:-1]}ю"])
        return variants

    def _load_cached_result(self, raw_address: str, input_postcode: str) -> MatchResult | None:
        self.stats.final_cache_lookups += 1
        fingerprint = self.cache_store.build_final_fingerprint(raw_address, input_postcode)
        payload = self.cache_store.get_final_result(fingerprint)
        if payload is None:
            return None
        self.stats.final_cache_hits += 1
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
