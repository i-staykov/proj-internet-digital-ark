"""Normalization and salvage audit over the provided baseline files.

One CSV row per line the canonicalizer corrected or dropped: original value,
normalized value, reason, validation result, source file, year. Required by
the delivery spec so every correction is deterministic and inspectable.
"""

import csv
from pathlib import Path

from loguru import logger
from tqdm import tqdm

from ark.canonical import reject_reason, to_registrable
from ark.ingest import YEARS

AUDIT_PATH = Path("data/reports/normalization_audit.csv")
FIELDS = ["original", "normalized", "reason", "result", "source_file", "year"]


def change_reason(raw: str, normalized: str) -> str:
    """Deterministic label for why a kept line differs from its original."""
    low = raw.strip().lower()
    if low.strip(".,") == normalized:
        return "case, trailing dot or separator punctuation"
    if low == f"www.{normalized}":
        return "www prefix removed"
    if low.endswith(f".{normalized}"):
        return "subdomain collapsed to registered domain"
    return "url parts or encoding normalized"


def write_audit(legacy_dir: Path, out_path: Path = AUDIT_PATH) -> dict[str, int]:
    """Scan all year files; record every corrected or dropped line."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    stats = {"lines": 0, "unchanged": 0, "corrected": 0, "dropped": 0}
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(FIELDS)
        for year in YEARS:
            path = legacy_dir / f"{year}.txt"
            with path.open(encoding="utf-8", errors="replace") as lines:
                for line in tqdm(lines, desc=path.name, unit=" lines"):
                    raw = line.strip()
                    if not raw:
                        continue
                    stats["lines"] += 1
                    normalized = to_registrable(raw)
                    if normalized is None:
                        stats["dropped"] += 1
                        writer.writerow([raw, "", reject_reason(raw), "dropped", path.name, year])
                    elif normalized != raw:
                        stats["corrected"] += 1
                        writer.writerow(
                            [
                                raw,
                                normalized,
                                change_reason(raw, normalized),
                                "valid",
                                path.name,
                                year,
                            ]
                        )
                    else:
                        stats["unchanged"] += 1
    logger.info(f"audit written to {out_path}: {stats}")
    return stats
