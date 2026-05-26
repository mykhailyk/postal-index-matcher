import os
import sqlite3
from typing import List

import config
from search.normalizer import TextNormalizer
from search.similarity import SimilarityCalculator
from search.ukrposhta_classifier import ClassifierAddress, ClassifierCity, ClassifierStreet, PostOffice


def init_ukrposhta_cache_schema(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS regions (
                region_id TEXT PRIMARY KEY,
                region TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS global_snapshots (
                snapshot_key TEXT PRIMARY KEY,
                cached_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS districts (
                district_id TEXT PRIMARY KEY,
                region_id TEXT NOT NULL,
                district TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS region_district_snapshots (
                region_id TEXT PRIMARY KEY,
                cached_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cities (
                city_id TEXT PRIMARY KEY,
                region_id TEXT,
                district_id TEXT,
                region TEXT,
                district TEXT,
                city TEXT NOT NULL,
                city_type_short TEXT,
                old_city TEXT,
                population INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS district_city_snapshots (
                district_id TEXT PRIMARY KEY,
                cached_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS streets (
                street_id TEXT PRIMARY KEY,
                city_id TEXT NOT NULL,
                street TEXT NOT NULL,
                street_type_short TEXT,
                old_street TEXT
            );

            CREATE TABLE IF NOT EXISTS city_street_snapshots (
                city_id TEXT PRIMARY KEY,
                cached_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS houses (
                street_id TEXT NOT NULL,
                house_number TEXT NOT NULL,
                normalized_house_number TEXT NOT NULL,
                postcode TEXT NOT NULL,
                PRIMARY KEY (street_id, normalized_house_number, house_number, postcode)
            );

            CREATE TABLE IF NOT EXISTS house_snapshots (
                street_id TEXT PRIMARY KEY,
                cached_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_cities_name ON cities(city);
            CREATE INDEX IF NOT EXISTS idx_cities_old_name ON cities(old_city);
            CREATE INDEX IF NOT EXISTS idx_streets_city ON streets(city_id);
            CREATE INDEX IF NOT EXISTS idx_houses_postcode ON houses(postcode);
            CREATE INDEX IF NOT EXISTS idx_houses_street ON houses(street_id);
            """
        )
        _ensure_column(conn, "house_snapshots", "cached_at", "TEXT NOT NULL DEFAULT ''")


def _ensure_column(conn, table_name: str, column_name: str, declaration: str) -> None:
    columns = {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {declaration}")


class UkrposhtaOfflineCacheClient:
    """Read-only local cache with the same lookup shape as UkrposhtaClassifierClient."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.UKRPOSHTA_CLASSIFIER_SQLITE_PATH
        self.normalizer = TextNormalizer()
        self.similarity = SimilarityCalculator()

    @property
    def enabled(self) -> bool:
        return os.path.exists(self.db_path)

    def get_addresses_by_postcode(self, postcode: str) -> List[ClassifierAddress]:
        postcode = self._normalize_postcode(postcode)
        if not self.enabled or not postcode:
            return []

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT h.postcode, c.region, c.district, c.city, c.city_type_short,
                       s.street, s.street_type_short, h.house_number,
                       c.old_city, s.old_street, c.city_id, s.street_id
                FROM houses h
                JOIN streets s ON s.street_id = h.street_id
                JOIN cities c ON c.city_id = s.city_id
                WHERE h.postcode = ?
                """,
                (postcode,),
            ).fetchall()

        return [
            ClassifierAddress(
                postcode=row["postcode"] or "",
                region=row["region"] or "",
                district=row["district"] or "",
                city=row["city"] or "",
                city_type_short=row["city_type_short"] or "",
                street=row["street"] or "",
                street_type_short=row["street_type_short"] or "",
                house_number=row["house_number"] or "",
                old_city=row["old_city"] or "",
                old_street=row["old_street"] or "",
                city_id=row["city_id"] or "",
                street_id=row["street_id"] or "",
            )
            for row in rows
        ]

    def get_cities_by_name(self, city_name: str) -> List[ClassifierCity]:
        if not self.enabled or not city_name:
            return []

        query = self.normalizer.normalize_city(city_name)
        scored = []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT region, district, city, city_type_short, city_id, population, old_city
                FROM cities
                """
            ).fetchall()

        for row in rows:
            city = row["city"] or ""
            old_city = row["old_city"] or ""
            city_score = self.similarity.token_similarity(query, self.normalizer.normalize_city(city))
            old_score = self.similarity.token_similarity(query, self.normalizer.normalize_city(old_city)) if old_city else 0
            score = max(city_score, old_score)
            if score < 0.80:
                continue
            scored.append((score, int(row["population"] or 0), row))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [
            ClassifierCity(
                region=row["region"] or "",
                district=row["district"] or "",
                city=row["city"] or "",
                city_type_short=row["city_type_short"] or "",
                city_id=row["city_id"] or "",
                population=int(row["population"] or 0),
                old_city=row["old_city"] or "",
            )
            for _, _, row in scored
        ]

    def get_streets_by_name(self, city_id: str, street_name: str) -> List[ClassifierStreet]:
        if not self.enabled or not city_id or not street_name:
            return []

        query = self.normalizer.normalize_street(street_name)
        scored = []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.region, c.district, c.city, c.city_type_short,
                       s.street, s.street_type_short, s.city_id, s.street_id, s.old_street
                FROM streets s
                JOIN cities c ON c.city_id = s.city_id
                WHERE s.city_id = ?
                """,
                (city_id,),
            ).fetchall()

        for row in rows:
            street_score = self.similarity.token_similarity(query, self.normalizer.normalize_street(row["street"] or ""))
            old_street = row["old_street"] or ""
            old_score = self.similarity.token_similarity(query, self.normalizer.normalize_street(old_street)) if old_street else 0
            score = max(street_score, old_score)
            if score < 0.72:
                continue
            scored.append((score, row))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            ClassifierStreet(
                region=row["region"] or "",
                district=row["district"] or "",
                city=row["city"] or "",
                city_type_short=row["city_type_short"] or "",
                street=row["street"] or "",
                street_type_short=row["street_type_short"] or "",
                city_id=row["city_id"] or "",
                street_id=row["street_id"] or "",
                old_street=row["old_street"] or "",
            )
            for _, row in scored
        ]

    def get_houses_by_street_id(self, street_id: str, house_number: str = "") -> List[tuple]:
        if not self.enabled or not street_id:
            return []

        params = [street_id]
        where = "WHERE street_id = ?"
        if house_number:
            where += " AND normalized_house_number = ?"
            params.append(self._normalize_building_for_match(house_number))

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT house_number, postcode
                FROM houses
                {where}
                ORDER BY house_number
                """,
                params,
            ).fetchall()

        return [(row["house_number"] or "", row["postcode"] or "") for row in rows]

    def get_post_offices_by_city_id(self, city_id: str) -> List[PostOffice]:
        if not self.enabled or not city_id:
            return []

        with self._connect() as conn:
            table_exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='post_offices'"
            ).fetchone()
            if not table_exists:
                return []
            rows = conn.execute(
                """
                SELECT postoffice_id, postcode, city_id, city, city_type_short, street,
                       house_number, lock_code, is_security, type_acronym, type_long
                FROM post_offices
                WHERE city_id = ?
                """,
                (city_id,),
            ).fetchall()

        return [
            PostOffice(
                postoffice_id=row["postoffice_id"] or "",
                postcode=row["postcode"] or "",
                city_id=row["city_id"] or "",
                city=row["city"] or "",
                city_type_short=row["city_type_short"] or "",
                street=row["street"] or "",
                house_number=row["house_number"] or "",
                lock_code=row["lock_code"] or "",
                is_security=bool(row["is_security"]),
                type_acronym=row["type_acronym"] or "",
                type_long=row["type_long"] or "",
            )
            for row in rows
        ]

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _normalize_postcode(postcode: str) -> str:
        cleaned = str(postcode or "").strip().replace(" ", "").replace("\x00", "")
        return cleaned.zfill(5) if cleaned.isdigit() else ""

    @staticmethod
    def _normalize_building_for_match(building: str) -> str:
        return str(building or "").upper().replace("-", "").replace(" ", "").strip()
