"""Full review of the provided baseline: which lines we drop, and why.

Writes a complete, grouped droplist so the research group can inspect
every line our canonicalizer excludes from the provided year files.
"""

from collections import defaultdict
from pathlib import Path

from loguru import logger
from tqdm import tqdm

from ark.canonical import reject_reason
from ark.ingest import YEARS

DEFAULT_DROPLIST_PATH = Path("output/legacy_review/dropped_domains.txt")


def review_legacy(legacy_dir: Path, out_path: Path = DEFAULT_DROPLIST_PATH) -> dict[str, int]:
    """Scan all year files, group dropped lines by reason, write the droplist."""
    # (reason, raw line) -> year files it occurs in
    occurrences: dict[tuple[str, str], set[str]] = defaultdict(set)
    total_lines = 0
    for year in YEARS:
        path = legacy_dir / f"{year}.txt"
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in tqdm(fh, desc=path.name, unit=" lines"):
                raw = line.strip()
                if not raw:
                    continue
                total_lines += 1
                reason = reject_reason(raw)
                if reason is not None:
                    occurrences[(reason, raw)].add(path.name)

    by_reason: dict[str, list[tuple[str, set[str]]]] = defaultdict(list)
    for (reason, raw), files in occurrences.items():
        by_reason[reason].append((raw, files))
    dropped_lines = sum(len(files) for files in occurrences.values())

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        fh.write("# Lines from the provided 1996-2001 year files that the pipeline drops\n")
        fh.write("# Reproduce with: uv run ark legacy-review (see README)\n")
        fh.write(f"# {dropped_lines} dropped lines ({len(occurrences)} distinct entries) ")
        fh.write(f"out of {total_lines} lines ({dropped_lines / total_lines:.3%})\n\n")
        for reason in sorted(by_reason, key=lambda r: len(by_reason[r]), reverse=True):
            entries = sorted(by_reason[reason])
            fh.write(f"## {reason} ({len(entries)} distinct entries)\n")
            for raw, files in entries:
                fh.write(f"{raw}\t[{', '.join(sorted(files))}]\n")
            fh.write("\n")

    counts = {reason: len(entries) for reason, entries in by_reason.items()}
    logger.info(f"droplist written to {out_path}: {counts}")
    return counts
