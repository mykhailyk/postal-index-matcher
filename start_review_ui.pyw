from __future__ import annotations

from pathlib import Path
import os
import sys
import traceback


def main() -> int:
    repo_root = Path(__file__).resolve().parent
    os.chdir(repo_root)
    sys.path.insert(0, str(repo_root / "src"))

    from ukrposhta_address_matcher.cli import review_ui_main

    return review_ui_main([])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:  # pragma: no cover - UI launcher fallback
        try:
            import tkinter
            from tkinter import messagebox

            root = tkinter.Tk()
            root.withdraw()
            messagebox.showerror(
                "Помилка запуску Review UI",
                f"Не вдалося запустити Review UI.\n\n{error}\n\n{traceback.format_exc()}",
            )
            root.destroy()
        except Exception:
            pass
        raise
