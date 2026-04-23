from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3


DEFAULT_TTL_DAYS = 30


class CacheStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS response_cache (
                cache_key TEXT PRIMARY KEY,
                endpoint TEXT NOT NULL,
                params_json TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                refreshed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS final_cache (
                input_fingerprint TEXT PRIMARY KEY,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                refreshed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def get_response(self, cache_key: str, ttl_days: int = DEFAULT_TTL_DAYS) -> str | None:
        row = self.connection.execute(
            "SELECT body, refreshed_at FROM response_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        if row is None:
            return None
        refreshed_at = datetime.fromisoformat(row["refreshed_at"])
        if refreshed_at < datetime.now(timezone.utc) - timedelta(days=ttl_days):
            return None
        return str(row["body"])

    def set_response(self, cache_key: str, endpoint: str, params: dict[str, str], body: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute(
            """
            INSERT INTO response_cache (cache_key, endpoint, params_json, body, created_at, refreshed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                endpoint = excluded.endpoint,
                params_json = excluded.params_json,
                body = excluded.body,
                refreshed_at = excluded.refreshed_at
            """,
            (cache_key, endpoint, json.dumps(params, ensure_ascii=False, sort_keys=True), body, now, now),
        )
        self.connection.commit()

    def iter_cached_requests(self) -> list[tuple[str, str, dict[str, str]]]:
        rows = self.connection.execute(
            "SELECT cache_key, endpoint, params_json FROM response_cache ORDER BY endpoint, cache_key"
        ).fetchall()
        return [
            (
                str(row["cache_key"]),
                str(row["endpoint"]),
                json.loads(str(row["params_json"])),
            )
            for row in rows
        ]

    def build_final_fingerprint(self, raw_address: str, postcode: str) -> str:
        payload = f"{postcode}|{raw_address}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get_final_result(self, fingerprint: str, ttl_days: int = DEFAULT_TTL_DAYS) -> dict[str, object] | None:
        row = self.connection.execute(
            "SELECT result_json, refreshed_at FROM final_cache WHERE input_fingerprint = ?",
            (fingerprint,),
        ).fetchone()
        if row is None:
            return None
        refreshed_at = datetime.fromisoformat(row["refreshed_at"])
        if refreshed_at < datetime.now(timezone.utc) - timedelta(days=ttl_days):
            return None
        return json.loads(str(row["result_json"]))

    def set_final_result(self, fingerprint: str, result: dict[str, object]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute(
            """
            INSERT INTO final_cache (input_fingerprint, result_json, created_at, refreshed_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(input_fingerprint) DO UPDATE SET
                result_json = excluded.result_json,
                refreshed_at = excluded.refreshed_at
            """,
            (fingerprint, json.dumps(result, ensure_ascii=False, sort_keys=True), now, now),
        )
        self.connection.commit()

    def set_metadata(self, key: str, value: str) -> None:
        self.connection.execute(
            """
            INSERT INTO metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        self.connection.commit()

    def get_metadata(self, key: str) -> str | None:
        row = self.connection.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    def close(self) -> None:
        self.connection.close()
