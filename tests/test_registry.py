from pathlib import Path

from ukrposhta_address_matcher.models import MatchResult, RegistryRow, StructuredAddress
from ukrposhta_address_matcher.registry import (
    read_registry,
    write_postcode_unresolved_report,
    write_registry,
    write_report,
)


def test_read_registry_supports_10_and_11_fields(tmp_path: Path) -> None:
    file_path = tmp_path / "input.txt"
    file_path.write_text(
        "1;0;04116;addr;name;simple;10;mailing;5;110x220\n"
        "2;0;04116;addr;name;simple;10;mailing;5;110x220;R123",
        encoding="utf-8",
    )
    document = read_registry(file_path)
    assert document.encoding == "utf-8"
    assert len(document.rows) == 2
    assert len(document.rows[0].fields) == 10
    assert len(document.rows[1].fields) == 11


def test_write_registry_replaces_address_and_postcode(tmp_path: Path) -> None:
    rows = [
        RegistryRow(
            line_no=1,
            raw_line="1;0;04116;a;n;s;10;m;5;110x220",
            fields=["1", "0", "04116", "a", "n", "s", "10", "m", "5", "110x220"],
        )
    ]
    result = MatchResult(
        structured_address=StructuredAddress(
            postcode="04210",
            region="\u041a\u0438\u0457\u0432",
            district="\u041a\u0438\u0457\u0432",
            city="\u041a\u0438\u0457\u0432",
            street="\u0412\u043e\u043b\u043e\u0434\u0438\u043c\u0438\u0440\u0430 \u0406\u0432\u0430\u0441\u044e\u043a\u0430",
            house_number="43\u0411",
            apartment_number="31",
        ),
        status="postcode_corrected",
        deviation_percent=35,
        postcode_state="postcode_corrected",
        input_postcode="04116",
        resolved_postcode="04210",
    )
    output_path = tmp_path / "output.txt"
    report_path = tmp_path / "report.csv"
    write_registry(output_path, rows, {1: result})
    write_report(report_path, rows, {1: result})
    output = output_path.read_text(encoding="utf-8")
    report = report_path.read_text(encoding="utf-8")
    assert "04210" in output
    assert '"street":"\u0412\u043e\u043b\u043e\u0434\u0438\u043c\u0438\u0440\u0430 \u0406\u0432\u0430\u0441\u044e\u043a\u0430"' in output
    assert "postcode_corrected" in report


def test_write_postcode_unresolved_report_outputs_only_rows_without_resolved_postcode(tmp_path: Path) -> None:
    rows = [
        RegistryRow(
            line_no=1,
            raw_line="1;0;04116;a;n;s;10;m;5;110x220",
            fields=["1", "0", "04116", "a", "n", "s", "10", "m", "5", "110x220"],
        ),
        RegistryRow(
            line_no=2,
            raw_line="2;0;;b;n;s;10;m;5;110x220",
            fields=["2", "0", "", "b", "n", "s", "10", "m", "5", "110x220"],
        ),
    ]
    results = {
        1: MatchResult(
            structured_address=StructuredAddress(postcode="04116"),
            status="postcode_verified",
            deviation_percent=0,
            postcode_state="postcode_verified_locked",
            input_postcode="04116",
            resolved_postcode="04116",
        ),
        2: MatchResult(
            structured_address=StructuredAddress(),
            status="unresolved_review",
            deviation_percent=100,
            postcode_state="postcode_unresolved",
            warnings=["no classifier candidate resolved"],
            input_postcode="",
            resolved_postcode="",
        ),
    }
    report_path = tmp_path / "postcode_unresolved.csv"
    count = write_postcode_unresolved_report(report_path, rows, results)
    report = report_path.read_text(encoding="utf-8")

    assert count == 1
    assert "line_no,input_postcode,original_address,status,postcode_state,warnings" in report
    assert "2,,b,unresolved_review,postcode_unresolved" in report
