"""Safety for files the application hands back to be opened in a spreadsheet.

A cell that starts with ``=``, ``+``, ``-``, ``@``, a tab or a carriage return is run as a formula by Excel and Sheets (CSV injection). Anything that
came from a person or a dataset must therefore be neutralised when it is EXPORTED. The stored data is never changed (the system reads it back for
analysis and training); the protection is applied on the way out.
"""
from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Iterator
from pathlib import Path

from app.services.upload_preprocessing import spreadsheet_safe


def safe_row(values: Iterable) -> list:
    return [spreadsheet_safe(v) for v in values]


def safe_csv_stream(path: Path) -> Iterator[bytes]:
    """The CSV file at ``path`` as UTF-8 bytes with every risky text cell neutralised, streamed row by row (memory stays bounded)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for i, row in enumerate(csv.reader(fh)):
            writer.writerow(safe_row(row))
            if i % 500 == 499:
                yield buf.getvalue().encode("utf-8")
                buf.seek(0), buf.truncate(0)
    yield buf.getvalue().encode("utf-8")
