from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any


# We assume the project root has a "templates" folder.
# This works whether you run from the repo root or install the package.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = PROJECT_ROOT / "templates"


def _load_json(path: Path) -> Dict[str, Any]:
    """Load a JSON file and return it as a dict."""
    if not path.exists():
        raise FileNotFoundError(f"Template file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_prodagbi_schema() -> Dict[str, Any]:
    """Load PRODAGBI schema definition."""
    return _load_json(TEMPLATES_DIR / "prodagbi_schema.json")


def load_pokupki_schema() -> Dict[str, Any]:
    """Load POKUPKI schema definition."""
    return _load_json(TEMPLATES_DIR / "pokupki_schema.json")


def load_deklar_schema() -> Dict[str, Any]:
    """Load DEKLAR schema definition."""
    return _load_json(TEMPLATES_DIR / "deklar_schema.json")


def load_tax_grid_mapping() -> Dict[str, Any]:
    """Load tax grid → columns mapping (used to build prodagbi/pokupki)."""
    return _load_json(TEMPLATES_DIR / "tax_grid_mapping.json")


def load_deklar_mapping() -> Dict[str, Any]:
    """Load DEKLAR logical mapping (how columns are filled/aggregated)."""
    return _load_json(TEMPLATES_DIR / "deklar_mapping.json")


def load_all_schemas_and_mappings() -> Dict[str, Dict[str, Any]]:
    """
    Convenience helper to load everything at once.
    Returns a dict with keys:
      - 'prodagbi_schema'
      - 'pokupki_schema'
      - 'deklar_schema'
      - 'tax_grid_mapping'
      - 'deklar_mapping'
    """
    return {
        "prodagbi_schema": load_prodagbi_schema(),
        "pokupki_schema": load_pokupki_schema(),
        "deklar_schema": load_deklar_schema(),
        "tax_grid_mapping": load_tax_grid_mapping(),
        "deklar_mapping": load_deklar_mapping(),
    }
