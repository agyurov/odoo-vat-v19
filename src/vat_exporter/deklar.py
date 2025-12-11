from __future__ import annotations

from typing import Dict, Any, Optional

import pandas as pd


def _parse_float(value) -> float:
    """Utility to parse strings safely into floats."""
    try:
        if value is None:
            return 0.0
        s = str(value).strip().replace(",", ".")
        return float(s)
    except Exception:
        return 0.0


def generate_deklar(
    prodagbi_df: pd.DataFrame,
    pokupki_df: pd.DataFrame,
    deklar_schema: Dict[str, Any],
    deklar_mapping: Dict[str, Any],
    tax_period: str,
    company: Dict[str, Any],
    ui_overrides: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Generate the DEKLAR summary row based on:
      - PRODAGBI table (sales)
      - POKUPKI table (purchases)
      - deklar_schema: defines columns, types, default lengths, etc.
      - deklar_mapping: defines where each deklar column value comes from
      - tax_period: e.g. "202511"
      - company: dict from journal parsing
      - ui_overrides: values provided by user interface (submitter, EGN, pop-up fields)

    Returns a one-row DataFrame.
    """
    if ui_overrides is None:
        ui_overrides = {}

    deklar_row = {}

    # === Step 1: Initialize all deklar columns from schema ===
    schema_by_name = {f["internal_name"]: f for f in deklar_schema["fields"]}

    for field in deklar_schema["fields"]:
        col = field["internal_name"]
        ftype = field.get("type", "object")

        if ftype == "float64":
            deklar_row[col] = 0.0
        elif ftype == "object":
            deklar_row[col] = ""
        else:
            deklar_row[col] = None

    # === Step 2: Build mapping lookup ===
    mapping_by_col = {
        m["deklar_column"]: m
        for m in deklar_mapping.get("fields", [])
    }

    # === Step 3: Fill non-expression fields ===
    for field in deklar_schema["fields"]:
        col = field["internal_name"]
        m = mapping_by_col.get(col)
        if not m:
            continue

        sk = m.get("source_kind")

        # 3.1: Company / context-driven fields
        if sk == "from_input_or_company":
            if col == "vat_number":
                deklar_row[col] = company["vat"]
            elif col == "taxpayer_name":
                deklar_row[col] = company["legal_name"]
            elif col == "tax_period":
                deklar_row[col] = tax_period
            elif col == "submitter_person":
                deklar_row[col] = ui_overrides.get(
                    "submitter_person", company.get("default_submitter", "Емилия Гюрова")
                )
            elif col == "sales_document_count":
                deklar_row[col] = len(prodagbi_df)
            elif col == "purchases_document_count":
                deklar_row[col] = len(pokupki_df)

        # 3.2: Sum over PRODAGBI
        elif sk == "sum_prodagbi_column":
            src = m.get("source_column")
            if src in prodagbi_df.columns and len(prodagbi_df) > 0:
                deklar_row[col] = prodagbi_df[src].sum()
            else:
                deklar_row[col] = 0.0

        # 3.3: Sum over POKUPKI
        elif sk == "sum_pokupki_column":
            src = m.get("source_column")
            if src in pokupki_df.columns and len(pokupki_df) > 0:
                deklar_row[col] = pokupki_df[src].sum()
            else:
                deklar_row[col] = 0.0

        # 3.4: Manual or UI-provided values (pop-up fields)
        elif sk == "manual_or_constant":
            if col in ui_overrides:
                field_type = schema_by_name[col].get("type", "float64")
                if field_type == "float64":
                    deklar_row[col] = _parse_float(ui_overrides[col])
                else:
                    deklar_row[col] = ui_overrides[col]
            elif "default_value" in m:
                field_type = schema_by_name[col].get("type", "float64")
                if field_type == "float64":
                    deklar_row[col] = _parse_float(m["default_value"])
                else:
                    deklar_row[col] = m["default_value"]

        # 3.5: expressions handled later
        elif sk == "from_deklar_expression":
            continue

        # Unknown source – ignore (schema default stays)
        else:
            continue

    # === Step 4: Evaluate expressions ===
    for field in deklar_schema["fields"]:
        col = field["internal_name"]
        m = mapping_by_col.get(col)
        if not m:
            continue

        if m.get("source_kind") != "from_deklar_expression":
            continue

        # Current simple expressions (extendable)
        if col == "total_tax_credit":
            deklar_row[col] = deklar_row.get("purchases_vat_full_credit", 0.0)
        elif col == "vat_due":
            deklar_row[col] = max(
                0.0,
                deklar_row.get("sales_total_vat", 0.0) -
                deklar_row.get("total_tax_credit", 0.0)
            )
        elif col == "vat_refundable":
            deklar_row[col] = max(
                0.0,
                deklar_row.get("total_tax_credit", 0.0) -
                deklar_row.get("sales_total_vat", 0.0)
            )

    # === Step 5: Handle EGN override if schema contains such a column ===
    if "egn" in ui_overrides:
        if "submitter_egn" in deklar_row:
            deklar_row["submitter_egn"] = ui_overrides["egn"]
        elif "egn" in deklar_row:
            deklar_row["egn"] = ui_overrides["egn"]

    # === Return one-row DataFrame ===
    return pd.DataFrame([deklar_row])
