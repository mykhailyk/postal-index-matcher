import argparse
from datetime import datetime, timedelta, timezone
import os
import sqlite3
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from search.ukrposhta_classifier import UkrposhtaClassifierClient
from search.ukrposhta_offline_cache import init_ukrposhta_cache_schema


def load_env_file(path: str) -> None:
    if not path:
        return
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(f"Env file not found: {env_path}")

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def normalize_house_number(value: str) -> str:
    return str(value or "").upper().replace("-", "").replace(" ", "").strip()


def first_value(item: dict, *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value:
            return str(value)
    return ""


def upsert_regions(conn, rows):
    conn.executemany(
        """
        INSERT INTO regions (region_id, region)
        VALUES (?, ?)
        ON CONFLICT(region_id) DO UPDATE SET region = excluded.region
        """,
        [
            (
                first_value(row, "REGION_ID"),
                first_value(row, "REGION_UA", "REGION_NAME"),
            )
            for row in rows
            if first_value(row, "REGION_ID")
        ],
    )


def upsert_districts(conn, rows):
    conn.executemany(
        """
        INSERT INTO districts (district_id, region_id, district)
        VALUES (?, ?, ?)
        ON CONFLICT(district_id) DO UPDATE SET
            region_id = excluded.region_id,
            district = excluded.district
        """,
        [
            (
                first_value(row, "DISTRICT_ID"),
                first_value(row, "REGION_ID"),
                first_value(row, "DISTRICT_UA", "DISTRICT_NAME"),
            )
            for row in rows
            if first_value(row, "DISTRICT_ID")
        ],
    )


def upsert_cities(conn, rows):
    conn.executemany(
        """
        INSERT INTO cities (
            city_id, region_id, district_id, region, district, city,
            city_type_short, old_city, population
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(city_id) DO UPDATE SET
            region_id = excluded.region_id,
            district_id = excluded.district_id,
            region = excluded.region,
            district = excluded.district,
            city = excluded.city,
            city_type_short = excluded.city_type_short,
            old_city = excluded.old_city,
            population = excluded.population
        """,
        [
            (
                first_value(row, "CITY_ID"),
                first_value(row, "REGION_ID"),
                first_value(row, "DISTRICT_ID"),
                first_value(row, "REGION_UA", "REGION_NAME"),
                first_value(row, "DISTRICT_UA", "DISTRICT_NAME"),
                first_value(row, "CITY_UA", "CITY_NAME"),
                first_value(row, "SHORTCITYTYPE_UA", "CITYTYPE_NAME"),
                first_value(row, "OLDCITY_UA", "OLDCITY_NAME"),
                int(first_value(row, "POPULATION") or "0"),
            )
            for row in rows
            if first_value(row, "CITY_ID")
        ],
    )


def upsert_streets(conn, rows):
    conn.executemany(
        """
        INSERT INTO streets (street_id, city_id, street, street_type_short, old_street)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(street_id) DO UPDATE SET
            city_id = excluded.city_id,
            street = excluded.street,
            street_type_short = excluded.street_type_short,
            old_street = excluded.old_street
        """,
        [
            (
                first_value(row, "STREET_ID"),
                first_value(row, "CITY_ID"),
                first_value(row, "STREET_UA", "STREET_NAME"),
                first_value(row, "SHORTSTREETTYPE_UA", "SHORTSTREETTYPE_NAME"),
                first_value(row, "OLDSTREET_UA", "OLDSTREET_NAME"),
            )
            for row in rows
            if first_value(row, "STREET_ID")
        ],
    )


def upsert_houses(conn, street_id: str, rows):
    conn.executemany(
        """
        INSERT INTO houses (street_id, house_number, normalized_house_number, postcode)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(street_id, normalized_house_number, house_number, postcode) DO NOTHING
        """,
        [
            (
                street_id,
                first_value(row, "HOUSENUMBER_UA", "HOUSENUMBER"),
                normalize_house_number(first_value(row, "HOUSENUMBER_UA", "HOUSENUMBER")),
                first_value(row, "POSTCODE"),
            )
            for row in rows
            if first_value(row, "HOUSENUMBER_UA", "HOUSENUMBER") and first_value(row, "POSTCODE")
        ],
    )


def maybe_sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def limited(items, limit: int):
    return items if not limit else items[:limit]


def city_streets_cached(conn, city_id: str, ttl_days: int) -> bool:
    return snapshot_is_fresh(conn, "city_street_snapshots", "city_id", city_id, ttl_days)


def street_houses_cached(conn, street_id: str, ttl_days: int) -> bool:
    return snapshot_is_fresh(conn, "house_snapshots", "street_id", street_id, ttl_days)


def region_districts_cached(conn, region_id: str, ttl_days: int) -> bool:
    return snapshot_is_fresh(conn, "region_district_snapshots", "region_id", region_id, ttl_days)


def district_cities_cached(conn, district_id: str, ttl_days: int) -> bool:
    return snapshot_is_fresh(conn, "district_city_snapshots", "district_id", district_id, ttl_days)


def regions_cached(conn, ttl_days: int) -> bool:
    return snapshot_is_fresh(conn, "global_snapshots", "snapshot_key", "regions", ttl_days)


def snapshot_is_fresh(conn, table_name: str, key_column: str, key_value: str, ttl_days: int) -> bool:
    row = conn.execute(
        f"SELECT cached_at FROM {table_name} WHERE {key_column} = ? LIMIT 1",
        (key_value,),
    ).fetchone()
    if row is None:
        return False
    if ttl_days <= 0:
        return True
    try:
        cached_at = datetime.fromisoformat(row["cached_at"])
    except (TypeError, ValueError):
        return False
    return cached_at >= datetime.now(timezone.utc) - timedelta(days=ttl_days)


def mark_city_streets_cached(conn, city_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO city_street_snapshots (city_id, cached_at)
        VALUES (?, ?)
        ON CONFLICT(city_id) DO UPDATE SET cached_at = excluded.cached_at
        """,
        (city_id, now),
    )


def mark_region_districts_cached(conn, region_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO region_district_snapshots (region_id, cached_at)
        VALUES (?, ?)
        ON CONFLICT(region_id) DO UPDATE SET cached_at = excluded.cached_at
        """,
        (region_id, now),
    )


def mark_regions_cached(conn) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO global_snapshots (snapshot_key, cached_at)
        VALUES ('regions', ?)
        ON CONFLICT(snapshot_key) DO UPDATE SET cached_at = excluded.cached_at
        """,
        (now,),
    )


def mark_district_cities_cached(conn, district_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO district_city_snapshots (district_id, cached_at)
        VALUES (?, ?)
        ON CONFLICT(district_id) DO UPDATE SET cached_at = excluded.cached_at
        """,
        (district_id, now),
    )


def mark_street_houses_cached(conn, street_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO house_snapshots (street_id, cached_at)
        VALUES (?, ?)
        ON CONFLICT(street_id) DO UPDATE SET cached_at = excluded.cached_at
        """,
        (street_id, now),
    )


def cached_regions(conn) -> list[dict[str, str]]:
    rows = conn.execute(
        """
        SELECT region_id AS REGION_ID, region AS REGION_UA
        FROM regions
        ORDER BY region
        """
    ).fetchall()
    return [dict(row) for row in rows]


def cached_districts(conn, region_id: str) -> list[dict[str, str]]:
    rows = conn.execute(
        """
        SELECT district_id AS DISTRICT_ID, region_id AS REGION_ID, district AS DISTRICT_UA
        FROM districts
        WHERE region_id = ?
        ORDER BY district
        """,
        (region_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def cached_cities(conn, district_id: str) -> list[dict[str, str]]:
    rows = conn.execute(
        """
        SELECT city_id AS CITY_ID, region_id AS REGION_ID, district_id AS DISTRICT_ID,
               region AS REGION_UA, district AS DISTRICT_UA, city AS CITY_UA,
               city_type_short AS SHORTCITYTYPE_UA, old_city AS OLDCITY_UA,
               population AS POPULATION
        FROM cities
        WHERE district_id = ?
        ORDER BY city
        """,
        (district_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def cached_streets(conn, city_id: str) -> list[dict[str, str]]:
    rows = conn.execute(
        """
        SELECT street_id AS STREET_ID, city_id AS CITY_ID, street AS STREET_UA,
               street_type_short AS SHORTSTREETTYPE_UA, old_street AS OLDSTREET_UA
        FROM streets
        WHERE city_id = ?
        ORDER BY street
        """,
        (city_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local SQLite cache from Ukrposhta address classifier.")
    parser.add_argument("--env-file", default="", help="Optional .env file with UKRPOSHTA_BEARER_TOKEN.")
    parser.add_argument("--db-path", default=config.UKRPOSHTA_CLASSIFIER_SQLITE_PATH)
    parser.add_argument("--include-houses", action="store_true", help="Also download house/postcode rows for each street.")
    parser.add_argument("--sleep", type=float, default=0.2, help="Delay between API requests.")
    parser.add_argument("--limit-regions", type=int, default=0, help="Debug limit.")
    parser.add_argument("--limit-districts", type=int, default=0, help="Debug limit.")
    parser.add_argument("--limit-cities", type=int, default=0, help="Debug limit.")
    parser.add_argument("--limit-streets", type=int, default=0, help="Debug limit.")
    parser.add_argument("--refresh", action="store_true", help="Re-download already cached city streets and houses.")
    parser.add_argument("--ttl-days", type=int, default=30, help="Refresh cached city/street snapshots older than this many days. Use 0 to never expire.")
    args = parser.parse_args()

    load_env_file(args.env_file)
    token = os.environ.get("UKRPOSHTA_BEARER_TOKEN", "")
    if not token:
        print("UKRPOSHTA_BEARER_TOKEN is missing. Pass --env-file or set the environment variable.", file=sys.stderr)
        return 2

    init_ukrposhta_cache_schema(args.db_path)
    client = UkrposhtaClassifierClient(token=token)

    with sqlite3.connect(args.db_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")

        if not args.refresh and regions_cached(conn, args.ttl_days):
            regions = cached_regions(conn)
            print(f"regions cached: {len(regions)}")
        else:
            regions = client.get_regions("")
            upsert_regions(conn, regions)
            mark_regions_cached(conn)
            conn.commit()
            print(f"regions: {len(regions)}")

        for region in limited(regions, args.limit_regions):
            region_id = first_value(region, "REGION_ID")
            if not region_id:
                continue

            if not args.refresh and region_districts_cached(conn, region_id, args.ttl_days):
                districts = cached_districts(conn, region_id)
                print(f"region {region_id}: districts cached {len(districts)}")
            else:
                districts = client.get_districts(region_id=region_id)
                upsert_districts(conn, districts)
                mark_region_districts_cached(conn, region_id)
                conn.commit()
                print(f"region {region_id}: districts {len(districts)}")
                maybe_sleep(args.sleep)

            for district in limited(districts, args.limit_districts):
                district_id = first_value(district, "DISTRICT_ID")
                if not district_id:
                    continue

                if not args.refresh and district_cities_cached(conn, district_id, args.ttl_days):
                    cities = cached_cities(conn, district_id)
                    print(f"district {district_id}: cities cached {len(cities)}")
                else:
                    cities = client.get_cities(region_id=region_id, district_id=district_id)
                    upsert_cities(conn, cities)
                    mark_district_cities_cached(conn, district_id)
                    conn.commit()
                    print(f"district {district_id}: cities {len(cities)}")
                    maybe_sleep(args.sleep)

                for city in limited(cities, args.limit_cities):
                    city_id = first_value(city, "CITY_ID")
                    if not city_id:
                        continue

                    if not args.refresh and city_streets_cached(conn, city_id, args.ttl_days):
                        streets = cached_streets(conn, city_id)
                        print(f"city {city_id}: streets cached {len(streets)}")
                    else:
                        streets = client.get_streets(region_id=region_id, district_id=district_id, city_id=city_id)
                        upsert_streets(conn, streets)
                        mark_city_streets_cached(conn, city_id)
                        conn.commit()
                        print(f"city {city_id}: streets {len(streets)}")
                        maybe_sleep(args.sleep)

                    if not args.include_houses:
                        continue

                    for street in limited(streets, args.limit_streets):
                        street_id = first_value(street, "STREET_ID")
                        if not street_id:
                            continue
                        if not args.refresh and street_houses_cached(conn, street_id, args.ttl_days):
                            print(f"street {street_id}: houses cached")
                            continue
                        houses = client._entries("get_addr_house_by_street_id", {"street_id": street_id})
                        upsert_houses(conn, street_id, houses)
                        mark_street_houses_cached(conn, street_id)
                        conn.commit()
                        print(f"street {street_id}: houses {len(houses)}")
                        maybe_sleep(args.sleep)

    print(f"cache ready: {args.db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
