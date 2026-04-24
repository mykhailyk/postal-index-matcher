import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ukrposhta_address_matcher.review_ui import ThreadingHTTPServerWithReuse, _build_handler


class DummyStore:
    def __init__(self) -> None:
        self.decision_payloads: list[dict[str, object]] = []

    def list_batches(self) -> list[dict[str, object]]:
        return [{"batch_id": "b1", "filename": "sample.txt", "summary": {"rows": 1, "auto_accept": 1, "review": 0, "hard_stop": 0, "pending_review": 0}, "stats": {"unique_requests": 1, "classifier_http_requests": 0}, "created_at": "2026-04-24T10:00:00+00:00"}]

    def load_batch(self, batch_id: str) -> dict[str, object]:
        if batch_id != "b1":
            raise FileNotFoundError(batch_id)
        return {
            "batch_id": "b1",
            "filename": "sample.txt",
            "summary": {"rows": 1, "auto_accept": 1, "review": 0, "hard_stop": 0, "pending_review": 0},
            "stats": {"unique_requests": 1, "classifier_http_requests": 0},
            "rows": [],
            "created_at": "2026-04-24T10:00:00+00:00",
        }

    def load_row_detail(self, batch_id: str, line_no: int) -> dict[str, object]:
        if batch_id != "b1" or line_no != 1:
            raise FileNotFoundError(batch_id)
        return {"line_no": 1, "batch_id": "b1", "candidates": [], "routing": {"queue": "review", "needs_review": True, "reasons": []}, "auto_result": {"structured_address": {"postcode": "04053", "region": "Київ", "district": "Київ", "city": "Київ", "street": "Велика Житомирська", "houseNumber": "30", "apartmentNumber": ""}, "status": "postcode_corrected", "warnings": []}, "parsed_address": {"postcode": "04053", "region": "", "district": "", "city": "Київ", "street": "Велика Житомирська", "houseNumber": "30", "apartmentNumber": "", "extras": [], "poBoxNumber": ""}, "input_postcode": "04053", "original_address": "м. Київ, вул. Велика Житомирська, 30", "decision": None, "similar_rows": []}

    def export_auto_result(self, batch_id: str) -> tuple[str, bytes]:
        return "auto.txt", b"auto"

    def export_final_result(self, batch_id: str) -> tuple[str, bytes]:
        return "final.txt", b"final"

    def export_review_log(self, batch_id: str) -> tuple[str, bytes]:
        return "review.csv", b"log"

    def create_batch_from_upload(self, filename: str, content: bytes) -> dict[str, object]:
        return self.load_batch("b1")

    def apply_decision(self, batch_id: str, line_no: int, payload: dict[str, object]) -> dict[str, object]:
        self.decision_payloads.append(payload)
        detail = self.load_row_detail(batch_id, line_no)
        detail["decision"] = {"action": payload["action"]}
        detail["applied_to_similar_line_nos"] = []
        return detail


def _start_server(store: DummyStore):
    server = ThreadingHTTPServerWithReuse(("127.0.0.1", 0), _build_handler(store))
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, port


def test_review_ui_serves_index_and_batches_api() -> None:
    store = DummyStore()
    server, thread, port = _start_server(store)
    try:
        root = urlopen(f"http://127.0.0.1:{port}/").read().decode("utf-8")
        batches = json.loads(urlopen(f"http://127.0.0.1:{port}/api/batches").read().decode("utf-8"))
        assert "Ручна перевірка адрес" in root
        assert batches["items"][0]["batch_id"] == "b1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_review_ui_accepts_multipart_upload_and_decision_post() -> None:
    store = DummyStore()
    server, thread, port = _start_server(store)
    try:
        boundary = "----BoundaryForUpload"
        payload = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="sample.txt"\r\n'
            "Content-Type: text/plain\r\n\r\n"
            "1;0;04053;addr;n;s;10;m;5;110x220\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")
        req = Request(f"http://127.0.0.1:{port}/api/batches", data=payload, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        req.add_header("Content-Length", str(len(payload)))
        created = json.loads(urlopen(req).read().decode("utf-8"))
        assert created["batch_id"] == "b1"

        decision_payload = json.dumps({"action": "accept_suggested", "reason_code": "accepted_suggested"}).encode("utf-8")
        decision_req = Request(
            f"http://127.0.0.1:{port}/api/batches/b1/rows/1/decision",
            data=decision_payload,
            method="POST",
        )
        decision_req.add_header("Content-Type", "application/json")
        decision_req.add_header("Content-Length", str(len(decision_payload)))
        detail = json.loads(urlopen(decision_req).read().decode("utf-8"))

        assert detail["decision"]["action"] == "accept_suggested"
        assert store.decision_payloads[0]["reason_code"] == "accepted_suggested"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_review_ui_returns_404_json_for_unknown_batch() -> None:
    store = DummyStore()
    server, thread, port = _start_server(store)
    try:
        try:
            urlopen(f"http://127.0.0.1:{port}/api/batches/missing")
            assert False, "Expected HTTPError"
        except HTTPError as error:
            payload = json.loads(error.read().decode("utf-8"))
            assert error.code == 404
            assert "missing" in payload["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
