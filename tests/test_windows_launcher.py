import os
from pathlib import Path

from ukrposhta_address_matcher import windows_launcher


def test_windows_launcher_calls_review_ui_main(monkeypatch, tmp_path: Path) -> None:
    original_cwd = Path.cwd()
    monkeypatch.setattr(windows_launcher, "__file__", str(tmp_path / "src" / "ukrposhta_address_matcher" / "windows_launcher.py"))
    captured = {}

    def fake_review_ui_main(argv):
        captured["argv"] = argv
        captured["cwd"] = Path.cwd()
        return 0

    monkeypatch.setattr(windows_launcher, "review_ui_main", fake_review_ui_main)

    try:
        exit_code = windows_launcher.main()
    finally:
        os.chdir(original_cwd)

    assert exit_code == 0
    assert captured["argv"] == []
    assert captured["cwd"] == tmp_path


def test_windows_launcher_passes_env_file_when_found(monkeypatch, tmp_path: Path) -> None:
    original_cwd = Path.cwd()
    launcher_path = tmp_path / "src" / "ukrposhta_address_matcher" / "windows_launcher.py"
    launcher_path.parent.mkdir(parents=True, exist_ok=True)
    launcher_path.write_text("", encoding="utf-8")
    env_path = tmp_path / ".env"
    env_path.write_text("UKRPOSHTA_BEARER_TOKEN=test", encoding="utf-8")
    monkeypatch.setattr(windows_launcher, "__file__", str(launcher_path))
    captured = {}

    def fake_review_ui_main(argv):
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(windows_launcher, "review_ui_main", fake_review_ui_main)

    try:
        exit_code = windows_launcher.main()
    finally:
        os.chdir(original_cwd)

    assert exit_code == 0
    assert captured["argv"] == ["--env-file", str(env_path)]
