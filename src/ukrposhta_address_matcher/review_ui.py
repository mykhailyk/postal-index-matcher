from __future__ import annotations

import json
from pathlib import Path
import re
from socketserver import ThreadingMixIn
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import webbrowser

from ukrposhta_address_matcher.config import Settings
from ukrposhta_address_matcher.review import ReviewBatchStore


WEB_DIR = Path(__file__).with_name("web")


class ThreadingHTTPServerWithReuse(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def run_review_ui(
    host: str,
    port: int,
    data_dir: str | Path,
    cache_path: str | Path,
    settings: Settings,
    use_ai: bool,
    match_workers: int,
    open_browser: bool = False,
) -> None:
    store = ReviewBatchStore(
        data_dir=data_dir,
        cache_path=cache_path,
        settings=settings,
        use_ai=use_ai,
        match_workers=match_workers,
    )
    handler_class = _build_handler(store)
    server = ThreadingHTTPServerWithReuse((host, port), handler_class)
    app_url = f"http://{host}:{port}"
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(app_url)).start()
    print(f"Review UI: {app_url}")
    server.serve_forever()


def _build_handler(store: ReviewBatchStore):
    class ReviewUIHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            try:
                if path == "/":
                    self._serve_static("index.html", "text/html; charset=utf-8")
                    return
                if path == "/app.js":
                    self._serve_static("app.js", "application/javascript; charset=utf-8")
                    return
                if path == "/styles.css":
                    self._serve_static("styles.css", "text/css; charset=utf-8")
                    return
                if path == "/api/batches":
                    self._send_json({"items": store.list_batches()})
                    return
                if path.startswith("/api/batches/"):
                    parts = [part for part in path.split("/") if part]
                    if len(parts) == 3:
                        self._send_json(store.load_batch(parts[2]))
                        return
                    if len(parts) == 5 and parts[3] == "rows":
                        self._send_json(store.load_row_detail(parts[2], int(parts[4])))
                        return
                    if len(parts) == 5 and parts[3] == "export":
                        self._handle_export(parts[2], parts[4])
                        return
                self._send_json({"error": "Маршрут не знайдено."}, status=404)
            except FileNotFoundError as error:
                self._send_json({"error": str(error)}, status=404)
            except ValueError as error:
                self._send_json({"error": str(error)}, status=400)
            except Exception as error:  # pragma: no cover - defensive HTTP handler branch
                self._send_json({"error": f"Внутрішня помилка сервера: {error}"}, status=500)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            try:
                if path == "/api/batches":
                    self._handle_create_batch()
                    return
                if path.startswith("/api/batches/"):
                    parts = [part for part in path.split("/") if part]
                    if len(parts) == 6 and parts[3] == "rows" and parts[5] == "decision":
                        payload = self._read_json()
                        detail = store.apply_decision(parts[2], int(parts[4]), payload)
                        self._send_json(detail)
                        return
                self._send_json({"error": "Маршрут не знайдено."}, status=404)
            except FileNotFoundError as error:
                self._send_json({"error": str(error)}, status=404)
            except ValueError as error:
                self._send_json({"error": str(error)}, status=400)
            except Exception as error:  # pragma: no cover - defensive HTTP handler branch
                self._send_json({"error": f"Внутрішня помилка сервера: {error}"}, status=500)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return None

        def _handle_create_batch(self) -> None:
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                raise ValueError("Очікується form-data з файлом.")
            filename, content = self._read_uploaded_file(content_type)
            if not content:
                raise ValueError("Файл порожній.")
            batch = store.create_batch_from_upload(filename, content)
            self._send_json(batch, status=201)

        def _handle_export(self, batch_id: str, export_kind: str) -> None:
            if export_kind == "auto":
                filename, payload = store.export_auto_result(batch_id)
            elif export_kind == "final":
                filename, payload = store.export_final_result(batch_id)
            elif export_kind == "review-log":
                filename, payload = store.export_review_log(batch_id)
            else:
                raise ValueError("Невідомий тип експорту.")
            self._send_bytes(payload, "application/octet-stream", filename=filename)

        def _serve_static(self, filename: str, content_type: str) -> None:
            path = WEB_DIR / filename
            if not path.exists():
                raise FileNotFoundError(f"Статичний файл не знайдено: {filename}")
            self._send_bytes(path.read_bytes(), content_type)

        def _read_json(self) -> dict[str, object]:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))

        def _read_uploaded_file(self, content_type: str) -> tuple[str, bytes]:
            boundary_match = re.search(r'boundary="?([^";]+)"?', content_type)
            if boundary_match is None:
                raise ValueError("Не вдалося визначити boundary для завантаження файла.")

            length = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(length)
            boundary = ("--" + boundary_match.group(1)).encode("utf-8")
            for part in payload.split(boundary):
                if b'name="file"' not in part:
                    continue
                header_block, separator, body = part.partition(b"\r\n\r\n")
                if not separator:
                    continue
                header_text = header_block.decode("utf-8", errors="ignore")
                filename_match = re.search(r'filename="([^"]*)"', header_text)
                filename = filename_match.group(1) if filename_match else "input.txt"
                content = body
                if content.endswith(b"\r\n"):
                    content = content[:-2]
                if content.endswith(b"--"):
                    content = content[:-2]
                if content.endswith(b"\r\n"):
                    content = content[:-2]
                return filename or "input.txt", content

            raise ValueError("Файл не передано.")

        def _send_json(self, payload: dict[str, object], status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_bytes(self, payload: bytes, content_type: str, filename: str | None = None) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(payload)

    return ReviewUIHandler
