"""data_engine.py — CSV loading and column-to-variable mapping.

Pure functions, no UI dependency.
"""

import csv
import io
from pathlib import Path
from typing import List

from project_io import TextBoxDef


def load_csv(path: str | Path) -> tuple[List[str], List[dict]]:
    """Read a CSV file.

    Returns (headers, rows) where each row is an OrderedDict-like dict
    keyed by header name.
    Raises ValueError on empty or unreadable files.
    """
    text = Path(path).read_text(encoding="utf-8-sig")  # utf-8-sig handles BOM from Excel
    return parse_csv_text(text)


def parse_csv_text(text: str) -> tuple[List[str], List[dict]]:
    """Parse CSV from a string. Useful for testing without files."""
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV has no header row")
    headers = list(reader.fieldnames)
    if not headers:
        raise ValueError("CSV header row is empty")
    rows = list(reader)
    if not rows:
        raise ValueError("CSV has no data rows")
    return headers, rows


def auto_map(headers: List[str], text_boxes: List[TextBoxDef]) -> dict[str, str]:
    """Best-effort mapping of text box variables to CSV column headers.

    Returns {variable_name: header_name} for each match found.
    Matching: exact, then case-insensitive, then underscore/space normalization.
    Unmatched variables are omitted from the result.
    """
    mapping = {}
    header_lower = {h.lower(): h for h in headers}
    header_normalized = {_normalize(h): h for h in headers}

    for box in text_boxes:
        var = box.variable
        if var in headers:
            mapping[var] = var
        elif var.lower() in header_lower:
            mapping[var] = header_lower[var.lower()]
        else:
            norm = _normalize(var)
            if norm in header_normalized:
                mapping[var] = header_normalized[norm]

    return mapping


def validate_mapping(mapping: dict[str, str], headers: List[str], text_boxes: List[TextBoxDef]) -> List[str]:
    """Check that every text box variable has a valid mapping.

    Returns list of unmapped variable names (empty = all good).
    """
    header_set = set(headers)
    unmapped = []
    for box in text_boxes:
        target = mapping.get(box.variable)
        if target is None or target not in header_set:
            unmapped.append(box.variable)
    return unmapped


def _normalize(s: str) -> str:
    """Normalize a string for fuzzy matching: lowercase, underscores→spaces, strip."""
    return s.lower().replace("_", " ").replace("-", " ").strip()
