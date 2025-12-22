from __future__ import annotations

from typing import Dict, Any, Tuple

import pandas as pd

from .journal import create_agg_col


def create_empty_df(schema: Dict[str, Any]) -> pd.DataFrame:
    """
    Create an empty DataFrame with columns defined by the schema.

    Columns are ordered by schema['fields'][*]['id'].
    """
    fields = sorted(schema["fields"], key=lambda x: x["id"])
    columns = [field["internal_name"] for field in fields]
    return pd.DataFrame(columns=columns)


def create_output_row(
    journal_row: pd.Series,
    schema: Dict[str, Any],
    row_number: int,
    company: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create a new output row (as dict) with ALL columns from schema,
    initialized with sensible defaults and populated from the journal row.

    This is used as a base for both PRODAGBI and POKUPKI rows.
    """
    row_data: Dict[str, Any] = {}

    # Initialize ALL columns from schema with appropriate default values
    for field in schema["fields"]:
        field_name = field["internal_name"]

        # Set default values based on field type
        if field.get("is_amount"):
            row_data[field_name] = 0.0  # Amount fields default to 0.0
        elif field["type"] == "float64":
            row_data[field_name] = 0.0  # Float fields default to 0.0
        elif field["type"] == "object":
            row_data[field_name] = ""  # String fields default to empty string
        else:
            row_data[field_name] = None  # Other fields default to None

    # Map specific fields from journal row
    if "partner_id/vat" in journal_row:
        row_data["vat_number"] = company["vat"]
        row_data["counterparty_vat"] = (
            journal_row["partner_id/vat"]
            if pd.notna(journal_row["partner_id/vat"]) and journal_row["partner_id/vat"] != ""
            else "999999999"
        )
        row_data["counterparty_name"] = journal_row.get("partner_id", "")

    if "date" in journal_row:
        # Prefer parsed date_dt if available
        if "date_dt" in journal_row and pd.notnull(journal_row["date_dt"]):
            dt = journal_row["date_dt"]
            row_data["tax_period"] = dt.strftime("%Y%m")  # YYYYMM
            row_data["document_date"] = dt.strftime("%d/%m/%Y")  # dd/MM/YYYY
        else:
            # Fallback if something unexpected happens
            try:
                dt = pd.to_datetime(journal_row["date"], dayfirst=True, format="%Y-%m-%d")
                row_data["tax_period"] = dt.strftime("%Y%m")
                row_data["document_date"] = dt.strftime("%d/%m/%Y")
            except Exception:
                row_data["tax_period"] = ""
                row_data["document_date"] = journal_row["date"]

    # Use agg_col for document number (already created in create_agg_col)
    if "agg_col" in journal_row:
        row_data["document_number"] = journal_row["agg_col"]

    # Set sequential row number (as string)
    row_data["journal_row_number"] = str(row_number)

    # Format document_type from move_id/l10n_bg_document_type with leading zero if needed
    if "move_id/l10n_bg_document_type" in journal_row:
        row_data["document_type"] = str(journal_row["move_id/l10n_bg_document_type"]).zfill(2)
    else:
        row_data["document_type"] = "!!"  # Fallback

    # Hardcode goods_or_service_description for each schema
    schema_name = schema.get("schema_name", "")

    has_gos_field = any(
        f.get("internal_name") == "goods_or_service_description"
        for f in schema.get("fields", [])
    )

    if has_gos_field:
        if schema_name == "prodagbi_schema":
            # Sales journal
            row_data["goods_or_service_description"] = "продажба стока/услуга"
        elif schema_name == "pokupki_schema":
            # Purchases journal
            row_data["goods_or_service_description"] = "покупка стока/услуга"

    # Set default values for other required fields
    row_data["branch_number"] = 0  # Default branch number

    return row_data


def process_journal(
    journal_df: pd.DataFrame,
    tax_mapping: Dict[str, Any],
    prodagbi_schema: Dict[str, Any],
    pokupki_schema: Dict[str, Any],
    company: Dict[str, Any],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Main processing logic:
      - build agg_col
      - group by document (agg_col + partner + date)
      - aggregate amounts into PRODAGBI and POKUPKI tables
    """
    # Create empty output DataFrames
    prodagbi_df = create_empty_df(prodagbi_schema)
    pokupki_df = create_empty_df(pokupki_schema)

    # Mapping from schema field id -> column name
    prodagbi_id_to_col = {field["id"]: field["internal_name"] for field in prodagbi_schema["fields"]}
    pokupki_id_to_col = {field["id"]: field["internal_name"] for field in pokupki_schema["fields"]}

    # CREATE AGG_COL BEFORE PROCESSING
    print("Creating agg_col for grouping.")
    journal_df = create_agg_col(journal_df)

    # Set default VAT for empty partner_id/vat before grouping
    if "partner_id/vat" in journal_df.columns:
        journal_df["partner_id/vat"] = journal_df["partner_id/vat"].fillna("999999999")
        journal_df["partner_id/vat"] = journal_df["partner_id/vat"].replace("", "999999999")
    else:
        raise ValueError("Journal data must contain 'partner_id/vat' column")

    print(f"Total journal rows: {len(journal_df)}")

    # Group by document (using agg_col, partner_id/vat, and date as document identifier)
    document_groups = journal_df.groupby(["agg_col", "partner_id/vat", "date"])
    print(f"Found {len(document_groups)} document groups")

    # Counters for sequential row numbers
    prodagbi_row_counter = 1
    pokupki_row_counter = 1

    # Process each document group
    for (doc_ref, counterparty_vat, doc_date), group_df in document_groups:
        # print(f"\nProcessing document: {doc_ref} | {counterparty_vat} | {doc_date}")
        # print(f"  Journal entries in this document: {len(group_df)}")

        # Collect ALL tax tags and amounts for this document
        document_prodagbi_columns: Dict[int, float] = {}
        document_pokupki_columns: Dict[int, float] = {}

        # Process each journal entry in this document
        for idx, row in group_df.iterrows():
            tax_tags_str = str(row["tax_tag_ids"])

            # Better parsing for multiple tags - remove quotes first, then split
            clean_tags_str = tax_tags_str.replace("'", "").replace('"', "")
            tax_tags = [tag.strip() for tag in clean_tags_str.split(",") if tag.strip()]

            # Get amount based on journal type
            jtype = row["journal_id/type"]
            jtype = row["journal_id/.id"]

            if jtype == "10":
                amount = row["debit"] if row["debit"] > 0 else -row["credit"]
            elif jtype == "9":
                amount = -row["debit"] if row["debit"] > 0 else row["credit"]
            else:
                amount = row["debit"] - row["credit"]

            # Process all tax tags for this journal entry
            for tag in tax_tags:
                mapping = next(
                    (m for m in tax_mapping["tax_grid_mapping"] if m["tax_grid"] == tag),
                    None,
                )

                if not mapping:
                    continue

                # Add to PRODAGBI if mapped
                if mapping["prodagbi_columns"]:
                    for col_id in mapping["prodagbi_columns"]:
                        if col_id not in document_prodagbi_columns:
                            document_prodagbi_columns[col_id] = 0.0
                        document_prodagbi_columns[col_id] += amount

                # Add to POKUPKI if mapped
                if mapping["pokupki_columns"]:
                    for col_id in mapping["pokupki_columns"]:
                        if col_id not in document_pokupki_columns:
                            document_pokupki_columns[col_id] = 0.0
                        document_pokupki_columns[col_id] += amount

        # Create one PRODAGBI row per document (if there are amounts)
        if document_prodagbi_columns:
            base_row = create_output_row(group_df.iloc[0], prodagbi_schema, prodagbi_row_counter, company)
            prodagbi_new_row = base_row.copy()

            for col_id, amount in document_prodagbi_columns.items():
                col_name = prodagbi_id_to_col[col_id]
                prodagbi_new_row[col_name] = amount

            if len(prodagbi_df) == 0:
                prodagbi_df = pd.DataFrame([prodagbi_new_row])
            else:
                prodagbi_df = pd.concat([prodagbi_df, pd.DataFrame([prodagbi_new_row])], ignore_index=True)

            prodagbi_row_counter += 1

        # Create one POKUPKI row per document (if there are amounts)
        if document_pokupki_columns:
            base_row = create_output_row(group_df.iloc[0], pokupki_schema, pokupki_row_counter, company)
            pokupki_new_row = base_row.copy()

            for col_id, amount in document_pokupki_columns.items():
                col_name = pokupki_id_to_col[col_id]
                pokupki_new_row[col_name] = amount

            if len(pokupki_df) == 0:
                pokupki_df = pd.DataFrame([pokupki_new_row])
            else:
                pokupki_df = pd.concat([pokupki_df, pd.DataFrame([pokupki_new_row])], ignore_index=True)

            pokupki_row_counter += 1

    return prodagbi_df, pokupki_df
