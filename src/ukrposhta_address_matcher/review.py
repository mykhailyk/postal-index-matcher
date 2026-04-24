from __future__ import annotations

from datetime import datetime, timezone
import csv
import io
import json
from pathlib import Path
from typing import Callable
from uuid import uuid4

from ukrposhta_address_matcher.cache import CacheStore
from ukrposhta_address_matcher.classifier import UkrposhtaClassifierClient
from ukrposhta_address_matcher.config import Settings
from ukrposhta_address_matcher.models import (
    AddressCandidate,
    MatchResult,
    ParsedAddress,
    PostOfficeCandidate,
    RegistryRow,
    StructuredAddress,
)
from ukrposhta_address_matcher.parser import parse_raw_address
from ukrposhta_address_matcher.registry import read_registry, write_registry
from ukrposhta_address_matcher.service import _run_batch_matches
from ukrposhta_address_matcher.utils import normalize_for_compare, normalize_house_number


AUTO_ACCEPT_STATUSES = {"ai_assisted_verified", "verified_fuzzy", "postcode_resolved", "postcode_corrected"}
HARD_STOP_STATUSES = {
    "postcode_anchor_review",
    "postcode_candidate_review",
    "forced_fill_review",
    "unresolved_review",
    "po_box_review",
}
REVIEW_DATA_VERSION = 1


def structured_address_to_dict(address: StructuredAddress) -> dict[str, str]:
    return address.to_json_dict()


def structured_address_from_dict(payload: dict[str, object]) -> StructuredAddress:
    return StructuredAddress(
        postcode=str(payload.get("postcode", "")),
        region=str(payload.get("region", "")),
        district=str(payload.get("district", "")),
        city=str(payload.get("city", "")),
        street=str(payload.get("street", "")),
        house_number=str(payload.get("houseNumber", "")),
        apartment_number=str(payload.get("apartmentNumber", "")),
    )


def match_result_to_dict(result: MatchResult) -> dict[str, object]:
    return {
        "structured_address": structured_address_to_dict(result.structured_address),
        "status": result.status,
        "deviation_percent": result.deviation_percent,
        "postcode_state": result.postcode_state,
        "warnings": list(result.warnings),
        "candidate_count": result.candidate_count,
        "input_postcode": result.input_postcode,
        "resolved_postcode": result.resolved_postcode,
        "used_ai": result.used_ai,
        "forced_fill": result.forced_fill,
    }


def match_result_from_dict(payload: dict[str, object]) -> MatchResult:
    return MatchResult(
        structured_address=structured_address_from_dict(dict(payload.get("structured_address", {}))),
        status=str(payload.get("status", "")),
        deviation_percent=int(payload.get("deviation_percent", 0)),
        postcode_state=str(payload.get("postcode_state", "")),
        warnings=[str(item) for item in payload.get("warnings", [])],
        candidate_count=int(payload.get("candidate_count", 0)),
        input_postcode=str(payload.get("input_postcode", "")),
        resolved_postcode=str(payload.get("resolved_postcode", "")),
        used_ai=bool(payload.get("used_ai", False)),
        forced_fill=bool(payload.get("forced_fill", False)),
    )


def parsed_address_to_dict(parsed: ParsedAddress) -> dict[str, object]:
    return {
        "postcode": parsed.postcode,
        "region": parsed.region,
        "district": parsed.district,
        "city": parsed.city,
        "street": parsed.street,
        "houseNumber": parsed.house_number,
        "apartmentNumber": parsed.apartment_number,
        "extras": list(parsed.extras),
        "poBoxNumber": parsed.po_box_number,
    }


def route_match_result(result: MatchResult) -> dict[str, object]:
    warnings = [item.lower() for item in result.warnings]
    reasons: list[str] = []

    if result.status in HARD_STOP_STATUSES:
        reasons.append(f"Статус потребує ручної перевірки: {result.status}")
    if any("post office address used" in item for item in warnings):
        reasons.append("Використано fallback на адресу відділення")
    if any("forced fill used" in item for item in warnings):
        reasons.append("Використано примусове заповнення")
    if any("nearest available house used" in item for item in warnings):
        reasons.append("Підібрано найближчий будинок")
    if any("resolved from nearest classifier address" in item for item in warnings):
        reasons.append("Використано найближчий кандидат з класифікатора")
    if result.deviation_percent > 40:
        reasons.append(f"Високе відхилення: {result.deviation_percent}%")
    if result.input_postcode and result.resolved_postcode and result.input_postcode != result.resolved_postcode:
        reasons.append("Змінено індекс")
    if result.used_ai and "Використано AI-нормалізацію або rescue" not in reasons:
        reasons.append("Використано AI-нормалізацію або rescue")
    if result.candidate_count > 1 and result.status.endswith("review"):
        reasons.append(f"Кілька кандидатів: {result.candidate_count}")

    is_hard_stop = bool(
        result.status in HARD_STOP_STATUSES
        or any(
            reason in reasons
            for reason in (
                "Використано fallback на адресу відділення",
                "Використано примусове заповнення",
                "Використано найближчий кандидат з класифікатора",
            )
        )
        or result.deviation_percent > 40
    )
    is_auto_accept = bool(
        result.status in AUTO_ACCEPT_STATUSES
        and result.deviation_percent <= 15
        and "Підібрано найближчий будинок" not in reasons
        and "Використано fallback на адресу відділення" not in reasons
        and "Використано найближчий кандидат з класифікатора" not in reasons
    )

    if is_hard_stop:
        queue = "hard_stop"
    elif is_auto_accept:
        queue = "auto_accept"
    else:
        queue = "review"

    if not reasons:
        reasons.append("Низький ризик, автоматичне підтвердження")

    return {
        "queue": queue,
        "needs_review": queue != "auto_accept",
        "reasons": reasons,
    }


def _safe_filename(name: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_", ".", " "} else "_" for char in name).strip()
    return cleaned or "input.txt"


def _address_identity(address: dict[str, str]) -> tuple[str, str, str, str, str, str]:
    return (
        normalize_for_compare(address.get("postcode", "")),
        normalize_for_compare(address.get("region", "")),
        normalize_for_compare(address.get("district", "")),
        normalize_for_compare(address.get("city", "")),
        normalize_for_compare(address.get("street", "")),
        normalize_house_number(address.get("houseNumber", "")),
    )


def _score_candidate(
    parsed: dict[str, object],
    suggested: dict[str, str],
    candidate: dict[str, str],
    input_postcode: str,
) -> int:
    score = 0
    parsed_city = normalize_for_compare(str(parsed.get("city", "")))
    parsed_street = normalize_for_compare(str(parsed.get("street", "")))
    parsed_house = normalize_house_number(str(parsed.get("houseNumber", "")))
    suggested_city = normalize_for_compare(suggested.get("city", ""))
    suggested_street = normalize_for_compare(suggested.get("street", ""))
    suggested_house = normalize_house_number(suggested.get("houseNumber", ""))
    candidate_city = normalize_for_compare(candidate.get("city", ""))
    candidate_street = normalize_for_compare(candidate.get("street", ""))
    candidate_house = normalize_house_number(candidate.get("houseNumber", ""))

    if input_postcode and candidate.get("postcode", "") == input_postcode:
        score += 10
    if suggested.get("postcode", "") and candidate.get("postcode", "") == suggested.get("postcode", ""):
        score += 10
    if parsed_city and candidate_city == parsed_city:
        score += 30
    elif suggested_city and candidate_city == suggested_city:
        score += 20
    if parsed_street and candidate_street == parsed_street:
        score += 30
    elif suggested_street and candidate_street == suggested_street:
        score += 20
    if parsed_house and candidate_house == parsed_house:
        score += 20
    elif suggested_house and candidate_house == suggested_house:
        score += 15
    return score


def _candidate_from_address(address: AddressCandidate) -> dict[str, str]:
    street = address.street
    if address.street_type_short and not street.lower().startswith(address.street_type_short.lower()):
        street = f"{address.street_type_short} {street}".strip()
    return {
        "postcode": address.postcode,
        "region": address.region,
        "district": address.district,
        "city": address.city,
        "street": street,
        "houseNumber": address.house_number,
        "apartmentNumber": "",
    }


def _candidate_from_post_office(office: PostOfficeCandidate, region: str, district: str) -> dict[str, str]:
    street = office.street
    if office.city_type_short and office.city and not street:
        street = office.city_type_short
    return {
        "postcode": office.postcode,
        "region": region,
        "district": district,
        "city": office.city,
        "street": street,
        "houseNumber": office.house_number,
        "apartmentNumber": "",
    }


def _row_similarity_key(row: dict[str, object]) -> tuple[str, str, str, str, str, str]:
    parsed = dict(row["parsed_address"])
    auto_result = dict(row["auto_result"])
    suggested = dict(auto_result["structured_address"])
    return (
        str(row["routing"]["queue"]),
        normalize_for_compare(str(row.get("input_postcode", ""))),
        normalize_for_compare(str(parsed.get("city", ""))),
        normalize_for_compare(str(parsed.get("street", ""))),
        normalize_house_number(str(parsed.get("houseNumber", ""))),
        _address_identity(suggested)[5],
    )


def _unique_candidates(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[tuple[str, str, str, str, str, str]] = set()
    unique: list[dict[str, object]] = []
    for candidate in candidates:
        identity = _address_identity(dict(candidate["address"]))
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(candidate)
    return unique


class ReviewBatchStore:
    def __init__(
        self,
        data_dir: str | Path,
        cache_path: str | Path,
        settings: Settings,
        use_ai: bool = True,
        match_workers: int = 4,
        batch_runner: Callable[..., tuple[dict[int, MatchResult], object]] = _run_batch_matches,
        cache_store_cls: type[CacheStore] = CacheStore,
        classifier_cls: type[UkrposhtaClassifierClient] = UkrposhtaClassifierClient,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = str(cache_path)
        self.settings = settings
        self.use_ai = use_ai
        self.match_workers = match_workers
        self.batch_runner = batch_runner
        self.cache_store_cls = cache_store_cls
        self.classifier_cls = classifier_cls

    def list_batches(self) -> list[dict[str, object]]:
        summaries: list[dict[str, object]] = []
        for batch_file in sorted(self.data_dir.glob("*/batch.json"), reverse=True):
            batch = json.loads(batch_file.read_text(encoding="utf-8"))
            summaries.append(self._batch_summary(batch))
        return summaries

    def create_batch_from_upload(self, filename: str, content: bytes) -> dict[str, object]:
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid4().hex[:8]
        batch_dir = self.data_dir / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        stored_name = _safe_filename(filename)
        input_path = batch_dir / stored_name
        input_path.write_bytes(content)

        document = read_registry(input_path)
        results, stats = self.batch_runner(
            document.rows,
            cache_path=self.cache_path,
            settings=self.settings,
            use_ai=self.use_ai,
            match_workers=self.match_workers,
        )

        rows_payload: list[dict[str, object]] = []
        for row in document.rows:
            result = results[row.line_no]
            parsed = parse_raw_address(row.raw_address, postcode=row.postcode)
            routing = route_match_result(result)
            rows_payload.append(
                {
                    "line_no": row.line_no,
                    "raw_line": row.raw_line,
                    "fields": row.fields,
                    "input_postcode": row.postcode,
                    "original_address": row.raw_address,
                    "parsed_address": parsed_address_to_dict(parsed),
                    "auto_result": match_result_to_dict(result),
                    "routing": routing,
                    "decision": None,
                }
            )

        batch = {
            "version": REVIEW_DATA_VERSION,
            "batch_id": batch_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "filename": stored_name,
            "input_path": str(input_path),
            "encoding": document.encoding,
            "stats": stats.to_summary(len({(row.raw_address, row.postcode) for row in document.rows})),
            "rows": rows_payload,
        }
        self._recalculate_summary(batch)
        self._save_batch(batch)
        return self.load_batch(batch_id)

    def load_batch(self, batch_id: str) -> dict[str, object]:
        batch = self._load_batch(batch_id)
        return {
            **self._batch_summary(batch),
            "rows": [self._row_list_item(row) for row in batch["rows"]],
        }

    def load_row_detail(self, batch_id: str, line_no: int) -> dict[str, object]:
        batch = self._load_batch(batch_id)
        row = self._find_row(batch, line_no)
        detail = dict(row)
        detail["candidates"] = self._build_candidates(row)
        detail["similar_rows"] = self._similar_rows(batch, row)
        detail["batch_id"] = batch["batch_id"]
        detail["filename"] = batch["filename"]
        return detail

    def apply_decision(self, batch_id: str, line_no: int, payload: dict[str, object]) -> dict[str, object]:
        batch = self._load_batch(batch_id)
        row = self._find_row(batch, line_no)
        decision = self._normalize_decision(row, payload)
        row["decision"] = decision
        apply_to_similar = bool(payload.get("apply_to_similar", False))
        applied_line_nos: list[int] = []
        if apply_to_similar:
            for similar_row in self._similar_rows(batch, row):
                similar_row["decision"] = json.loads(json.dumps(decision, ensure_ascii=False))
                applied_line_nos.append(int(similar_row["line_no"]))
        self._recalculate_summary(batch)
        self._save_batch(batch)
        detail = self.load_row_detail(batch_id, line_no)
        detail["applied_to_similar_line_nos"] = applied_line_nos
        return detail

    def export_auto_result(self, batch_id: str) -> tuple[str, bytes]:
        batch = self._load_batch(batch_id)
        return self._export_registry(batch, final=False)

    def export_final_result(self, batch_id: str) -> tuple[str, bytes]:
        batch = self._load_batch(batch_id)
        pending = [row["line_no"] for row in batch["rows"] if row["routing"]["needs_review"] and row["decision"] is None]
        if pending:
            raise ValueError(f"Pending review rows remain: {pending[:10]}")
        return self._export_registry(batch, final=True)

    def export_review_log(self, batch_id: str) -> tuple[str, bytes]:
        batch = self._load_batch(batch_id)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "line_no",
                "queue",
                "status",
                "action",
                "reason_code",
                "comment",
                "final_json",
            ]
        )
        for row in batch["rows"]:
            decision = row["decision"] or {}
            final_address = decision.get("final_address") or row["auto_result"]["structured_address"]
            writer.writerow(
                [
                    row["line_no"],
                    row["routing"]["queue"],
                    row["auto_result"]["status"],
                    decision.get("action", ""),
                    decision.get("reason_code", ""),
                    decision.get("comment", ""),
                    json.dumps(final_address, ensure_ascii=False, separators=(",", ":")),
                ]
            )
        filename = f"{Path(batch['filename']).stem}_review_log.csv"
        return filename, buffer.getvalue().encode("utf-8")

    def _export_registry(self, batch: dict[str, object], final: bool) -> tuple[str, bytes]:
        output_path = self.data_dir / batch["batch_id"] / ("final_output.txt" if final else "auto_output.txt")
        rows = [
            RegistryRow(
                line_no=int(item["line_no"]),
                raw_line=str(item["raw_line"]),
                fields=[str(field) for field in item["fields"]],
            )
            for item in batch["rows"]
        ]
        results = {
            row.line_no: self._result_for_export(self._find_row(batch, row.line_no), final=final)
            for row in rows
        }
        write_registry(output_path, rows, results, encoding=str(batch["encoding"]))
        suffix = "final" if final else "auto"
        filename = f"{Path(batch['filename']).stem}_{suffix}.txt"
        return filename, output_path.read_bytes()

    def _result_for_export(self, row: dict[str, object], final: bool) -> MatchResult:
        base = match_result_from_dict(dict(row["auto_result"]))
        if not final or row["decision"] is None:
            return base

        decision = dict(row["decision"])
        action = str(decision.get("action", "accept_suggested"))
        if action == "accept_suggested":
            return base

        address = structured_address_from_dict(dict(decision.get("final_address", {})))
        status_map = {
            "select_candidate": "operator_selected_candidate",
            "manual_override": "operator_manual_override",
            "mark_unresolved": "operator_marked_unresolved",
        }
        return MatchResult(
            structured_address=address,
            status=status_map.get(action, base.status),
            deviation_percent=base.deviation_percent,
            postcode_state=base.postcode_state,
            warnings=base.warnings,
            candidate_count=base.candidate_count,
            input_postcode=base.input_postcode,
            resolved_postcode=address.postcode,
            used_ai=base.used_ai,
            forced_fill=base.forced_fill,
        )

    def _normalize_decision(self, row: dict[str, object], payload: dict[str, object]) -> dict[str, object]:
        action = str(payload.get("action", "")).strip()
        if action not in {"accept_suggested", "select_candidate", "manual_override", "mark_unresolved"}:
            raise ValueError("Непідтримувана дія оператора.")

        if action == "accept_suggested":
            final_address = dict(row["auto_result"]["structured_address"])
        elif action == "mark_unresolved":
            final_address = dict(row["auto_result"]["structured_address"])
        else:
            final_address = dict(payload.get("final_address", {}))
            required_fields = ("postcode", "region", "city", "street", "houseNumber")
            missing = [field for field in required_fields if not str(final_address.get(field, "")).strip()]
            if missing:
                raise ValueError(f"Не заповнені обов'язкові поля адреси: {', '.join(missing)}")

        return {
            "action": action,
            "reason_code": str(payload.get("reason_code", "")).strip(),
            "comment": str(payload.get("comment", "")).strip(),
            "final_address": {
                "postcode": str(final_address.get("postcode", "")).strip(),
                "region": str(final_address.get("region", "")).strip(),
                "district": str(final_address.get("district", "")).strip(),
                "city": str(final_address.get("city", "")).strip(),
                "street": str(final_address.get("street", "")).strip(),
                "houseNumber": str(final_address.get("houseNumber", "")).strip(),
                "apartmentNumber": str(final_address.get("apartmentNumber", "")).strip(),
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _build_candidates(self, row: dict[str, object]) -> list[dict[str, object]]:
        parsed = dict(row["parsed_address"])
        suggested = dict(row["auto_result"]["structured_address"])
        input_postcode = str(row["input_postcode"])

        cache_store = self.cache_store_cls(self.cache_path)
        try:
            classifier = self.classifier_cls(self.settings.ukrposhta_bearer_token, cache_store)
            collected: list[dict[str, object]] = []
            requested_postcodes = [
                value
                for value in [
                    suggested.get("postcode", ""),
                    str(row["auto_result"].get("resolved_postcode", "")),
                    input_postcode,
                ]
                if value
            ]
            seen_postcodes: set[str] = set()
            for postcode in requested_postcodes:
                if postcode in seen_postcodes:
                    continue
                seen_postcodes.add(postcode)
                for candidate in classifier.get_addresses_by_postcode(postcode):
                    address = _candidate_from_address(candidate)
                    collected.append(
                        {
                            "source": "address_by_postcode",
                            "score": _score_candidate(parsed, suggested, address, input_postcode),
                            "note": "Classifier address candidate",
                            "address": address,
                        }
                    )

            if row["routing"]["queue"] == "hard_stop":
                city_name = str(suggested.get("city") or parsed.get("city") or "")
                if city_name:
                    for city in classifier.get_cities_by_name(city_name)[:3]:
                        for office in classifier.get_post_offices_by_city_id(city.city_id):
                            address = _candidate_from_post_office(office, city.region, city.district)
                            collected.append(
                                {
                                    "source": "post_office",
                                    "score": _score_candidate(parsed, suggested, address, input_postcode),
                                    "note": "Post office fallback",
                                    "address": address,
                                }
                            )
            unique = _unique_candidates(collected)
            unique.sort(key=lambda item: (int(item["score"]), item["source"] == "post_office"), reverse=True)
            return unique[:5]
        finally:
            cache_store.close()

    def _batch_summary(self, batch: dict[str, object]) -> dict[str, object]:
        return {
            "batch_id": batch["batch_id"],
            "created_at": batch["created_at"],
            "filename": batch["filename"],
            "summary": batch["summary"],
            "stats": batch["stats"],
        }

    def _row_list_item(self, row: dict[str, object]) -> dict[str, object]:
        return {
            "line_no": row["line_no"],
            "input_postcode": row["input_postcode"],
            "original_address": row["original_address"],
            "auto_result": row["auto_result"],
            "routing": row["routing"],
            "decision": row["decision"],
        }

    def _find_row(self, batch: dict[str, object], line_no: int) -> dict[str, object]:
        for row in batch["rows"]:
            if int(row["line_no"]) == line_no:
                return row
        raise KeyError(f"Unknown line number: {line_no}")

    def _similar_rows(self, batch: dict[str, object], reference_row: dict[str, object]) -> list[dict[str, object]]:
        reference_key = _row_similarity_key(reference_row)
        similar: list[dict[str, object]] = []
        for row in batch["rows"]:
            if int(row["line_no"]) == int(reference_row["line_no"]):
                continue
            if row["decision"] is not None:
                continue
            if _row_similarity_key(row) != reference_key:
                continue
            similar.append(row)
        return similar

    def _recalculate_summary(self, batch: dict[str, object]) -> None:
        rows = list(batch["rows"])
        queue_counts = {"auto_accept": 0, "review": 0, "hard_stop": 0}
        pending = 0
        for row in rows:
            queue = str(row["routing"]["queue"])
            queue_counts[queue] += 1
            if row["routing"]["needs_review"] and row["decision"] is None:
                pending += 1
        batch["summary"] = {
            "rows": len(rows),
            "auto_accept": queue_counts["auto_accept"],
            "review": queue_counts["review"],
            "hard_stop": queue_counts["hard_stop"],
            "pending_review": pending,
        }

    def _load_batch(self, batch_id: str) -> dict[str, object]:
        batch_path = self.data_dir / batch_id / "batch.json"
        if not batch_path.exists():
            raise FileNotFoundError(f"Unknown batch: {batch_id}")
        return json.loads(batch_path.read_text(encoding="utf-8"))

    def _save_batch(self, batch: dict[str, object]) -> None:
        batch_path = self.data_dir / batch["batch_id"] / "batch.json"
        batch_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
