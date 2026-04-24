from __future__ import annotations

from dataclasses import dataclass


def _rate(hits: int, lookups: int) -> float:
    if lookups <= 0:
        return 0.0
    return round((hits / lookups) * 100, 1)


@dataclass(slots=True)
class RuntimeStats:
    final_cache_lookups: int = 0
    final_cache_hits: int = 0
    city_cache_lookups: int = 0
    city_cache_hits: int = 0
    street_cache_lookups: int = 0
    street_cache_hits: int = 0
    street_house_cache_lookups: int = 0
    street_house_cache_hits: int = 0
    response_cache_lookups: int = 0
    response_memory_hits: int = 0
    response_sqlite_hits: int = 0
    classifier_http_requests: int = 0

    def merge(self, other: "RuntimeStats") -> None:
        self.final_cache_lookups += other.final_cache_lookups
        self.final_cache_hits += other.final_cache_hits
        self.city_cache_lookups += other.city_cache_lookups
        self.city_cache_hits += other.city_cache_hits
        self.street_cache_lookups += other.street_cache_lookups
        self.street_cache_hits += other.street_cache_hits
        self.street_house_cache_lookups += other.street_house_cache_lookups
        self.street_house_cache_hits += other.street_house_cache_hits
        self.response_cache_lookups += other.response_cache_lookups
        self.response_memory_hits += other.response_memory_hits
        self.response_sqlite_hits += other.response_sqlite_hits
        self.classifier_http_requests += other.classifier_http_requests

    def to_summary(self, unique_requests: int) -> dict[str, object]:
        response_cache_hits = self.response_memory_hits + self.response_sqlite_hits
        return {
            "unique_requests": unique_requests,
            "classifier_http_requests": self.classifier_http_requests,
            "final_cache": {
                "lookups": self.final_cache_lookups,
                "hits": self.final_cache_hits,
                "hit_rate_percent": _rate(self.final_cache_hits, self.final_cache_lookups),
            },
            "city_cache": {
                "lookups": self.city_cache_lookups,
                "hits": self.city_cache_hits,
                "hit_rate_percent": _rate(self.city_cache_hits, self.city_cache_lookups),
            },
            "street_cache": {
                "lookups": self.street_cache_lookups,
                "hits": self.street_cache_hits,
                "hit_rate_percent": _rate(self.street_cache_hits, self.street_cache_lookups),
            },
            "street_house_cache": {
                "lookups": self.street_house_cache_lookups,
                "hits": self.street_house_cache_hits,
                "hit_rate_percent": _rate(self.street_house_cache_hits, self.street_house_cache_lookups),
            },
            "response_cache": {
                "lookups": self.response_cache_lookups,
                "hits": response_cache_hits,
                "memory_hits": self.response_memory_hits,
                "sqlite_hits": self.response_sqlite_hits,
                "hit_rate_percent": _rate(response_cache_hits, self.response_cache_lookups),
            },
        }
