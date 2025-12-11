from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional

import tkinter as tk
from tkinter import filedialog, messagebox

from .schemas import load_deklar_mapping
from .cli import run as run_pipeline


def _build_ui_window(deklar_mapping: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Build and display the Tkinter window.

    Returns a dict with:
      - "journal_path": Path
      - "ui_overrides": Dict[str, Any]
    or None if the user cancels/closes without running.
    """
    root = tk.Tk()
    root.title("VAT Journal Export")

    params: Dict[str, Any] = {
        "journal_path": None,
        "ui_overrides": {},
    }

    # --- journal file selection ---

    file_var = tk.StringVar(value="(no file selected)")

    def choose_file():
        path = filedialog.askopenfilename(
            title="Select Journal CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=str(Path.cwd() / "data"),
        )
        if path:
            file_var.set(path)

    row = 0
    tk.Label(root, text="Journal CSV file:").grid(row=row, column=0, sticky="w", padx=5, pady=(5, 0))
    tk.Button(root, text="Browse...", command=choose_file).grid(row=row, column=1, sticky="w", padx=5, pady=(5, 0))
    row += 1
    tk.Label(root, textvariable=file_var, wraplength=500).grid(
        row=row, column=0, columnspan=2, sticky="w", padx=5
    )
    row += 1

    # --- submitter + EGN ---

    submitter_var = tk.StringVar(value="Емилия Гюрова")
    egn_var = tk.StringVar(value="6111146394")

    tk.Label(root, text="Submitter (Подател):").grid(row=row, column=0, sticky="w", padx=5, pady=(10, 0))
    tk.Entry(root, textvariable=submitter_var, width=40).grid(row=row, column=1, sticky="w", padx=5, pady=(10, 0))
    row += 1

    tk.Label(root, text="ЕГН:").grid(row=row, column=0, sticky="w", padx=5)
    tk.Entry(root, textvariable=egn_var, width=40).grid(row=row, column=1, sticky="w", padx=5)
    row += 1

    # --- pop-up DEKLAR fields (manual_or_constant) ---

    tk.Label(root, text="Deklar pop-up fields:").grid(
        row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(10, 0)
    )
    row += 1

    popup_fields = [
        m for m in deklar_mapping.get("fields", [])
        if m.get("source_kind") == "manual_or_constant"
    ]

    field_vars: Dict[str, tk.StringVar] = {}
    for m in popup_fields:
        colname = m["deklar_column"]
        default_val = m.get("default_value", 0)
        v = tk.StringVar(value=str(default_val))
        field_vars[colname] = v

        tk.Label(root, text=colname + ":").grid(row=row, column=0, sticky="w", padx=5)
        tk.Entry(root, textvariable=v, width=20).grid(row=row, column=1, sticky="w", padx=5)
        row += 1

    # --- buttons ---

    def on_run():
        path_str = file_var.get()
        if not path_str or path_str == "(no file selected)":
            messagebox.showerror("Missing file", "Please choose a journal CSV file.")
            return

        jpath = Path(path_str)
        if not jpath.exists():
            messagebox.showerror("Invalid file", f"File does not exist:\n{jpath}")
            return

        ui_overrides: Dict[str, Any] = {
            "submitter_person": submitter_var.get(),
            "egn": egn_var.get(),
        }
        for colname, var in field_vars.items():
            ui_overrides[colname] = var.get()

        params["journal_path"] = jpath
        params["ui_overrides"] = ui_overrides

        root.destroy()

    def on_cancel():
        params["journal_path"] = None
        root.destroy()

    tk.Button(root, text="Run", command=on_run).grid(row=row, column=0, padx=5, pady=10, sticky="w")
    tk.Button(root, text="Cancel", command=on_cancel).grid(row=row, column=1, padx=5, pady=10, sticky="w")

    root.mainloop()

    if params["journal_path"] is None:
        return None
    return params


def main() -> None:
    """
    Entry point for the Tkinter UI.

    Usage:
        python -m src.vat_exporter.ui
    """
    # Load DEKLAR mapping to know which pop-up fields to show
    deklar_mapping = load_deklar_mapping()

    result = _build_ui_window(deklar_mapping)
    if result is None:
        print("Operation cancelled by user.")
        return

    journal_path: Path = result["journal_path"]
    ui_overrides: Dict[str, Any] = result["ui_overrides"]

    # Delegate actual work to the core pipeline
    run_pipeline(journal_path, ui_overrides=ui_overrides)


if __name__ == "__main__":
    main()
