from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, Optional

import pandas as pd

from .schemas import load_all_schemas_and_mappings
from .journal import select_company, get_accounting_period, normalize_journal_columns
from .processing import process_journal
from .deklar import generate_deklar
from .io_utils import create_output_folder, df_to_fixed_width_txt


def run(
    journal_csv_path: Path,
    ui_overrides: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Main entry point for command-line use.

    Steps:
      1. Load journal CSV
      2. Infer company + accounting period
      3. Load schemas + mappings
      4. Process journal into PRODAGBI + POKUPKI
      5. Generate DEKLAR from aggregates
      6. Create output folder and write CSV + TXT files
    """
    if ui_overrides is None:
        ui_overrides = {}

    journal_csv_path = Path(journal_csv_path)
    if not journal_csv_path.exists():
        raise FileNotFoundError(f"Journal file not found: {journal_csv_path}")

    print(f"Using journal file: {journal_csv_path}")

    # --- Load journal CSV ---
    journal_df = pd.read_csv(journal_csv_path, encoding="utf-8")

    # --- Load all schemas and mappings ---
    schemas = load_all_schemas_and_mappings()
    prodagbi_schema = schemas["prodagbi_schema"]
    pokupki_schema = schemas["pokupki_schema"]
    deklar_schema = schemas["deklar_schema"]
    tax_grid_mapping = schemas["tax_grid_mapping"]
    ledger_columns = schemas["ledger_columns"]
    deklar_mapping = schemas["deklar_mapping"]

    # --- Normalize journal CSV columns for Odoo v19 ---
    journal_df = normalize_journal_columns(journal_df, ledger_columns)

    # --- Extract company from journal ---
    company = select_company(journal_df)

    # --- Extract accounting period (YYYYMM) ---
    accounting_period = get_accounting_period(journal_df)
    print(f"Accounting period inferred from journal: {accounting_period}")

    # Tag schema names (used by create_output_row for descriptions)
    prodagbi_schema["schema_name"] = "prodagbi_schema"
    pokupki_schema["schema_name"] = "pokupki_schema"

    # --- Process journal into PRODAGBI + POKUPKI ---
    prodagbi_df, pokupki_df = process_journal(
        journal_df,
        tax_grid_mapping,
        prodagbi_schema,
        pokupki_schema,
        company,
    )

    print(f"PRODAGBI rows: {len(prodagbi_df)}")
    print(f"POKUPKI rows: {len(pokupki_df)}")

    # --- Generate DEKLAR from aggregated data ---
    deklar_df = generate_deklar(
        prodagbi_df=prodagbi_df,
        pokupki_df=pokupki_df,
        deklar_schema=deklar_schema,
        deklar_mapping=deklar_mapping,
        tax_period=accounting_period,
        company=company,
        ui_overrides=ui_overrides,
    )

    print(f"DEKLAR rows: {len(deklar_df)}")

    # --- Create output folder under project root ---
    output_folder = create_output_folder(company, accounting_period)

    # --- Write CSV outputs ---
    prodagbi_csv = output_folder / "prodagbi_output.csv"
    pokupki_csv = output_folder / "pokupki_output.csv"
    deklar_csv = output_folder / "deklar_output.csv"

    prodagbi_df.to_csv(prodagbi_csv, index=False, encoding="utf-8", float_format="%.2f")
    pokupki_df.to_csv(pokupki_csv, index=False, encoding="utf-8", float_format="%.2f")
    deklar_df.to_csv(deklar_csv, index=False, encoding="utf-8", float_format="%.2f")

    print("CSV exports:")
    print(f"  PRODAGBI: {prodagbi_csv}")
    print(f"  POKUPKI:  {pokupki_csv}")
    print(f"  DEKLAR:   {deklar_csv}")

    # --- Write TXT outputs (fixed-width NRA-style) ---
    prodagbi_txt = output_folder / "Prodagbi.txt"
    pokupki_txt = output_folder / "Pokupki.txt"
    deklar_txt = output_folder / "Deklar.txt"

    df_to_fixed_width_txt(prodagbi_df, prodagbi_schema, prodagbi_txt)
    df_to_fixed_width_txt(pokupki_df, pokupki_schema, pokupki_txt)
    df_to_fixed_width_txt(deklar_df, deklar_schema, deklar_txt)

    print("TXT exports:")
    print(f"  PRODAGBI TXT: {prodagbi_txt}")
    print(f"  POKUPKI TXT:  {pokupki_txt}")
    print(f"  DEKLAR TXT:   {deklar_txt}")

    # --- Simple summary ---
    if len(deklar_df) > 0:
        drow = deklar_df.iloc[0]
        print("\nDEKLAR summary (from generated row):")
        for key in [
            "sales_document_count",
            "purchases_document_count",
            "sales_total_vat",
            "purchases_vat_full_credit",
            "total_tax_credit",
            "vat_due",
            "vat_refundable",
        ]:
            if key in drow.index:
                print(f"  {key}: {drow[key]}")


def main(argv: Optional[list[str]] = None) -> None:
    """
    Minimal CLI parser.

    Usage:
        python -m src.vat_exporter.cli path/to/journal.csv
    """
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) < 1:
        print("Usage: python -m src.vat_exporter.cli path/to/journal.csv")
        sys.exit(1)

    journal_path = Path(argv[0])
    run(journal_path)


if __name__ == "__main__":
    main()
