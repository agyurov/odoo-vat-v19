from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def create_output_folder(company: Dict[str, Any], accounting_period: str) -> Path:
    """
    Create an output folder under the project root with versioning.

    Pattern:
        VAT_<CompanyNameCleaned>_<YYYYMM>_vN

    Example:
        VAT_FAC_Doema_LTD_202511_v1
    """
    display_name = company.get("display_name") or company.get("legal_name") or "UnknownCompany"

    # Clean company display name for folder name (remove special characters)
    clean_company_name = re.sub(r'[<>:"/\\|?*]', "", display_name).replace(" ", "_")

    base_folder_name = f"VAT_{clean_company_name}_{accounting_period}"
    base_path = PROJECT_ROOT

    # Find existing versions
    existing_versions = []
    pattern = re.compile(rf"^{re.escape(base_folder_name)}_v(\d+)$")

    for item in base_path.iterdir():
        if item.is_dir():
            m = pattern.match(item.name)
            if m:
                existing_versions.append(int(m.group(1)))

    next_version = max(existing_versions) + 1 if existing_versions else 1
    folder_name = f"{base_folder_name}_v{next_version}"

    output_path = base_path / folder_name
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"Created output folder: {output_path}")
    return output_path


def format_value_for_txt(value, field_def: Dict[str, Any]) -> str:
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
    length = field_def.get("length")
    if length is None:
        raise ValueError(f"Field {field_def.get('internal_name')} missing 'length' in schema")

    field_type = field_def.get("type", "object")
    is_amount = field_def.get("is_amount", False)
    decimals = field_def.get("decimals", 2)

    # Defaults:
    #   - amounts: right, SPACE padded, show decimals
    #   - numeric (non-amount): right, SPACE padded
    #   - strings: left, SPACE padded
    if is_amount:
        align = field_def.get("align", "right")
        fill_char = field_def.get("fill_char", " ")
    elif field_type in ("float64", "int64"):
        align = field_def.get("align", "right")
        fill_char = field_def.get("fill_char", " ")
    else:
        align = field_def.get("align", "left")
        fill_char = field_def.get("fill_char", " ")

    # Normalize missing values
    if pd.isna(value):
        if is_amount or field_type in ("float64", "int64"):
            value = 0
        else:
            value = ""

    # Build raw string
    if is_amount:
        try:
            num = float(value)
        except Exception:
            num = 0.0
        s = f"{num:.{decimals}f}"
    elif field_type in ("float64", "int64"):
        try:
            num = float(value)
        except Exception:
            num = 0.0
        if field_type == "int64":
            s = str(int(round(num)))
        else:
            s = f"{num:.{decimals}f}"
    else:
        s = str(value)

    # Trim if too long
    if len(s) > length:
        s = s[:length]

    # Pad to fixed length
    if align == "right":
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


def df_to_fixed_width_txt(
    df: pd.DataFrame,
    schema: Dict[str, Any],
    output_path: Path,
    encoding: str = "cp1251",
) -> None:
    """
    Write DataFrame to fixed-width TXT using the schema definition.

    One line per row, fields ordered by schema['fields'][*]['id'].
    """
    fields = sorted(schema["fields"], key=lambda f: f["id"])

    lines = []
    for _, row in df.iterrows():
        parts = []
        for field in fields:
            col_name = field["internal_name"]
            value = row[col_name] if col_name in df.columns else None
            parts.append(format_value_for_txt(value, field))
        line = "".join(parts)
        lines.append(line)

    output_path = Path(output_path)

    with output_path.open("w", encoding=encoding, newline="") as f:
        for line in lines:
            # NRA tools normally expect Windows-style line endings
            f.write(line + "\r\n")

    print(f"Wrote {len(lines)} lines to {output_path}")
