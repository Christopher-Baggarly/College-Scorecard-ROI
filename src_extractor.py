"""
Targeted Row Extractor for College Scorecard Federal Dataset

The College Scorecard 'Institution-Level' file is ~200MB of UTF-8 / latin-1
encoded CSV with thousands of columns. Loading it whole into pandas for a
single-institution extraction is wasteful (and breaks on memory-constrained
deployments). This module does targeted line-by-line scanning instead.

Pattern: open file, read line by line, parse just the columns we need,
short-circuit as soon as we find the match. Never holds more than one row
in memory.
"""

import csv
import os
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional


def _detect_encoding(filepath: str) -> str:
    """
    Sniff the encoding of the CSV header. College Scorecard vintages
    have shifted between latin-1 and UTF-8 depending on year.
    """
    with open(filepath, "rb") as f:
        header_bytes = f.read(4096)
    try:
        header_bytes.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "latin-1"


def _read_header(filepath: str, encoding: str, delimiter: str) -> List[str]:
    """Read just the header row, return column names as a list."""
    with open(filepath, "r", encoding=encoding, errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        return next(reader)


def _field_indices(header: List[str], fields: List[str]) -> Dict[str, int]:
    """Map desired field names to their column indices in the header row."""
    indices = {}
    for field in fields:
        try:
            indices[field] = header.index(field)
        except ValueError:
            indices[field] = -1
    return indices


def _clean_value(raw: str) -> Optional[str]:
    """
    College Scorecard uses PrivacySuppressed sentinel values like
    'PrivacySuppressed', 'NULL', 'NA'. Normalize to None.
    """
    if raw is None:
        return None
    s = raw.strip()
    if s in ("", "NULL", "NA", "PrivacySuppressed", "Suppressed"):
        return None
    return s


def grep_rows(
    filepath: str,
    match_field: str,
    match_value: str,
    fields_to_extract: List[str],
    encoding: Optional[str] = None,
    delimiter: str = ",",
) -> Optional[Dict[str, Optional[str]]]:
    """
    Targeted row extraction. Reads one line at a time, stops as soon
    as the match field is found, returns only the requested columns.

    Memory ceiling: one CSV row (a few KB). Does not load the full file.

    Returns: dict mapping each requested field name to its string value,
             or None if the institution was not found.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Raw data file not found: {filepath}")

    if encoding is None:
        encoding = _detect_encoding(filepath)

    header = _read_header(filepath, encoding, delimiter)
    indices = _field_indices(header, fields_to_extract)

    if match_field not in header:
        raise ValueError(
            f"Match field '{match_field}' not found in header. "
            f"First 20 columns: {header[:20]}"
        )

    match_idx = header.index(match_field)
    # Re-prepend the match field to the extract list if not already there
    if match_field not in fields_to_extract:
        fields_with_match = [match_field] + list(fields_to_extract)
        indices[match_field] = match_idx
    else:
        fields_with_match = list(fields_to_extract)

    match_pattern = re.compile(re.escape(str(match_value).strip()))

    with open(filepath, "r", encoding=encoding, errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        next(reader)  # Skip header row

        for row_num, row in enumerate(reader, start=2):
            if row_num % 100000 == 0:
                # Heartbeat for very large files
                print(f"  [extractor] Scanned {row_num:,} rows...")

            if len(row) <= match_idx:
                continue

            if match_pattern.match(row[match_idx].strip()):
                # Match found — extract only requested fields, return immediately
                extracted = {}
                for field in fields_with_match:
                    idx = indices.get(field, -1)
                    if idx >= 0 and idx < len(row):
                        extracted[field] = _clean_value(row[idx])
                    else:
                        extracted[field] = None
                return extracted

    return None  # No match found in file


def grep_rows_multi(
    filepath: str,
    match_field: str,
    match_values: List[str],
    fields_to_extract: List[str],
    encoding: Optional[str] = None,
    delimiter: str = ",",
) -> Dict[str, Optional[Dict[str, Optional[str]]]]:
    """
    Batch extraction. Pass a list of UNITIDs (or other match values),
    get a dict mapping each match value to its extracted row.

    More memory-efficient than calling grep_rows N times because
    the file is only opened once and scanned once.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Raw data file not found: {filepath}")

    if encoding is None:
        encoding = _detect_encoding(filepath)

    header = _read_header(filepath, encoding, delimiter)
    indices = _field_indices(header, fields_to_extract)

    if match_field not in header:
        raise ValueError(f"Match field '{match_field}' not found in header.")

    match_idx = header.index(match_field)
    target_set = {str(v).strip() for v in match_values}
    results: Dict[str, Optional[Dict[str, Optional[str]]]] = {v: None for v in match_values}

    fields_with_match = (
        [match_field] + list(fields_to_extract)
        if match_field not in fields_to_extract
        else list(fields_to_extract)
    )
    indices[match_field] = match_idx

    with open(filepath, "r", encoding=encoding, errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        next(reader)

        for row_num, row in enumerate(reader, start=2):
            if row_num % 100000 == 0:
                print(f"  [extractor] Scanned {row_num:,} rows...")

            if len(row) <= match_idx:
                continue

            key = row[match_idx].strip()
            if key in target_set:
                extracted = {}
                for field in fields_with_match:
                    idx = indices.get(field, -1)
                    if idx >= 0 and idx < len(row):
                        extracted[field] = _clean_value(row[idx])
                    else:
                        extracted[field] = None
                results[key] = extracted
                target_set.discard(key)
                if not target_set:
                    break

    return results


if __name__ == "__main__":
    print("extractor.py loaded as a module. Import grep_rows or grep_rows_multi.")