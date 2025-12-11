from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any
import json
import shutil
from datetime import datetime

import tkinter as tk
from tkinter import messagebox

from .paths import get_app_root


REQUIRED_TEMPLATES = [
    "prodagbi_schema.json",
    "pokupki_schema.json",
    "deklar_schema.json",
    "deklar_mapping.json",
    "tax_grid_mapping.json",
]


def _get_templates_dir() -> Path:
    """Return the external templates directory (user-editable)."""
    return get_app_root() / "templates"


def _get_default_templates_dir() -> Path:
    """Return the internal default templates directory (packaged)."""
    # Frozen (PyInstaller) → defaults are under <app_root>/vat_exporter/default_templates
    if getattr(sys, "frozen", False):
        return get_app_root() / "vat_exporter" / "default_templates"

    # Dev / source mode → defaults are alongside this file in src/vat_exporter/default_templates
    return Path(__file__).resolve().parent / "default_templates"



def _load_json(path: Path) -> Dict[str, Any]:
    """Load JSON file, raising JSONDecodeError on invalid content."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _show_yes_no(title: str, message: str) -> bool:
    """
    Show a Tkinter Yes/No dialog and return True if user clicked 'Yes'.
    Creates a temporary root so it works even before the main UI.
    """
    root = tk.Tk()
    root.withdraw()
    try:
        result = messagebox.askyesno(title, message)
    finally:
        root.destroy()
    return bool(result)


def _backup_file(path: Path) -> None:
    """Rename an existing file to *.broken_<timestamp> for safety."""
    if not path.exists():
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_suffix(path.suffix + f".broken_{timestamp}")
    shutil.move(str(path), str(backup_path))


def _restore_default_template(template_name: str, target_path: Path) -> None:
    """Copy default template into the external templates directory."""
    default_dir = _get_default_templates_dir()
    default_path = default_dir / template_name

    if not default_path.exists():
        raise FileNotFoundError(
            f"Internal default template not found: {default_path}"
        )

    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(default_path), str(target_path))


def ensure_templates_ready() -> None:
    """
    Ensure that all required template JSON files exist and are valid.

    Logic:
      - If a template is missing:
          * Ask user if they want to create it from default.
      - If a template is invalid JSON:
          * Ask user if they want to backup + restore default.
      - If user cancels at any point:
          * Raise RuntimeError to abort the app cleanly.
    """
    templates_dir = _get_templates_dir()
    templates_dir.mkdir(parents=True, exist_ok=True)

    for name in REQUIRED_TEMPLATES:
        target_path = templates_dir / name

        # Case 1: file missing
        if not target_path.exists():
            msg = (
                f"The template file '{name}' is missing in:\n\n"
                f"{templates_dir}\n\n"
                f"Do you want to create it from the default template?"
            )
            create = _show_yes_no("Missing template", msg)
            if not create:
                raise RuntimeError(
                    f"Template '{name}' is required but missing, and user declined to restore."
                )

            _restore_default_template(name, target_path)
            continue

        # Case 2: file exists → try to parse JSON
        try:
            _ = _load_json(target_path)
            # NOTE: For now we only validate that it's parseable JSON.
            #       Structural validation can be added later.
        except json.JSONDecodeError as e:
            msg = (
                f"The template file '{name}' appears to be invalid JSON:\n\n"
                f"{target_path}\n\n"
                f"Error: {e}\n\n"
                f"Do you want to backup the broken file and restore the default?"
            )
            restore = _show_yes_no("Invalid template", msg)
            if not restore:
                raise RuntimeError(
                    f"Template '{name}' is invalid and user declined to restore."
                )

            # Backup old file, then restore default
            _backup_file(target_path)
            _restore_default_template(name, target_path)

        except Exception as e:
            msg = (
                f"Unexpected error while reading template '{name}':\n\n"
                f"{target_path}\n\n"
                f"Error: {e}\n\n"
                f"Do you want to backup the file and restore the default?"
            )
            restore = _show_yes_no("Template error", msg)
            if not restore:
                raise RuntimeError(
                    f"Template '{name}' could not be used and user declined to restore."
                )

            _backup_file(target_path)
            _restore_default_template(name, target_path)
