"""Stage the pricing snapshot the fleet prices against, and write its manifest.

`sync_fleet.sh` pushes what this stages. The staging directory is built with hard links,
so pointing at a 1.5 GB baseline and a 300 MB candidate export costs no disk and no copy
time, and the bytes the manifest hashes are the bytes that get pushed.

What lands, and why each piece is there:

    <marker>/{1996..2001}.txt   the reviewer's current baseline, required, from data/baseline.json
    netnew/{year}{,_hostnames,-ISC}.txt   our last export, optional per family
    candidates/candidate_pool.txt         his candidate pool
    candidates/<the rest he holds>        his ISC collection and unparsed names, outside the
                                          pool (`export.his_held_candidate_files`)
    candidates/candidate_unverified.txt   ours
    candidates/isc_candidates.txt         the ISC collection names, the class he refused
                                          for the annual files and which still scores as
                                          candidates
    candidates/{candidate_additions,header_candidates}.txt   ours, in the claim
    netnew/attested_registrables.txt      what the store dates beyond his files, required
    calculator/                           his scorer and its table, required
    manifest.json                         {marker, built_at, claim_sha256, files}

**A zero-line file refuses the build**, because an empty held-set prices every name as
net-new, which is the most flattering way this can go wrong, and so does an ABSENT
`{year}.txt` or `{year}_hostnames.txt`: a held-set the pricer never loads reads the same
way. The exception is an export family that may legitimately be empty or absent for one
year, which is `-ISC` (`1998-ISC.txt` is zero lines today because the survey dates nothing
in 1998) and the candidate exports. Nothing is silently dropped: every absent and every
empty entry is printed.

    uv run python scripts/harness/snapshot_manifest.py --out output/fleet_snapshot
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from ark.baseline import calculator_path  # noqa: E402
from ark.export import ATTESTED_NAME, claim_files, his_held_candidate_files  # noqa: E402
from ark.ingest import YEARS  # noqa: E402
from ark.price_snapshot import (  # noqa: E402
    ATTESTED,
    CALCULATOR_DIR,
    CALCULATOR_FILES,
    CANDIDATES_DIR,
    MANIFEST_NAME,
    NETNEW_DIR,
    SnapshotError,
    build_manifest,
)

BASELINE_JSON = REPO / "data/baseline.json"
EXPORT_NETNEW = REPO / "output/netnew"
EXPORT_CANDIDATES = REPO / "output/candidate_unverified.txt"
# calculator_path() is relative to the working directory; anchored like every path here.
CALCULATOR = REPO / calculator_path()
# The fleet's record of the claim the pushed snapshot carries, which every leg checks.
EXPECTED = "snapshot.json"
# **Both of these must exist for every year, or the build is refused.** They are the two
# units we ship, registrables and the hostnames beneath them (the second accepted
# 2026-09-01), so a missing one means `output/netnew` is stale or half-written, and every
# name we have already delivered for that year would price as net-new. An EMPTY one is
# different and allowed: a year can legitimately have no net-new names, and that says so.
NETNEW_REQUIRED = ("{year}.txt", "{year}_hostnames.txt")
# `-ISC` ships outside the claim and is empty for four of the six years, so it may be
# absent as well as empty. A name in it has still been delivered, so it is priced as held.
NETNEW_OPTIONAL = ("{year}-ISC.txt",)


def sources(baseline: Path, marker: str) -> tuple[dict[str, Path], set[str], list[str]]:
    """(relative path -> local file), which of them may be empty, and which are absent.

    Absence is returned rather than swallowed. A file that is not there cannot be hashed,
    so it would leave the snapshot without a line in the manifest, and a held-set the
    pricer never loads reads exactly like a held-set with nothing in it: every name in it
    prices as net-new. The caller refuses the required ones and prints the rest.
    """
    files: dict[str, Path] = {}
    optional: set[str] = set()
    absent: list[str] = []
    for year in YEARS:
        files[f"{marker}/{year}.txt"] = baseline / f"{year}.txt"
        for family in NETNEW_REQUIRED + NETNEW_OPTIONAL:
            name = family.format(year=year)
            rel = f"{NETNEW_DIR}/{name}"
            path = EXPORT_NETNEW / name
            if not path.is_file():
                absent.append(rel)
                continue
            files[rel] = path
            optional.add(rel)
    pool = baseline / "candidate_pool.txt"
    # what he holds outside the pool, so a name he keeps there never prices as net-new
    outside = [path for path in his_held_candidate_files(baseline) if path != pool]
    for rel, path in (
        (f"{CANDIDATES_DIR}/candidate_pool.txt", pool),
        *((f"{CANDIDATES_DIR}/{path.relative_to(baseline)}", path) for path in outside),
        (f"{CANDIDATES_DIR}/candidate_unverified.txt", EXPORT_CANDIDATES),
        (f"{CANDIDATES_DIR}/isc_candidates.txt", EXPORT_NETNEW / "isc_candidates.txt"),
        (f"{CANDIDATES_DIR}/candidate_additions.txt", EXPORT_NETNEW / "candidate_additions.txt"),
        (f"{CANDIDATES_DIR}/header_candidates.txt", EXPORT_NETNEW / "header_candidates.txt"),
    ):
        if not path.is_file():
            absent.append(rel)
            continue
        files[rel] = path
        optional.add(rel)
    for rel, path in (
        (ATTESTED, EXPORT_NETNEW / ATTESTED_NAME),
        *((f"{CALCULATOR_DIR}/{name}", CALCULATOR.parent / name) for name in CALCULATOR_FILES),
    ):
        if path.is_file():
            files[rel] = path
        else:
            absent.append(rel)
    return files, optional, absent


def must_be_present(absent: list[str]) -> list[str]:
    """The absent entries that are not allowed to be absent, in their manifest names."""
    required = {
        f"{NETNEW_DIR}/{family.format(year=year)}" for year in YEARS for family in NETNEW_REQUIRED
    }
    required |= {ATTESTED, *(f"{CALCULATOR_DIR}/{name}" for name in CALCULATOR_FILES)}
    return [rel for rel in absent if rel in required]


def claim_of(files: dict[str, Path]) -> set[str]:
    """The staged entries that are claim files, as the export names them."""
    claim = set(claim_files(EXPORT_NETNEW, EXPORT_CANDIDATES))
    return {rel for rel, path in files.items() if path in claim}


def publish_expected(stage: Path, fleet: Path) -> int:
    """Write the fleet's `snapshot.json` from the staged manifest, building nothing, so it
    names the claim `sync_fleet.sh` pushed."""
    manifest = json.loads((stage / MANIFEST_NAME).read_text(encoding="utf-8"))
    claim = manifest.get("claim_sha256")
    if not claim or not fleet.is_dir():
        why = f"{fleet} is not a directory" if claim else "the staged manifest has no claim_sha256"
        print(f"snapshot_manifest: nothing published, {why}", file=sys.stderr)
        return 1
    expected = {"marker": manifest["marker"], "claim_sha256": claim}
    (fleet / EXPECTED).write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    print(f"snapshot_manifest: {EXPECTED} expects {manifest['marker']} claim_sha256 {claim}")
    return 0


def stage(out: Path, files: dict[str, Path], manifest: dict) -> None:
    """Hard-link every manifest file into `out` and write the manifest last.

    The manifest is written last on purpose: a run interrupted halfway leaves a manifest
    that describes files which are not there yet, and the pricer refuses that rather than
    measuring against a torn snapshot.
    """
    if out.exists():
        shutil.rmtree(out)
    for rel in manifest["files"]:
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(files[rel], target)
        except OSError:
            # A different filesystem, or a link limit. Copying is slower and correct.
            shutil.copy2(files[rel], target)
    (out / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="staging directory to build")
    parser.add_argument(
        "--publish-expected",
        type=Path,
        metavar="FLEET",
        help="write FLEET/snapshot.json from the manifest already at --out, and build nothing",
    )
    args = parser.parse_args()
    if args.publish_expected:
        return publish_expected(args.out, args.publish_expected.expanduser())

    current = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))["current"]
    marker, baseline = current["marker"], REPO / current["directory"]
    files, optional, absent = sources(baseline, marker)
    for rel in absent:
        print(f"snapshot_manifest: {rel} is absent")
    missing = must_be_present(absent)
    if missing:
        print(
            "snapshot_manifest: refusing to build, because "
            + ", ".join(missing)
            + " would price as net-new every name we have already shipped, or leave the EE "
            "without his calculator. Run `uv run ark export`, or restore his package.",
            file=sys.stderr,
        )
        return 1
    try:
        manifest, skipped = build_manifest(marker, files, optional, claim_of(files))
    except SnapshotError as exc:
        print(f"snapshot_manifest: {exc}", file=sys.stderr)
        return 1
    stage(args.out, files, manifest)
    for rel in skipped:
        print(f"snapshot_manifest: {rel} is empty, left out of the snapshot")
    print(
        f"snapshot_manifest: {len(manifest['files'])} files, marker {marker}, "
        f"built_at {manifest['built_at']}"
    )
    print(f"snapshot_manifest: claim_sha256 {manifest['claim_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
