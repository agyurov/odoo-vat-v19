from __future__ import annotations

from typing import Dict, Any
import re

import pandas as pd


REQUIRED_LEDGER_COLUMN_KEYS = [
    "company_name",
    "company_vat",
    "partner_name",
    "partner_vat",
    "tax_tag_ids",
    "balance",
    "date",
    "journal_type",
    "purchase_ref",
    "sales_move_name",
    "document_type",
]


def normalize_journal_columns(
    journal_df: pd.DataFrame,
    ledger_columns: Dict[str, Any],
) -> pd.DataFrame:
    """
    Normalize Odoo v19 export columns to canonical internal names.

    This function also removes export artifacts (Unnamed:* columns) and validates
    that all required mappings and source columns are present.
    """
    unnamed_cols = [c for c in journal_df.columns if str(c).startswith("Unnamed:")]
    if unnamed_cols:
        journal_df = journal_df.drop(columns=unnamed_cols)

    missing_mapping_keys = [k for k in REQUIRED_LEDGER_COLUMN_KEYS if k not in ledger_columns]
    if missing_mapping_keys:
        raise ValueError(
            "Missing required keys in ledger-columns.json: "
            + ", ".join(missing_mapping_keys)
        )

    rename_map: Dict[str, str] = {}
    missing_source_columns = []

    for canonical_key in REQUIRED_LEDGER_COLUMN_KEYS:
        source_col = ledger_columns[canonical_key]
        if source_col not in journal_df.columns:
            missing_source_columns.append(f"{canonical_key} -> {source_col}")
            continue
        rename_map[source_col] = canonical_key

    if missing_source_columns:
        raise ValueError(
            "Journal CSV is missing required columns from ledger-columns.json: "
            + "; ".join(missing_source_columns)
        )

    return journal_df.rename(columns=rename_map)


def select_company(journal_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Extract company info from the journal CSV.

    Expects canonical columns:
      - 'company_name'   -> company name
      - 'company_vat'    -> VAT number

    Assumes all rows belong to the same company.
    """
    required_cols = ["company_name", "company_vat"]
    missing = [c for c in required_cols if c not in journal_df.columns]
    if missing:
        raise ValueError(f"Missing required columns in journal for company info: {missing}")

    # Get unique non-empty values
    company_names = (
        journal_df["company_name"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )
    tax_ids = (
        journal_df["company_vat"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )

    if len(company_names) == 0 or len(tax_ids) == 0:
        raise ValueError(
            "Could not find non-empty values for 'company_name' and 'company_vat' in journal."
        )

    if len(company_names) > 1:
        print("WARNING: Multiple different Company names found in journal. Using the first one.")
        print("  Unique Company values:", list(company_names))
    if len(tax_ids) > 1:
        print("WARNING: Multiple different company_vat values found in journal. Using the first one.")
        print("  Unique company_vat values:", list(tax_ids))

    company_name = company_names[0]
    tax_id = tax_ids[0]

    # Optional: numeric version (strip non-digits), in case you want it later
    vat_numeric = re.sub(r"\D", "", tax_id)

    company = {
        "id": "from_csv",
        "display_name": company_name,
        "legal_name": company_name,
        "country_code": "BG",  # adjust if needed
        "vat": tax_id,
        "vat_numeric": vat_numeric,
        "bulstat": vat_numeric,
        "default": True,
    }

    print(f"Using company from journal: {company_name} ({tax_id})")
    return company


def get_accounting_period(journal_df: pd.DataFrame) -> str:
    """
    Extract accounting period (YYYYMM) from journal data using max date.

    Side effect:
      - adds a 'date_dt' column (datetime) to journal_df, which other
        logic (e.g. create_output_row) can reuse.
    """
    if "date" not in journal_df.columns:
        raise ValueError("Journal data must contain 'date' column")

    date_values = journal_df["date"].astype("string").str.strip()
    non_empty_mask = date_values.notna() & (date_values != "")

    if not non_empty_mask.any():
        raise ValueError("Journal 'date' column has no non-empty values")

    non_empty_values = date_values[non_empty_mask]
    iso_mask = non_empty_values.str.fullmatch(r"\d{4}-\d{2}-\d{2}")
    eu_mask = non_empty_values.str.fullmatch(r"\d{2}/\d{2}/\d{4}")

    assumed_format = "mixed (YYYY-MM-DD and/or DD/MM/YYYY)"
    parsed_dates = pd.Series(pd.NaT, index=journal_df.index, dtype="datetime64[ns]")

    if iso_mask.all():
        assumed_format = "ISO (%Y-%m-%d)"
        parsed_dates.loc[non_empty_values.index] = pd.to_datetime(
            non_empty_values,
            format="%Y-%m-%d",
            errors="coerce",
        )
    elif eu_mask.all():
        assumed_format = "EU (%d/%m/%Y)"
        parsed_dates.loc[non_empty_values.index] = pd.to_datetime(
            non_empty_values,
            format="%d/%m/%Y",
            errors="coerce",
        )
    else:
        iso_indices = non_empty_values.index[iso_mask]
        eu_indices = non_empty_values.index[eu_mask]

        if len(iso_indices) > 0:
            parsed_dates.loc[iso_indices] = pd.to_datetime(
                non_empty_values.loc[iso_indices],
                format="%Y-%m-%d",
                errors="coerce",
            )
        if len(eu_indices) > 0:
            parsed_dates.loc[eu_indices] = pd.to_datetime(
                non_empty_values.loc[eu_indices],
                format="%d/%m/%Y",
                errors="coerce",
            )

    invalid_mask = non_empty_mask & parsed_dates.isna()
    if invalid_mask.any():
        bad_values = date_values[invalid_mask].head(3).tolist()
        raise ValueError(
            "Error parsing dates from 'date' column. "
            f"Assumed format: {assumed_format}. "
            f"First invalid values: {bad_values}"
        )

    journal_df["date_dt"] = parsed_dates
    max_date = journal_df["date_dt"].max()
    accounting_period = max_date.strftime("%Y%m")  # YYYYMM format
    return accounting_period


def create_agg_col(journal_df: pd.DataFrame) -> pd.DataFrame:
    """
    Create agg_col based on journal type:
      - 'ref' for Purchase
      - 'move_name' for Sales
      - 'UNKNOWN' for anything else

    Also:
      - formats agg_col to exactly 10 characters:
          * if longer: keep last 10 chars
          * if shorter: left-pad with zeros
      - prints some basic stats
    """
    required_cols = ["journal_type", "purchase_ref", "sales_move_name"]
    missing_cols = [col for col in required_cols if col not in journal_df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns for agg_col: {missing_cols}")

    df = journal_df.copy()

    def _agg_source(row: pd.Series) -> str:
        jtype = row["journal_type"]
        if jtype == "Purchase":
            return row["purchase_ref"]
        elif jtype == "Sales":
            return row["sales_move_name"]
        else:
            # cleaned up from the old 'what the fuck' string
            return "UNKNOWN"

    df["agg_col"] = df.apply(_agg_source, axis=1)

    # Format agg_col to exactly 10 characters
    def format_agg_col(x):
        if pd.notna(x):
            x_str = str(x)
            if len(x_str) > 10:
                return x_str[-10:]  # last 10 chars
            else:
                return x_str.zfill(10)  # pad with zeros
        else:
            return None

    df["agg_col"] = df["agg_col"].apply(format_agg_col)

    # Log some stats
    purchase_count = (df["journal_type"] == "Purchase").sum()
    sales_count = (df["journal_type"] == "Sales").sum()
    other_count = len(df) - purchase_count - sales_count

    print("agg_col creation stats:")
    print(f"  - Purchase entries: {purchase_count} (using 'ref')")
    print(f"  - Sales entries: {sales_count} (using 'move_name')")
    print(f"  - Other entries: {other_count}")
    print(f"  - Unique agg_col values: {df['agg_col'].nunique()}")

    return df
