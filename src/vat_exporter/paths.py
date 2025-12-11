from __future__ import annotations

from pathlib import Path
import sys


def get_app_root() -> Path:
    """
    Return the 'application root' directory.

    - When running from source: repo root (the folder that has src/, templates/, etc.)
    - When frozen with PyInstaller: the folder where the EXE lives.

    This lets us keep templates/ next to the EXE in the portable app.
    """
    # PyInstaller / frozen exe case
    if getattr(sys, "frozen", False):
        # sys.executable is the path to the EXE
        return Path(sys.executable).resolve().parent

    # Normal source run (your current dev flow)
    return Path(__file__).resolve().parents[2]
