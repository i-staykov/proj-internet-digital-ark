"""Audit CSV: one row per corrected or dropped baseline line."""

import csv
from pathlib import Path

from ark.audit import write_audit
from ark.ingest import YEARS


def test_write_audit(tmp_path: Path) -> None:
    for year in YEARS:
        (tmp_path / f"{year}.txt").write_text("clean.com\n", encoding="utf-8")
    # 1996 additionally gets one corrected and one dropped line
    (tmp_path / "1996.txt").write_text(
        "clean.com\nwww.corrected.com\n$garbage$\n", encoding="utf-8"
    )

    out = tmp_path / "audit.csv"
    stats = write_audit(tmp_path, out)

    assert stats == {"lines": 8, "unchanged": 6, "corrected": 1, "dropped": 1}
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert len(rows) == 2
    corrected = next(r for r in rows if r["result"] == "valid")
    assert corrected["original"] == "www.corrected.com"
    assert corrected["normalized"] == "corrected.com"
    assert corrected["reason"] == "www prefix removed"
    assert corrected["source_file"] == "1996.txt"
    dropped = next(r for r in rows if r["result"] == "dropped")
    assert dropped["original"] == "$garbage$"
    assert dropped["normalized"] == ""
    assert dropped["reason"]
