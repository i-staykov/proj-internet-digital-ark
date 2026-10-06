"""Take one reviewer release: verify the zip, extract it, remeasure it, point the figures at it.

The baseline goes stale between his release and our next measurement, and every hour
collected against a stale denominator prices itself wrong. So the whole intake is one
command, and the order is fixed:

    checksum -> extract -> count -> measure -> data/baseline.json -> docs/registers/releases.md
    -> docs/registers/rounds.md (only with --mail)

    uv run python scripts/round/intake.py feedback/feedback-phase-8/his.zip
    uv run python scripts/round/intake.py his.zip --mail private/mail/verdict7.txt \\
        --round 7 --received "2026-09-02 05:50"
    uv run python scripts/round/intake.py his.zip --dry-run

**Every figure is read from the extracted files, never from his mail.** The pairs are
`wc -l` over the six core year files and the 2002 to 2015 files present (the extended
baseline, kept apart), and the equivalent-English is his own calculator run over each,
because the mail quotes a merge we cannot check and the files are what every diff against
him reads.

The run is idempotent: a second run on the same zip re-reads what is there, writes
nothing and says so, and the expensive step is skipped when the JSON already carries
this release with the same line counts (`--recompute` forces it). It refuses rather
than half-applying: a marker already recorded under a different sha256 stops the run
before anything is written.

Writing the held sets is not part of this script: `just intake` runs `uv run ark intake`
after it, on the release this points `data/baseline.json` at.
"""

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path


def _load(name: str):
    """Import a sibling script by path: `scripts/` is not a package."""
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


releases = _load("releases")

# Imported here, before anything writes, on purpose: `rounds` reads `ark.baseline` at
# import time, and the benchmark stamp a new round defaults to is the release he scored
# against, which is the one this run is about to replace.
rounds = _load("rounds")

from ark.baseline import EXTENDED_YEARS, calculator_path  # noqa: E402

BASELINE_JSON = Path("data/baseline.json")
YEARS = releases.YEARS
FOUR_PLACES = Decimal("0.0001")


@contextmanager
def step(label: str) -> Iterator[None]:
    """Wall time per step, so a slow intake says which part was slow."""
    start = time.monotonic()
    print(f"{label}:")
    try:
        yield
    finally:
        print(f"  {time.monotonic() - start:.2f}s")


def run_module(module, argv: list[str]) -> None:
    """Call a sibling script's `main()` with our own argument list."""
    saved = sys.argv
    sys.argv = argv
    try:
        module.main()
    finally:
        sys.argv = saved


def marker_of(zip_path: Path, chosen: str | None) -> str:
    """The release a zip holds, read from its member list rather than from its name."""
    markers = releases.zip_markers(zip_path)
    if chosen:
        if chosen not in markers:
            raise SystemExit(f"{zip_path}: holds {sorted(markers) or 'no marker'}, not {chosen}")
        return chosen
    if len(markers) != 1:
        raise SystemExit(f"{zip_path}: holds {sorted(markers) or 'no marker'}; pass --marker")
    return markers.pop()


def zip_stamp(zip_path: Path) -> str | None:
    """The newest member's own timestamp, `YYYY-MM-DD HH:MM`, written by his packer."""
    with zipfile.ZipFile(zip_path) as zf:
        stamps = [info.date_time for info in zf.infolist() if not info.is_dir()]
    if not stamps:
        return None
    y, mo, d, h, mi, _ = max(stamps)
    return f"{y:04d}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}"


def released_at(zip_path: Path, marker: str, given: str | None) -> str:
    """When the release was cut, in his clock, because t_i is measured from it.

    The zip's member stamps are his machine's, so they are used when they fall on the
    marker's own date. When they do not, the date is all that is trustworthy and the
    time has to come off his mail.
    """
    if given:
        return given
    day = releases.release_date(marker)
    stamp = zip_stamp(zip_path)
    if stamp and stamp.startswith(day):
        return stamp
    print(f"  no usable stamp in the zip for {day}; pass --released-at from his mail")
    return f"{day} 00:00"


def recorded_sha(page: Path, marker: str) -> str | None:
    """The sha256 docs/registers/releases.md already carries for a marker, if it carries one."""
    if not page.is_file():
        return None
    _, rows, _ = releases.split_page(page.read_text(encoding="utf-8"))
    for row in rows:
        if row["marker"] == marker:
            value = row["sha256"]
            return None if value in (releases.PENDING, releases.NONE) else value
    return None


def ensure_row(page: Path, marker: str) -> bool:
    """Give a release its row, in date order, so `releases.py` has a cell to fill."""
    head, rows, tail = releases.split_page(page.read_text(encoding="utf-8"))
    if any(row["marker"] == marker for row in rows):
        return False
    rows.append(releases.blank_row(marker))
    rows.sort(key=lambda row: releases.marker_key(row["marker"]))
    table = releases.render_table(rows)
    page.write_text(f"{head}{releases.BEGIN}\n{table}\n{releases.END}{tail}", encoding="utf-8")
    return True


def extracted_tree(feedback: Path, marker: str) -> Path | None:
    """The shallowest extraction of this release already under the feedback root."""
    trees = releases.find_trees(feedback, {}).get(marker)
    return trees[0] if trees else None


def year_counts(tree: Path) -> dict[int, int]:
    counts = releases.year_counts(tree)
    missing = [y for y in YEARS if y not in counts]
    if missing:
        raise SystemExit(f"{tree}: no {', '.join(f'{y}.txt' for y in missing)}")
    return counts


def measure_year(calculator: Path, year_file: Path) -> Decimal:
    """His own calculator over one year file, so our figure is the one he computes."""
    with tempfile.TemporaryDirectory() as work:
        subprocess.run(
            [sys.executable, str(calculator), str(year_file), "--output-dir", work],
            check=True,
            capture_output=True,
        )
        summary = json.loads((Path(work) / "summary.json").read_text(encoding="utf-8"))
    return Decimal(summary["equivalent_english_domains"]).quantize(FOUR_PLACES)


def kept_ee(
    current: dict, marker: str, counts: dict[int, int], prefix: str = "reviewer"
) -> dict[str, str] | None:
    """The stored per-year EE, when it belongs to exactly these files. `prefix` picks the
    core keys or the `reviewer_extended` ones, so each block skips its own measuring."""
    if current.get("marker") != marker:
        return None
    if current.get(f"{prefix}_pairs") != sum(counts.values()):
        return None
    stored = current.get(f"{prefix}_ee_by_year", {})
    if sorted(stored) != sorted(str(y) for y in counts):
        return None
    return stored


def _total(ee: dict) -> str:
    return f"{sum((Decimal(v) for v in ee.values()), Decimal(0)):.4f}"


def update_baseline(
    path: Path,
    marker: str,
    tree: Path,
    stamp: str,
    pairs: int,
    ee: dict,
    ext_pairs: int = 0,
    ext_ee: dict | None = None,
) -> bool:
    """Point `data/baseline.json` at the new release, leaving the round fields alone. The
    extended keys are always written, zero when the release has no 2002 to 2015 file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    before = json.dumps(data, indent=2, ensure_ascii=False)
    ext_ee = ext_ee or {}
    data["current"].update(
        {
            "marker": marker,
            "directory": tree.as_posix(),
            "released_at": stamp,
            "reviewer_pairs": pairs,
            "reviewer_ee": _total(ee),
            "reviewer_ee_by_year": ee,
            "reviewer_extended_pairs": ext_pairs,
            "reviewer_extended_ee": _total(ext_ee),
            "reviewer_extended_ee_by_year": ext_ee,
        }
    )
    after = json.dumps(data, indent=2, ensure_ascii=False)
    if after == before:
        return False
    path.write_text(after + "\n", encoding="utf-8")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("zip", type=Path, help="the reviewer's release zip")
    ap.add_argument("--mail", type=Path, help="his verdict mail, for the round row")
    ap.add_argument("--round", help="round label, required with --mail")
    ap.add_argument("--received", help="'YYYY-MM-DD HH:MM' in his clock, required with --mail")
    ap.add_argument("--released", help="the benchmark stamp the round is scored from")
    ap.add_argument("--released-at", help="when this release was cut, in his clock")
    ap.add_argument("--marker", help="which release the zip holds, when it holds more than one")
    ap.add_argument("--sha256", help="the checksum the zip must have")
    ap.add_argument("--feedback", type=Path, default=releases.FEEDBACK)
    ap.add_argument("--into", type=Path, help="where to extract, default the feedback root")
    ap.add_argument("--archive", type=Path, default=releases.ARCHIVE)
    ap.add_argument("--legacy", type=Path, default=releases.TREE_ALIASES["merged260715-2"])
    ap.add_argument("--baseline-json", type=Path, default=BASELINE_JSON)
    ap.add_argument("--page", type=Path, default=releases.PAGE)
    ap.add_argument("--rounds-page", type=Path, default=rounds.PAGE)
    ap.add_argument("--calculator", type=Path, help="his equivalent_english_domains.py")
    ap.add_argument("--recompute", action="store_true", help="rerun the calculator regardless")
    ap.add_argument("--dry-run", action="store_true", help="say what it would do, write nothing")
    args = ap.parse_args()

    if args.mail and not (args.round and args.received):
        raise SystemExit("--mail needs --round and --received")
    if not args.zip.is_file():
        raise SystemExit(f"no zip at {args.zip}")

    started = time.monotonic()
    dry = args.dry_run
    changed: list[str] = []

    with step("checksum"):
        digest = releases.sha256(args.zip)
        marker = marker_of(args.zip, args.marker)
        print(f"  {marker}, sha256 {digest}")
        if args.sha256 and args.sha256 != digest:
            raise SystemExit(f"{args.zip}: sha256 is {digest}, not the {args.sha256} given")
        known = recorded_sha(args.page, marker)
        if known and known != digest:
            raise SystemExit(
                f"{marker} is already recorded in {args.page} under sha256 {known}."
                " Two different zips carry one marker: settle which is the release first."
            )
        if known:
            print(f"  already recorded in {args.page}")

    with step("extract"):
        tree = extracted_tree(args.feedback, marker)
        target = (args.into or args.feedback) / args.zip.stem
        if tree is not None:
            print(f"  already extracted at {tree}")
        elif dry:
            print(f"  would extract {args.zip} into {target}")
        else:
            with zipfile.ZipFile(args.zip) as zf:
                zf.extractall(target)
            tree = extracted_tree(args.feedback, marker)
            if tree is None:
                raise SystemExit(f"{target}: no {marker}/ tree after extracting")
            print(f"  extracted to {tree}")
            changed.append(str(target))

    with step("artifact"):
        # His zip is the artifact of record and `releases.py` hashes it where it lies,
        # so a zip handed to us from elsewhere is kept beside the tree it produced.
        under_feedback = args.feedback.resolve() in args.zip.resolve().parents
        beside = args.feedback / args.zip.name
        if under_feedback:
            print(f"  {args.zip} is already under {args.feedback}/")
        elif beside.is_file():
            print(f"  already copied to {beside}")
        elif dry:
            print(f"  would copy {args.zip} to {beside}")
        else:
            beside.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(args.zip, beside)
            print(f"  copied to {beside}")
            changed.append(str(beside))

    counts: dict[int, int] = {}
    ext_counts: dict[int, int] = {}
    with step("line counts"):
        if tree is None:
            print("  nothing extracted yet")
        else:
            counts = year_counts(tree)
            ext_counts = {
                y: releases.count_lines(tree / f"{y}.txt")
                for y in EXTENDED_YEARS
                if (tree / f"{y}.txt").is_file()
            }
            for year, n in (counts | ext_counts).items():
                print(f"  {year} {n:,}")
            print(f"  {sum(counts.values()):,} pairs, {sum(ext_counts.values()):,} extended")

    ee: dict[str, str] = {}
    ext_ee: dict[str, str] = {}
    with step("equivalent English"):
        data = json.loads(args.baseline_json.read_text(encoding="utf-8"))
        calculator = args.calculator or calculator_path()
        for block, years, prefix in (
            (ee, counts, "reviewer"),
            (ext_ee, ext_counts, "reviewer_extended"),
        ):
            stored = None if args.recompute else kept_ee(data["current"], marker, years, prefix)
            if stored is not None:
                block.update(stored)
                print(f"  {prefix}: unchanged, kept from {args.baseline_json}")
            elif not years:
                print(f"  {prefix}: nothing to measure")
            elif dry:
                print(f"  would run {calculator} over {len(years)} year files")
            elif not Path(calculator).is_file():
                raise SystemExit(f"calculator not found at {calculator}")
            else:
                for year in years:
                    block[str(year)] = f"{measure_year(Path(calculator), tree / f'{year}.txt'):.4f}"
                    print(f"  {year} {block[str(year)]}", flush=True)

    with step(str(args.baseline_json)):
        stamp = released_at(args.zip, marker, args.released_at)
        if dry:
            print(f"  would name {marker}, released {stamp}")
        elif not ee or tree is None:
            print("  nothing measured, left alone")
        elif update_baseline(
            args.baseline_json,
            marker,
            tree,
            stamp,
            sum(counts.values()),
            ee,
            sum(ext_counts.values()),
            ext_ee,
        ):
            print(f"  now names {marker}, released {stamp}")
            changed.append(str(args.baseline_json))
        else:
            print("  unchanged")

    with step(str(args.page)):
        if dry:
            print(f"  would add a row for {marker} and fill it from disk")
        else:
            if ensure_row(args.page, marker):
                print(f"  added a row for {marker}")
            before = args.page.read_text(encoding="utf-8")
            run_module(
                releases,
                [
                    "releases.py",
                    "--page",
                    str(args.page),
                    "--feedback",
                    str(args.feedback),
                    "--archive",
                    str(args.archive),
                    "--legacy",
                    str(args.legacy),
                ],
            )
            if args.page.read_text(encoding="utf-8") != before:
                changed.append(str(args.page))

    if args.mail:
        with step(str(args.rounds_page)):
            if dry:
                print(f"  would read {args.mail} into round {args.round}")
            else:
                before = args.rounds_page.read_text(encoding="utf-8")
                argv = [
                    "rounds.py",
                    "--mail",
                    str(args.mail),
                    "--round",
                    args.round,
                    "--received",
                    args.received,
                    "--page",
                    str(args.rounds_page),
                    "--feedback",
                    str(args.feedback),
                ]
                if args.released:
                    argv += ["--released", args.released]
                run_module(rounds, argv)
                if args.rounds_page.read_text(encoding="utf-8") != before:
                    changed.append(str(args.rounds_page))

    print(f"total: {time.monotonic() - started:.2f}s")
    if dry:
        print("dry run: nothing written")
    elif changed:
        print("changed: " + ", ".join(changed))
    else:
        print("no change: this release was already taken in")


if __name__ == "__main__":
    main()
