from __future__ import annotations

from typing import Dict, Any
import re

import pandas as pd


def select_company(journal_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Extract company info from the journal CSV.

    Expects columns:
      - 'company_id'          -> company name
      - 'company_id/vat'   -> VAT number

    Assumes all rows belong to the same company.
    """
    required_cols = ["Company", "company_id/vat"]
    missing = [c for c in required_cols if c not in journal_df.columns]
    if missing:
        raise ValueError(f"Missing required columns in journal for company info: {missing}")

    # Get unique non-empty values
    company_names = (
        journal_df["Company"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )
    tax_ids = (
        journal_df["company_id/vat"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )

    if len(company_names) == 0 or len(tax_ids) == 0:
        raise ValueError(
            "Could not find non-empty values for 'company_id' and 'company_id/vat' in journal."
        )

    if len(company_names) > 1:
        print("WARNING: Multiple different Company names found in journal. Using the first one.")
        print("  Unique Company values:", list(company_names))
    if len(tax_ids) > 1:
        print("WARNING: Multiple different company_id/vat values found in journal. Using the first one.")
        print("  Unique company_id/vat values:", list(tax_ids))

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

    # Convert dates to datetime and find the maximum date
    try:
        journal_df["date_dt"] = pd.to_datetime(
            journal_df["date"],
            dayfirst=True,
            format="%d/%m/%Y",
        )
        max_date = journal_df["date_dt"].max()
        accounting_period = max_date.strftime("%Y%m")  # YYYYMM format
        return accounting_period
    except Exception as e:
        raise ValueError(f"Error parsing dates from 'date' column: {e}")


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
    required_cols = ["journal_id/type", "ref", "move_name"]
    missing_cols = [col for col in required_cols if col not in journal_df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns for agg_col: {missing_cols}")

    df = journal_df.copy()

    def _agg_source(row: pd.Series) -> str:
        jtype = row["journal_id/type"]
        if jtype == "Purchase":
            return row["ref"]
        elif jtype == "Sales":
            return row["move_name"]
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
    purchase_count = (df["journal_id/type"] == "Purchase").sum()
    sales_count = (df["journal_id/type"] == "Sales").sum()
    other_count = len(df) - purchase_count - sales_count

    print("agg_col creation stats:")
    print(f"  - Purchase entries: {purchase_count} (using 'ref')")
    print(f"  - Sales entries: {sales_count} (using 'move_name')")
    print(f"  - Other entries: {other_count}")
    print(f"  - Unique agg_col values: {df['agg_col'].nunique()}")

    return df
