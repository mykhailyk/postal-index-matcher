from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from ukrposhta_address_matcher.utils import normalize_for_compare, normalize_house_number


DEFAULT_TTL_DAYS = 30


class CacheStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path, timeout=30.0)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA busy_timeout = 30000")
        if self.db_path != ":memory:":
            self.connection.execute("PRAGMA journal_mode = WAL")
            self.connection.execute("PRAGMA synchronous = NORMAL")
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

            CREATE TABLE IF NOT EXISTS street_house_cache (
                street_id TEXT NOT NULL,
                house_number_norm TEXT NOT NULL,
                house_number TEXT NOT NULL,
                postcode TEXT NOT NULL,
                refreshed_at TEXT NOT NULL,
                PRIMARY KEY (street_id, house_number_norm, house_number, postcode)
            );

            CREATE TABLE IF NOT EXISTS street_house_snapshots (
                street_id TEXT PRIMARY KEY,
                refreshed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS city_candidate_cache (
                query_norm TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                refreshed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS street_candidate_cache (
                city_id TEXT NOT NULL,
                query_norm TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                refreshed_at TEXT NOT NULL,
                PRIMARY KEY (city_id, query_norm)
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

    def get_cached_houses(
        self,
        street_id: str,
        house_number: str = "",
        ttl_days: int = DEFAULT_TTL_DAYS,
    ) -> list[tuple[str, str]] | None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=ttl_days)).isoformat()

        if house_number:
            normalized_house = normalize_house_number(house_number)
            rows = self.connection.execute(
                """
                SELECT house_number, postcode
                FROM street_house_cache
                WHERE street_id = ? AND house_number_norm = ? AND refreshed_at >= ?
                ORDER BY house_number, postcode
                """,
                (street_id, normalized_house, cutoff),
            ).fetchall()
            if rows:
                return [(str(row["house_number"]), str(row["postcode"])) for row in rows]
            if self.has_full_street_snapshot(street_id, ttl_days=ttl_days):
                return []
            return None

        if not self.has_full_street_snapshot(street_id, ttl_days=ttl_days):
            return None
        rows = self.connection.execute(
            """
            SELECT house_number, postcode
            FROM street_house_cache
            WHERE street_id = ? AND refreshed_at >= ?
            ORDER BY house_number, postcode
            """,
            (street_id, cutoff),
        ).fetchall()
        return [(str(row["house_number"]), str(row["postcode"])) for row in rows]

    def upsert_street_houses(self, street_id: str, houses: list[tuple[str, str]]) -> None:
        if not houses:
            return
        now = datetime.now(timezone.utc).isoformat()
        self.connection.executemany(
            """
            INSERT INTO street_house_cache (street_id, house_number_norm, house_number, postcode, refreshed_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(street_id, house_number_norm, house_number, postcode) DO UPDATE SET
                refreshed_at = excluded.refreshed_at
            """,
            [
                (street_id, normalize_house_number(house_number), house_number, postcode, now)
                for house_number, postcode in houses
                if house_number
            ],
        )
        self.connection.commit()

    def replace_street_houses(self, street_id: str, houses: list[tuple[str, str]]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute("DELETE FROM street_house_cache WHERE street_id = ?", (street_id,))
        if houses:
            self.connection.executemany(
                """
                INSERT INTO street_house_cache (street_id, house_number_norm, house_number, postcode, refreshed_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(street_id, house_number_norm, house_number, postcode) DO UPDATE SET
                    refreshed_at = excluded.refreshed_at
                """,
                [
                    (street_id, normalize_house_number(house_number), house_number, postcode, now)
                    for house_number, postcode in houses
                    if house_number
                ],
            )
        self.connection.execute(
            """
            INSERT INTO street_house_snapshots (street_id, refreshed_at)
            VALUES (?, ?)
            ON CONFLICT(street_id) DO UPDATE SET refreshed_at = excluded.refreshed_at
            """,
            (street_id, now),
        )
        self.connection.commit()

    def has_full_street_snapshot(self, street_id: str, ttl_days: int = DEFAULT_TTL_DAYS) -> bool:
        row = self.connection.execute(
            "SELECT refreshed_at FROM street_house_snapshots WHERE street_id = ?",
            (street_id,),
        ).fetchone()
        if row is None:
            return False
        refreshed_at = datetime.fromisoformat(str(row["refreshed_at"]))
        return refreshed_at >= datetime.now(timezone.utc) - timedelta(days=ttl_days)

    def get_cached_city_candidates(
        self,
        city_name: str,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ) -> list[dict[str, object]] | None:
        query_norm = normalize_for_compare(city_name)
        if not query_norm:
            return None
        row = self.connection.execute(
            "SELECT payload_json, refreshed_at FROM city_candidate_cache WHERE query_norm = ?",
            (query_norm,),
        ).fetchone()
        if row is None:
            return None
        refreshed_at = datetime.fromisoformat(str(row["refreshed_at"]))
        if refreshed_at < datetime.now(timezone.utc) - timedelta(days=ttl_days):
            return None
        return json.loads(str(row["payload_json"]))

    def set_cached_city_candidates(self, city_name: str, candidates: list[dict[str, object]]) -> None:
        query_norm = normalize_for_compare(city_name)
        if not query_norm:
            return
        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute(
            """
            INSERT INTO city_candidate_cache (query_norm, payload_json, refreshed_at)
            VALUES (?, ?, ?)
            ON CONFLICT(query_norm) DO UPDATE SET
                payload_json = excluded.payload_json,
                refreshed_at = excluded.refreshed_at
            """,
            (query_norm, json.dumps(candidates, ensure_ascii=False, sort_keys=True), now),
        )
        self.connection.commit()

    def get_cached_street_candidates(
        self,
        city_id: str,
        street_name: str,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ) -> list[dict[str, object]] | None:
        query_norm = normalize_for_compare(street_name)
        if not city_id or not query_norm:
            return None
        row = self.connection.execute(
            """
            SELECT payload_json, refreshed_at
            FROM street_candidate_cache
            WHERE city_id = ? AND query_norm = ?
            """,
            (city_id, query_norm),
        ).fetchone()
        if row is None:
            return None
        refreshed_at = datetime.fromisoformat(str(row["refreshed_at"]))
        if refreshed_at < datetime.now(timezone.utc) - timedelta(days=ttl_days):
            return None
        return json.loads(str(row["payload_json"]))

    def set_cached_street_candidates(
        self,
        city_id: str,
        street_name: str,
        candidates: list[dict[str, object]],
    ) -> None:
        query_norm = normalize_for_compare(street_name)
        if not city_id or not query_norm:
            return
        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute(
            """
            INSERT INTO street_candidate_cache (city_id, query_norm, payload_json, refreshed_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(city_id, query_norm) DO UPDATE SET
                payload_json = excluded.payload_json,
                refreshed_at = excluded.refreshed_at
            """,
            (city_id, query_norm, json.dumps(candidates, ensure_ascii=False, sort_keys=True), now),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()
