from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from .paths import get_app_root

# Config file lives next to the EXE (in frozen mode)
# or in the repo root (in dev mode).
CONFIG_FILE = get_app_root() / "vattool_config.json"


def load_user_settings() -> Dict[str, str]:
    """
    Load previously saved submitter/EGN from config file, if it exists.
    If anything goes wrong, return empty defaults.
    """
    try:
        if CONFIG_FILE.exists():
            with CONFIG_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "submitter_person": data.get("submitter_person", ""),
                "egn": data.get("egn", ""),
            }
    except Exception:
        # If file is corrupted or unreadable, just ignore it.
        pass

    return {"submitter_person": "", "egn": ""}


def save_user_settings(settings: Dict[str, str]) -> None:
    """
    Save submitter/EGN to config file.
    Errors are swallowed so they don't break the VAT run.
    """
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_FILE.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "submitter_person": settings.get("submitter_person", ""),
                    "egn": settings.get("egn", ""),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
    except Exception:
        # Don't crash if disk permissions are weird, etc.
        pass
