from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


def _load_env_file(env_path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not env_path.exists():
        return data
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip("'").strip('"')
    return data


@dataclass(slots=True)
class Settings:
    ukrposhta_bearer_token: str
    gemini_api_key: str
    classifier_refresh_hour: int
    classifier_refresh_minute: int
    classifier_refresh_tz: str
    github_username: str

    @classmethod
    def load(cls, env_path: str | Path = ".env") -> "Settings":
        env_map = _load_env_file(Path(env_path))

        def get(name: str, default: str = "") -> str:
            return os.environ.get(name) or env_map.get(name, default)

        return cls(
            ukrposhta_bearer_token=get("UKRPOSHTA_BEARER_TOKEN"),
            gemini_api_key=get("GEMINI_API_KEY"),
            classifier_refresh_hour=int(get("CLASSIFIER_REFRESH_HOUR", "3")),
            classifier_refresh_minute=int(get("CLASSIFIER_REFRESH_MINUTE", "0")),
            classifier_refresh_tz=get("CLASSIFIER_REFRESH_TZ", "Europe/Kyiv"),
            github_username=get("GITHUB_USERNAME", "mykhailyk"),
        )

