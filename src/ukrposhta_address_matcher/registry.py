from __future__ import annotations

from pathlib import Path
import csv

from ukrposhta_address_matcher.models import MatchResult, RegistryDocument, RegistryRow
from ukrposhta_address_matcher.utils import compact_json


INPUT_ENCODINGS = ["utf-8", "utf-8-sig", "cp1251", "cp866"]


def read_registry(path: str | Path) -> RegistryDocument:
    raw_bytes = Path(path).read_bytes()
    text = None
    encoding = "utf-8"
    for candidate_encoding in INPUT_ENCODINGS:
        try:
            text = raw_bytes.decode(candidate_encoding)
            encoding = candidate_encoding
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw_bytes.decode("latin-1")
        encoding = "latin-1"

    rows: list[RegistryRow] = []
    for index, line in enumerate(text.splitlines(), start=1):
        fields = line.rstrip("\n").split(";")
        if len(fields) not in (10, 11):
            raise ValueError(f"Unsupported field count {len(fields)} on line {index}")
        rows.append(RegistryRow(line_no=index, raw_line=line, fields=fields))
    return RegistryDocument(rows=rows, encoding=encoding)


def write_registry(
    path: str | Path,
    rows: list[RegistryRow],
    results: dict[int, MatchResult],
    encoding: str = "utf-8",
) -> None:
    output_lines: list[str] = []
    for row in rows:
        fields = row.fields[:]
        result = results[row.line_no]
        fields[2] = result.structured_address.postcode
        fields[3] = compact_json(result.structured_address)
        output_lines.append(";".join(fields))
    Path(path).write_text("\n".join(output_lines), encoding=encoding)


def write_report(path: str | Path, rows: list[RegistryRow], results: dict[int, MatchResult]) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(
            [
                "line_no",
                "status",
                "deviation_percent",
                "input_postcode",
                "resolved_postcode",
                "postcode_state",
                "warnings",
                "original_address",
                "resolved_json",
                "candidate_count",
            ]
        )
        for row in rows:
            result = results[row.line_no]
            writer.writerow(
                [
                    row.line_no,
                    result.status,
                    result.deviation_percent,
                    result.input_postcode,
                    result.resolved_postcode,
                    result.postcode_state,
                    " | ".join(result.warnings),
                    row.raw_address,
                    compact_json(result.structured_address),
                    result.candidate_count,
                ]
            )
