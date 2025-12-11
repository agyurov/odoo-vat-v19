import pandas as pd
import json
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from tkinter import ttk
import os
from pathlib import Path
import re
from datetime import datetime

def get_user_parameters(deklar_mapping):
    """
    Show a Tkinter window to:
      - choose the journal CSV
      - override submitter, EGN
      - override 'pop-up, default 0' deklar fields (manual_or_constant)
    Returns:
      dict with keys:
        - journal_file_path
        - submitter_person
        - egn
        - deklar_fields: {deklar_column_name: value_as_string}
      or None if user cancels.
    """
    root = tk.Tk()
    root.title("VAT Deklar Parameters")

    params = {
        "journal_file_path": None,
        "submitter_person": None,
        "egn": None,
        "deklar_fields": {}
    }

    file_var = tk.StringVar()

    def choose_file():
        path = filedialog.askopenfilename(
            title="Select Journal CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir="data"
        )
        if path:
            file_var.set(path)

    row = 0
    tk.Label(root, text="Journal CSV file:").grid(row=row, column=0, sticky="w")
    tk.Button(root, text="Browse...", command=choose_file).grid(row=row, column=1, sticky="w")
    row += 1
    tk.Label(root, textvariable=file_var, wraplength=500).grid(row=row, column=0, columnspan=2, sticky="w")
    row += 1

    # Submitter + EGN
    submitter_var = tk.StringVar(value="Емилия Гюрова")
    egn_var = tk.StringVar(value="6111146394")

    tk.Label(root, text="Submitter (Подател):").grid(row=row, column=0, sticky="w", pady=(10, 0))
    tk.Entry(root, textvariable=submitter_var, width=40).grid(row=row, column=1, sticky="w", pady=(10, 0))
    row += 1

    tk.Label(root, text="ЕГН:").grid(row=row, column=0, sticky="w")
    tk.Entry(root, textvariable=egn_var, width=40).grid(row=row, column=1, sticky="w")
    row += 1

    # Pop-up deklar fields (manual_or_constant → your "pop-up, default 0")
    tk.Label(root, text="Deklar pop-up fields:").grid(row=row, column=0, columnspan=2, sticky="w", pady=(10, 0))
    row += 1

    popup_fields = [
        m for m in deklar_mapping.get('fields', [])
        if m.get('source_kind') == 'manual_or_constant'
    ]

    field_vars = {}
    for m in popup_fields:
        colname = m['deklar_column']
        default_val = m.get('default_value', 0)
        v = tk.StringVar(value=str(default_val))
        field_vars[colname] = v
        tk.Label(root, text=colname + ":").grid(row=row, column=0, sticky="w")
        tk.Entry(root, textvariable=v, width=20).grid(row=row, column=1, sticky="w")
        row += 1

    def on_run():
        if not file_var.get():
            messagebox.showerror("Missing file", "Please choose a journal CSV file.")
            return
        params['journal_file_path'] = file_var.get()
        params['submitter_person'] = submitter_var.get()
        params['egn'] = egn_var.get()
        deklar_values = {}
        for colname, var in field_vars.items():
            deklar_values[colname] = var.get()
        params['deklar_fields'] = deklar_values
        root.destroy()

    def on_cancel():
        root.destroy()

    tk.Button(root, text="Run", command=on_run).grid(row=row, column=0, pady=10)
    tk.Button(root, text="Cancel", command=on_cancel).grid(row=row, column=1, pady=10)

    root.mainloop()

    if not params['journal_file_path']:
        # User closed/cancelled without choosing a file
        return None
    return params


def select_company(journal_df):
    """
    Extract company info from the journal CSV.

    Expects columns:
      - 'Company'          -> company name
      - 'Company/Tax ID'   -> VAT number

    Assumes all rows belong to the same company.
    """
    required_cols = ['Company', 'Company/Tax ID']
    missing = [c for c in required_cols if c not in journal_df.columns]
    if missing:
        raise ValueError(f"Missing required columns in journal for company info: {missing}")

    # Get unique non-empty values
    company_names = journal_df['Company'].dropna().astype(str).str.strip().unique()
    tax_ids = journal_df['Company/Tax ID'].dropna().astype(str).str.strip().unique()

    if len(company_names) == 0 or len(tax_ids) == 0:
        raise ValueError(
            "Could not find non-empty values for 'Company' and 'Company/Tax ID' in journal."
        )

    if len(company_names) > 1:
        print("WARNING: Multiple different Company names found in journal. Using the first one.")
        print("  Unique Company values:", list(company_names))
    if len(tax_ids) > 1:
        print("WARNING: Multiple different Company/Tax ID values found in journal. Using the first one.")
        print("  Unique Company/Tax ID values:", list(tax_ids))

    company_name = company_names[0]
    tax_id = tax_ids[0]

    # Optional: numeric version (strip non-digits), in case you want it later
    vat_numeric = re.sub(r'\D', '', tax_id)

    company = {
        "id": "from_csv",
        "display_name": company_name,
        "legal_name": company_name,
        "country_code": "BG",          # adjust if needed
        "vat": tax_id,
        "vat_numeric": vat_numeric,
        "bulstat": vat_numeric,
        "default": True,
    }

    print(f"Using company from journal: {company_name} ({tax_id})")
    return company



def load_schemas():
    """Load all schema files"""
    with open('templates/prodagbi_schema.json', 'r', encoding='utf-8') as f:
        prodagbi_schema = json.load(f)
    with open('templates/pokupki_schema.json', 'r', encoding='utf-8') as f:
        pokupki_schema = json.load(f)
    with open('templates/deklar_schema.json', 'r', encoding='utf-8') as f:
        deklar_schema = json.load(f)
    with open('templates/tax_grid_mapping.json', 'r', encoding='utf-8') as f:
        tax_mapping = json.load(f)
    with open('templates/deklar_mapping.json', 'r', encoding='utf-8') as f:
        deklar_mapping = json.load(f)

    return prodagbi_schema, pokupki_schema, deklar_schema, tax_mapping, deklar_mapping


def select_journal_file():
    """Open file dialog to select journal.csv file"""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    file_path = filedialog.askopenfilename(
        title="Select Journal CSV File",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        initialdir="data"  # Start in data directory if it exists
    )
    
    root.destroy()
    return file_path

def get_accounting_period(journal_df):
    """Extract accounting period (YYYYMM) from journal data using max date"""
    if 'date' not in journal_df.columns:
        raise ValueError("Journal data must contain 'date' column")
    
    # Convert dates to datetime and find the maximum date
    try:
        journal_df['date_dt'] = pd.to_datetime(journal_df['date'],dayfirst=True,format='%d/%m/%Y')
        max_date = journal_df['date_dt'].max()
        accounting_period = max_date.strftime('%Y%m')  # YYYYMM format
        return accounting_period
    except Exception as e:
        raise ValueError(f"Error parsing dates: {e}")

def create_agg_col(journal_df):
    """Create agg_col based on journal type: ref for Purchase, move_name for Sales"""
    # Check if required columns exist
    required_cols = ['journal_id/type', 'ref', 'move_name']
    missing_cols = [col for col in required_cols if col not in journal_df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns for agg_col: {missing_cols}")
    
    # Create the agg_col based on the rules
    journal_df = journal_df.copy()
    journal_df['agg_col'] = journal_df.apply(
        lambda row: row['ref'] if row['journal_id/type'] == 'Purchase' 
        else row['move_name'] if row['journal_id/type'] == 'Sales' 
        else "what the fuck",
        axis=1
    )
    
    # Format agg_col to exactly 10 characters: trim if longer, pad with zeros if shorter
    def format_agg_col(x):
        if pd.notna(x):
            x_str = str(x)
            if len(x_str) > 10:
                return x_str[-10:]  # Trim to 10 chars if longer
            else:
                return x_str.zfill(10)  # Pad with zeros if shorter
        else:
            return None
    
    journal_df['agg_col'] = journal_df['agg_col'].apply(format_agg_col)
    
    # Log statistics about the created agg_col
    purchase_count = (journal_df['journal_id/type'] == 'Purchase').sum()
    sales_count = (journal_df['journal_id/type'] == 'Sales').sum()
    other_count = len(journal_df) - purchase_count - sales_count
    
    print(f"agg_col creation stats:")
    print(f"  - Purchase entries: {purchase_count} (using 'ref')")
    print(f"  - Sales entries: {sales_count} (using 'move_name')")
    print(f"  - Other entries: {other_count}")
    print(f"  - Unique agg_col values: {journal_df['agg_col'].nunique()}")
    
    return journal_df

def create_output_folder(company, accounting_period):
    """Create output folder with versioning"""
    # Clean company display name for folder name (remove special characters)
    clean_company_name = re.sub(r'[<>:"/\\|?*]', '', company['display_name']).replace(' ', '_')
    
    # Base folder name pattern
    base_folder_name = f"VAT_{clean_company_name}_{accounting_period}"
    
    # Find existing versions
    existing_versions = []
    pattern = re.compile(rf"^{base_folder_name}_v(\d+)$")
    
    for item in os.listdir('.'):
        if os.path.isdir(item):
            match = pattern.match(item)
            if match:
                existing_versions.append(int(match.group(1)))
    
    # Determine next version number
    next_version = max(existing_versions) + 1 if existing_versions else 1
    
    # Create folder name
    folder_name = f"{base_folder_name}_v{next_version}"
    
    # Create the folder
    os.makedirs(folder_name, exist_ok=True)
    print(f"Created output folder: {folder_name}")
    
    return folder_name

def create_empty_df(schema):
    """Create empty DataFrame from schema"""
    fields = sorted(schema['fields'], key=lambda x: x['id'])
    columns = [field['internal_name'] for field in fields]
    return pd.DataFrame(columns=columns)

def process_journal(journal_df, tax_mapping, prodagbi_schema, pokupki_schema, company):
    """Main processing logic - FIXED: Group by document and aggregate amounts"""
    # Create empty output DataFrames
    prodagbi_df = create_empty_df(prodagbi_schema)
    pokupki_df = create_empty_df(pokupki_schema)
    
    # Create mapping from field id to column name for each schema
    prodagbi_id_to_col = {field['id']: field['internal_name'] for field in prodagbi_schema['fields']}
    pokupki_id_to_col = {field['id']: field['internal_name'] for field in pokupki_schema['fields']}
    
    # CREATE AGG_COL BEFORE PROCESSING
    print("Creating agg_col for grouping...")
    journal_df = create_agg_col(journal_df)

    # ADD THIS: Set default VAT for empty partner_id/vat before grouping
    journal_df['partner_id/vat'] = journal_df['partner_id/vat'].fillna('999999999')
    journal_df['partner_id/vat'] = journal_df['partner_id/vat'].replace('', '999999999')
    
    # FIX: Group journal entries by document using agg_col
    print(f"Total journal rows: {len(journal_df)}")
    
    # Group by document (using agg_col, partner_id/vat, and date as document identifier)
    document_groups = journal_df.groupby(['agg_col', 'partner_id/vat', 'date'])
    
    print(f"Found {len(document_groups)} document groups")

       # Counters for sequential row numbers
    prodagbi_row_counter = 1
    pokupki_row_counter = 1
    
    # Process each document group
    for (doc_ref, counterparty_vat, doc_date), group_df in document_groups:
        # print(f"\nProcessing document: {doc_ref} | {counterparty_vat} | {doc_date}")
        # print(f"  Journal entries in this document: {len(group_df)}")
        
        # FIX: Collect ALL tax tags and amounts for this document
        document_prodagbi_columns = {}
        document_pokupki_columns = {}
        
        # Process each journal entry in this document
        for idx, row in group_df.iterrows():
            tax_tags_str = str(row['tax_tag_ids'])
            
            # Better parsing for multiple tags - remove quotes first, then split
            clean_tags_str = tax_tags_str.replace("'", "").replace('"', '')
            tax_tags = [tag.strip() for tag in clean_tags_str.split(',') if tag.strip()]
            
            # Get amount (use debit if available, else credit as negative)
            # amount = row['debit'] if row['debit'] > 0 else -row['credit']
            jtype = row['journal_id/type']
            # amount = row['balance'] # in the future the input journal csv file could contain the balance column

            if jtype == 'Purchase':
                amount = row['debit'] if row['debit'] > 0 else -row['credit']

            elif jtype == 'Sales':
                amount = -row['debit'] if row['debit'] > 0 else row['credit']

            else:
                amount = row['debit'] - row['credit']
            
            # print(f"  Journal entry {idx}: tax_tags = {tax_tags}, amount: {amount}")
            
            # Process all tax tags for this journal entry
            for tag in tax_tags:
                mapping = next((m for m in tax_mapping['tax_grid_mapping'] if m['tax_grid'] == tag), None)
                
                if mapping:
                    # Add to prodagbi if mapped
                    if mapping['prodagbi_columns']:
                        for col_id in mapping['prodagbi_columns']:
                            if col_id not in document_prodagbi_columns:
                                document_prodagbi_columns[col_id] = 0.0
                            document_prodagbi_columns[col_id] += amount
                            # print(f"    Added {amount} to prodagbi column {col_id}")
                    
                    # Add to pokupki if mapped
                    if mapping['pokupki_columns']:
                        for col_id in mapping['pokupki_columns']:
                            if col_id not in document_pokupki_columns:
                                document_pokupki_columns[col_id] = 0.0
                            document_pokupki_columns[col_id] += amount
                            # print(f"    Added {amount} to pokupki column {col_id}")
        
        # FIXED: Create ONE row per target table for this document (if there are amounts)
        if document_prodagbi_columns:
            # Create base row and make a copy to avoid dictionary mutation
            base_row = create_output_row(group_df.iloc[0], prodagbi_schema, prodagbi_row_counter, company)
            prodagbi_new_row = base_row.copy()  # Create a fresh copy for this row
            
            # Set the aggregated amounts
            for col_id, amount in document_prodagbi_columns.items():
                col_name = prodagbi_id_to_col[col_id]
                prodagbi_new_row[col_name] = amount
            
            # Add to DataFrame using the copied dictionary
            if len(prodagbi_df) == 0:
                prodagbi_df = pd.DataFrame([prodagbi_new_row])
            else:
                prodagbi_df = pd.concat([prodagbi_df, pd.DataFrame([prodagbi_new_row])], ignore_index=True)
            prodagbi_row_counter += 1
            # print(f"  FINAL: Added ONE prodagbi row with columns {list(document_prodagbi_columns.keys())}")
        
        if document_pokupki_columns:
            # Create base row and make a copy to avoid dictionary mutation
            base_row = create_output_row(group_df.iloc[0], pokupki_schema, pokupki_row_counter, company)
            pokupki_new_row = base_row.copy()  # Create a fresh copy for this row
            
            # Set the aggregated amounts
            for col_id, amount in document_pokupki_columns.items():
                col_name = pokupki_id_to_col[col_id]
                pokupki_new_row[col_name] = amount
            
            # Add to DataFrame using the copied dictionary
            if len(pokupki_df) == 0:
                pokupki_df = pd.DataFrame([pokupki_new_row])
            else:
                pokupki_df = pd.concat([pokupki_df, pd.DataFrame([pokupki_new_row])], ignore_index=True)
            pokupki_row_counter += 1
            # print(f"  FINAL: Added ONE pokupki row with columns {list(document_pokupki_columns.keys())}")
    
    return prodagbi_df, pokupki_df

def create_output_row(journal_row, schema, row_number, company):
    """Create a new output row with ALL columns from schema"""
    row_data = {}
    
    # Initialize ALL columns from schema with appropriate default values
    for field in schema['fields']:
        field_name = field['internal_name']
        
        # Set default values based on field type
        if field.get('is_amount'):
            row_data[field_name] = 0.0  # Amount fields default to 0.0
        elif field['type'] == 'float64':
            row_data[field_name] = 0.0  # Float fields default to 0.0
        elif field['type'] == 'object':
            row_data[field_name] = ''   # String fields default to empty string
        else:
            row_data[field_name] = None  # Other fields default to None
    
    # Now map specific fields from journal row
    if 'partner_id/vat' in journal_row:
        row_data['vat_number'] = company['vat']
        row_data['counterparty_vat'] = journal_row['partner_id/vat'] if pd.notna(journal_row['partner_id/vat']) and journal_row['partner_id/vat'] != '' else '999999999'
        row_data['counterparty_name'] = journal_row['partner_id']
    
    if 'date' in journal_row:
        # Prefer parsed date_dt if available
        if 'date_dt' in journal_row and pd.notnull(journal_row['date_dt']):
            dt = journal_row['date_dt']
            row_data['tax_period'] = dt.strftime('%Y%m')       # YYYYMM
            row_data['document_date'] = dt.strftime('%d/%m/%Y') # dd/MM/YYYY
        else:
            # Fallback if something unexpected happens
            try:
                dt = pd.to_datetime(journal_row['date'], dayfirst=True, format='%d/%m/%Y')
                row_data['tax_period'] = dt.strftime('%Y%m')
                row_data['document_date'] = dt.strftime('%d/%m/%Y')
            except Exception:
                row_data['tax_period'] = ''
                row_data['document_date'] = journal_row['date']

    
    # Use agg_col for document number (already created in process_journal)
    if 'agg_col' in journal_row:
        row_data['document_number'] = journal_row['agg_col']
    
    # Set sequential row number (as string)
    row_data['journal_row_number'] = str(row_number)
    
    # Format document_type from move_id/l10n_bg_document_type with leading zero if needed
    row_data['document_type'] = str(journal_row['move_id/l10n_bg_document_type']).zfill(2) if 'move_id/l10n_bg_document_type' in journal_row else '!!'
    
        # Hardcode goods_or_service_description for each schema
    schema_name = schema.get('schema_name', '')

    has_gos_field = any(
        f.get('internal_name') == 'goods_or_service_description'
        for f in schema.get('fields', [])
    )

    if has_gos_field:
        if schema_name == 'prodagbi_schema':
            # Sales journal
            row_data['goods_or_service_description'] = 'продажба стока/услуга'
        elif schema_name == 'pokupki_schema':
            # Purchases journal
            row_data['goods_or_service_description'] = 'покупка стока/услуга'

    
    # Set default values for other required fields
    row_data['branch_number'] = 0  # Default branch number
    
    return row_data

def generate_deklar(prodagbi_df, pokupki_df, deklar_schema, deklar_mapping, tax_period, company, ui_overrides=None):
    """
    Generate DEKLAR summary from PRODAGBI and POKUPKI data,
    driven by deklar_schema (types/defaults), deklar_mapping (lineage),
    and UI overrides (submitter, EGN, pop-up fields).
    """
    if ui_overrides is None:
        ui_overrides = {}

    deklar_row = {}

    # Pre-index schema by column name for type info
    schema_by_name = {f['internal_name']: f for f in deklar_schema['fields']}

    # 1) Initialize ALL columns from deklar schema with default values
    for field in deklar_schema['fields']:
        field_name = field['internal_name']
        field_type = field.get('type', 'object')

        if field_type == 'float64':
            deklar_row[field_name] = 0.0
        elif field_type == 'object':
            deklar_row[field_name] = ''
        else:
            deklar_row[field_name] = None

    # 2) Index mapping by deklar_column name for easy lookup
    mapping_by_col = {
        m['deklar_column']: m
        for m in deklar_mapping.get('fields', [])
    }

    def parse_float(value):
        try:
            s = str(value).strip().replace(',', '.')
            return float(s)
        except Exception:
            return 0.0

    # ---------- PASS 1: fill all non-expression fields ----------
    for field in deklar_schema['fields']:
        col = field['internal_name']
        m = mapping_by_col.get(col)

        if not m:
            continue

        source_kind = m.get('source_kind')

        # 2.1. Values coming from company / input context
        if source_kind == 'from_input_or_company':
            if col == 'vat_number':
                deklar_row[col] = company['vat']
            elif col == 'taxpayer_name':
                deklar_row[col] = company['legal_name']
            elif col == 'tax_period':
                deklar_row[col] = tax_period
            elif col == 'submitter_person':
                # UI override wins
                if 'submitter_person' in ui_overrides and ui_overrides['submitter_person']:
                    deklar_row[col] = ui_overrides['submitter_person']
                else:
                    deklar_row[col] = company.get('default_submitter', 'Емилия Гюрова')
            elif col == 'sales_document_count':
                deklar_row[col] = len(prodagbi_df)
            elif col == 'purchases_document_count':
                deklar_row[col] = len(pokupki_df)

        # 2.2. Sum over PRODAGBI
        elif source_kind == 'sum_prodagbi_column':
            src_col = m.get('source_column')
            if src_col and src_col in prodagbi_df.columns and len(prodagbi_df) > 0:
                deklar_row[col] = prodagbi_df[src_col].sum()
            else:
                deklar_row[col] = 0.0

        # 2.3. Sum over POKUPKI
        elif source_kind == 'sum_pokupki_column':
            src_col = m.get('source_column')
            if src_col and src_col in pokupki_df.columns and len(pokupki_df) > 0:
                deklar_row[col] = pokupki_df[src_col].sum()
            else:
                deklar_row[col] = 0.0

        # 2.4. Constants / pop-up (manual_or_constant)
        elif source_kind == 'manual_or_constant':
            # UI override wins, then default_value, then schema default
            if col in ui_overrides:
                field_type = schema_by_name.get(col, {}).get('type', 'float64')
                if field_type == 'float64':
                    deklar_row[col] = parse_float(ui_overrides[col])
                else:
                    deklar_row[col] = ui_overrides[col]
            elif 'default_value' in m:
                field_type = schema_by_name.get(col, {}).get('type', 'float64')
                if field_type == 'float64':
                    deklar_row[col] = parse_float(m['default_value'])
                else:
                    deklar_row[col] = m['default_value']
            # else: keep default from initialization

        # 2.5. Expressions handled in pass 2
        elif source_kind == 'from_deklar_expression':
            continue

        else:
            # Unknown source_kind – keep default
            continue

    # ---------- PASS 2: expression-based fields ----------
    for field in deklar_schema['fields']:
        col = field['internal_name']
        m = mapping_by_col.get(col)
        if not m:
            continue
        if m.get('source_kind') != 'from_deklar_expression':
            continue

        if col == 'total_tax_credit':
            # current simple logic: full credit only
            deklar_row[col] = deklar_row.get('purchases_vat_full_credit', 0.0)
        elif col == 'vat_due':
            sales_total_vat = deklar_row.get('sales_total_vat', 0.0)
            total_tax_credit = deklar_row.get('total_tax_credit', 0.0)
            deklar_row[col] = max(0.0, sales_total_vat - total_tax_credit)
        elif col == 'vat_refundable':
            sales_total_vat = deklar_row.get('sales_total_vat', 0.0)
            total_tax_credit = deklar_row.get('total_tax_credit', 0.0)
            deklar_row[col] = max(0.0, total_tax_credit - sales_total_vat)
        else:
            # Other future expressions could be handled here
            pass

    # Attach EGN from UI if there's a matching column in the schema
    if 'egn' in ui_overrides and ui_overrides['egn']:
        if 'submitter_egn' in deklar_row:
            deklar_row['submitter_egn'] = ui_overrides['egn']
        elif 'egn' in deklar_row:
            deklar_row['egn'] = ui_overrides['egn']

    return pd.DataFrame([deklar_row])



def format_value_for_txt(value, field_def):
    """
    Format a single value according to schema field definition for fixed-width TXT.
    Expected schema keys:
      - internal_name
      - length
      - type
      - is_amount (optional, bool)
      - decimals (optional, for amounts / floats; default 2)
      - align: 'left' or 'right' (optional)
      - fill_char: padding character (optional)
    """
    length = field_def.get('length')
    if length is None:
        raise ValueError(f"Field {field_def.get('internal_name')} missing 'length' in schema")

    field_type = field_def.get('type', 'object')
    is_amount = field_def.get('is_amount', False)
    decimals = field_def.get('decimals', 2)

    # Defaults:
    #   - amounts: right, SPACE padded, show decimals (no scaling)
    #   - numeric (non-amount): right, SPACE padded
    #   - strings: left, SPACE padded
    if is_amount:
        align = field_def.get('align', 'right')
        fill_char = field_def.get('fill_char', ' ')
    elif field_type in ('float64', 'int64'):
        align = field_def.get('align', 'right')
        fill_char = field_def.get('fill_char', ' ')
    else:
        align = field_def.get('align', 'left')
        fill_char = field_def.get('fill_char', ' ')

    # Normalize missing values
    if pd.isna(value):
        if is_amount or field_type in ('float64', 'int64'):
            value = 0
        else:
            value = ''

    # Build the raw string
    if is_amount:
        # NRA amount style: e.g. 12.31 -> '12.31', right aligned, spaces on the left
        try:
            num = float(value)
        except Exception:
            num = 0.0
        s = f"{num:.{decimals}f}"
    elif field_type in ('float64', 'int64'):
        try:
            num = float(value)
        except Exception:
            num = 0.0
        if field_type == 'int64':
            s = str(int(round(num)))
        else:
            s = f"{num:.{decimals}f}"
    else:
        s = str(value)

    # Trim if too long
    if len(s) > length:
        s = s[:length]

    # Pad to fixed length
    if align == 'right':
        s = s.rjust(length, fill_char)
    else:
        s = s.ljust(length, fill_char)

    # Safety: ensure exact length
    if len(s) != length:
        if len(s) > length:
            s = s[:length]
        else:
            s = s.ljust(length, fill_char)

    return s


def df_to_fixed_width_txt(df, schema, output_path, encoding="cp1251"):
    """
    Write DataFrame to fixed-width TXT using the schema definition.
    One line per row, fields ordered by schema['fields'][*]['id'].
    """
    fields = sorted(schema['fields'], key=lambda f: f['id'])

    lines = []
    for _, row in df.iterrows():
        parts = []
        for field in fields:
            col_name = field['internal_name']
            value = row[col_name] if col_name in df.columns else None
            parts.append(format_value_for_txt(value, field))
        line = ''.join(parts)
        lines.append(line)

    # Always create the file (even if empty DF)
    with open(output_path, 'w', encoding=encoding, newline='') as f:
        for line in lines:
            # NRA tools normally expect Windows-style line endings
            f.write(line + '\r\n')

    print(f"Wrote {len(lines)} lines to {output_path}")


# Main execution
def main():
    try:
        # Load schemas and mappings
        prodagbi_schema, pokupki_schema, deklar_schema, tax_mapping, deklar_mapping = load_schemas()

        # Show UI to pick file and override pop-up values
        ui_params = get_user_parameters(deklar_mapping)
        if ui_params is None:
            print("No file selected / operation cancelled.")
            return

        journal_file_path = ui_params['journal_file_path']
        ui_overrides = ui_params['deklar_fields']
        # add submitter + EGN into overrides
        ui_overrides['submitter_person'] = ui_params['submitter_person']
        ui_overrides['egn'] = ui_params['egn']

        print(f"Selected file: {journal_file_path}")

        # Load data with UTF-8 encoding
        journal_df = pd.read_csv(journal_file_path, encoding='utf-8')

        # Extract company from the journal CSV
        selected_company = select_company(journal_df)
        print(f"Selected company: {selected_company['display_name']} ({selected_company['vat']})")

        # Extract accounting period from max date
        accounting_period = get_accounting_period(journal_df)
        print(f"Accounting period: {accounting_period}")

        # Create output folder with versioning
        output_folder = create_output_folder(selected_company, accounting_period)

        # Print available tax grids for debugging
        print("Available tax grids in mapping:")
        for mapping in tax_mapping['tax_grid_mapping']:
            print(f"  - {mapping['tax_grid']}")
        print()

        # Process journal to create PRODAGBI and POKUPKI
        prodagbi_df, pokupki_df = process_journal(
            journal_df, tax_mapping, prodagbi_schema, pokupki_schema, selected_company
        )

        # Generate DEKLAR from the aggregated data (now using mapping + UI values)
        deklar_df = generate_deklar(
            prodagbi_df,
            pokupki_df,
            deklar_schema,
            deklar_mapping,
            accounting_period,
            selected_company,
            ui_overrides=ui_overrides
        )

        # Save as CSV in the output folder
        prodagbi_output_path = os.path.join(output_folder, 'prodagbi_output.csv')
        pokupki_output_path = os.path.join(output_folder, 'pokupki_output.csv')
        deklar_output_path = os.path.join(output_folder, 'deklar_output.csv')

        prodagbi_df.to_csv(prodagbi_output_path, index=False, encoding='utf-8', float_format='%.2f')
        pokupki_df.to_csv(pokupki_output_path, index=False, encoding='utf-8', float_format='%.2f')
        deklar_df.to_csv(deklar_output_path, index=False, encoding='utf-8', float_format='%.2f')

        # Also save fixed-width TXT files for NRA
        prodagbi_txt_path = os.path.join(output_folder, 'Prodagbi.txt')
        pokupki_txt_path = os.path.join(output_folder, 'Pokupki.txt')
        deklar_txt_path = os.path.join(output_folder, 'Deklar.txt')

        df_to_fixed_width_txt(prodagbi_df, prodagbi_schema, prodagbi_txt_path)
        df_to_fixed_width_txt(pokupki_df, pokupki_schema, pokupki_txt_path)
        df_to_fixed_width_txt(deklar_df, deklar_schema, deklar_txt_path)

        print(f"\nFinal Results:")
        print(f"Output folder: {output_folder}")
        print(f"Prodagbi: {len(prodagbi_df)} rows, {len(prodagbi_df.columns)} columns")
        print(f"Pokupki: {len(pokupki_df)} rows, {len(pokupki_df.columns)} columns")
        print(f"Deklar: {len(deklar_df)} rows, {len(deklar_df.columns)} columns")

        if len(deklar_df) > 0:
            print("\nDeklar summary:")
            print(f"Sales documents: {deklar_df['sales_document_count'].iloc[0]}")
            print(f"Purchases documents: {deklar_df['purchases_document_count'].iloc[0]}")
            print(f"Sales total VAT: {deklar_df['sales_total_vat'].iloc[0]:.2f}")
            print(f"Purchases VAT credit: {deklar_df['purchases_vat_full_credit'].iloc[0]:.2f}")
            print(f"VAT due: {deklar_df['vat_due'].iloc[0]:.2f}")

    except Exception as e:
        print(f"Error processing file: {e}")
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", f"Failed to process file:\n{e}")
        root.destroy()



if __name__ == "__main__":
    main()