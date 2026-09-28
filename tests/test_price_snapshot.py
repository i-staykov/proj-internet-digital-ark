"""The snapshot pricer: what counts as net-new, and every snapshot it refuses to price against."""

import json
import shutil
import subprocess
import sys
from decimal import Decimal
from functools import partial
from pathlib import Path

import pytest

from ark import price_snapshot as ps
from ark.baseline import calculator_path
from ark.english_share import SHARE_PATH

MARKER = "merged260908"
COM = 0.6321
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts/harness"))
import snapshot_manifest as sm  # noqa: E402

# His calculator's interface, for a fresh clone that lacks his; the parity test runs his.
STAND_IN = """import json, sys; from decimal import Decimal; from pathlib import Path
from ark.english_share import english_weights
weights = english_weights(Path(__file__).with_name("q2_tld_top_langs.json"))
names = {line.strip() for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()}
out = Path(sys.argv[sys.argv.index("--output-dir") + 1]); out.mkdir(parents=True, exist_ok=True)
ee = sum((weights.get(n.rsplit(".", 1)[-1], Decimal(0)) for n in names), Decimal(0))
summary = {"unique_valid_domains": len(names), "equivalent_english_domains": format(ee, "f")}
(out / "summary.json").write_text(json.dumps(summary))
"""


def _write(path: Path, names: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{name}\n" for name in names), encoding="utf-8")
    return path


def _snapshot(root: Path, held=None, netnew=None, candidates=None, calculator=None) -> Path:
    """A snapshot as `sync_fleet.sh` pushes it, with his calculator from `calculator` or ours."""
    snapshot = root / "ark-data"
    files = {f"calculator/{name}": snapshot / "calculator" / name for name in ps.CALCULATOR_FILES}
    (snapshot / "calculator").mkdir(parents=True)
    for path in files.values():
        shutil.copy(calculator / path.name if calculator else SHARE_PATH, path)
    if not calculator:
        files["calculator/equivalent_english_domains.py"].write_text(STAND_IN)
    for year in range(1996, 2002):
        rel = f"{MARKER}/{year}.txt"
        files[rel] = _write(snapshot / rel, (held or {}).get(year) or [f"filler{year}.example"])
    for family, lists in (("netnew", netnew), ("candidates", candidates)):
        for name, names in (lists or {}).items():
            files[f"{family}/{name}"] = _write(snapshot / family / name, names)
    manifest, skipped = ps.build_manifest(MARKER, files)
    assert not skipped
    (snapshot / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return snapshot


def _items(tmp_path: Path, *rows) -> Path:
    """Items as `host:year` tokens, `host` alone for an undated one, or whole records."""
    path, records = tmp_path / "items.jsonl", []
    for row in rows:
        host, _, year = row.partition(":") if isinstance(row, str) else ("", "", "")
        records.append({"host": host, **({"year": int(year)} if year else {})} if host else row)
    path.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    return path


def _check(priced: dict, **want) -> None:
    flat = {**priced, **priced["counts"]}
    assert {key: flat[key] for key in want} == want


def test_the_three_item_fixture(tmp_path: Path) -> None:
    """One held, one net-new, one `www.` alias: the whole contract in three lines."""
    snapshot = _snapshot(tmp_path, held={1998: ["held.com"]})
    items = _items(tmp_path, "held.com:1998", "fresh.com:1998", "www.other.com:1998")
    priced, ee = ps.price(snapshot, items), f"{2 * COM:.4f}"
    manifest, sha = ps.read_manifest(snapshot)
    _check(priced, track="annual", split=ps.SPLIT_AUTO, netnew_pairs=2, ee=ee, items=3)
    _check(priced, by_year={"1998": {"pairs": 2, "ee": ee}}, already_held=1, www_of_parent=1)
    assert priced["by_tld"] == [{"tld": "com", "pairs": 2, "ee": ee}]
    _check(priced, www_alias_share=0.5, hostname_records=1, parent_held_share=0.0)
    _check(priced, snapshot_marker=MARKER, manifest_sha=sha, snapshot_built_at=manifest["built_at"])
    with pytest.raises(ps.SnapshotError, match="track must be"):
        ps.price(snapshot, items, track="pool")


def test_held_is_the_exact_name_in_its_year_and_neither_form_holds_the_other(tmp_path) -> None:
    """Our export is held too, and a held child, parent or `www.` form holds no other form."""
    held = {1999: ["his.com"], 2000: ["mail.parent.com", "lone.com"]}
    held[2001] = ["bare.com", "www.other.com"]
    ours = {"1999.txt": ["ours.com"], "1999_hostnames.txt": ["a.ours.com"]}
    items = [f"{h}:1999" for h in ("his.com", "ours.com", "a.ours.com", "b.ours.com")]
    items += [f"{h}:2000" for h in ("parent.com", "mail.parent.com", "sub.lone.com")]
    items += ["www.bare.com:2001", "other.com:2001"]
    priced = ps.price(_snapshot(tmp_path, held=held, netnew=ours), _items(tmp_path, *items))
    pairs = {year: row["pairs"] for year, row in priced["by_year"].items()}
    assert pairs == {"1999": 1, "2000": 2, "2001": 2}
    _check(priced, already_held=4, hostname_records=3, parent_held_share=1.0, www_alias_share=0.2)


def test_a_year_is_a_year_and_an_error_capture_prices_on_the_candidate_track_only(tmp_path) -> None:
    """Out of window prices nowhere; an undated name or a 4xx or 5xx capture is a candidate."""
    snapshot = _snapshot(tmp_path, held={1997: ["moved.com"]})
    rows = ["moved.com:1997", "moved.com:1998", "old.com:1995", "plain.com"]
    rows += [{"host": "dated.com", "year": "1994-12-01"}]
    caps = (("ok.com/", "200"), ("gone.com/x", 404), ("down.org/", "503"))
    rows += [{"url": f"http://{u}", "timestamp": "19990101000000", "status": c} for u, c in caps]
    rows += [{"host": "up.com", "year": 1999, "status": "active"}]
    items = _items(tmp_path, *rows, {"host": "lost.com", "year": 1999, "status": 404})
    priced = ps.price(snapshot, items)
    _check(priced, netnew_pairs=3, out_of_window=1, undated=1, error_status=3)
    one, two = {"pairs": 1, "ee": f"{COM:.4f}"}, {"pairs": 2, "ee": f"{2 * COM:.4f}"}
    assert priced["by_year"] == {"1998": one, "1999": two}
    candidate = ps.price(snapshot, items, track="candidate")
    _check(candidate, netnew_pairs=6, out_of_window=1, already_held=1)  # moved.com, held in 1997


def test_text_is_read_junk_is_dropped_and_a_pair_that_could_never_ship_is_not_priced(tmp_path):
    """`text` is read beside `host`, and a `.arpa` name or one older than its TLD never prices."""
    rows = [{"item": "msg-1", "year": 2001, "text": "http://one.com/a two.org 10.0.0.1"}]
    rows += [{"item": "msg-2", "year": 2001, "text": "not_a_host bare.invalidtld"}]
    rows += [{"item": "msg-3", "year": 2001}, "gone.arpa:1998", "early.info:1998", "fine.com:1998"]
    priced = ps.price(_snapshot(tmp_path), _items(tmp_path, *rows), split="none")
    _check(priced, netnew_pairs=3, not_shippable=2, ee=f"{2 * COM + 0.7101:.4f}")
    # the suffix list does not know one; the IP, the underscore name and the empty item have no host
    _check(priced, rejected_host=1, no_host=3)


def test_the_ee_is_his_calculators(tmp_path: Path) -> None:
    """The EE a leg quotes is what his calculator prints for the same net-new names."""
    his = ROOT / calculator_path()
    if not his.is_file():
        pytest.skip(f"his calculator is not on disk at {his}")
    snapshot = _snapshot(tmp_path, held={1998: ["held.com"]}, calculator=his.parent)
    names = ["a.com", "b.org", "c.co.uk", "d.de", "e.com", "www.e.com"]
    priced = ps.price(snapshot, _items(tmp_path, "held.com:1998", *(f"{n}:1998" for n in names)))
    out = [str(_write(tmp_path / "1998.txt", names)), "--output-dir", str(tmp_path / "his")]
    subprocess.run([sys.executable, "-B", str(his), *out], check=True, capture_output=True)
    summary = json.loads((tmp_path / "his" / "summary.json").read_text())
    assert priced["netnew_pairs"] == summary["unique_valid_domains"] == 6
    assert Decimal(priced["ee"]) == Decimal(summary["equivalent_english_domains"])


def test_the_candidate_track_and_how_much_of_it_is_hostname_grain(tmp_path: Path) -> None:
    """A candidate prices against both pools and every annual file, and names its hostname EE."""
    pools = {"candidate_pool.txt": ["his.com"], "isc_candidates.txt": ["isc.com"]}
    pools["candidate_additions.txt"] = ["ours.com"]
    snapshot = _snapshot(tmp_path, held={1996: ["annual.com"]}, candidates=pools)
    rows = ["his.com", "isc.com", "ours.com", "annual.com", "brand.new.com:1998", "plain.com"]
    priced = ps.price(snapshot, _items(tmp_path, *rows, "deep.inside.com"), track="candidate")
    _check(priced, track="candidate", netnew_pairs=3, ee=f"{3 * COM:.4f}", hostname_records=2)
    _check(priced, ee_hostname=f"{2 * COM:.4f}", already_in_candidate_pool=3, already_held=1)
    assert priced["by_year"] == {}, "a candidate claims no year, even when an item had one"
    registrable = ps.price(snapshot, _items(tmp_path, "one.com", "two.com"), track="candidate")
    assert registrable["ee_hostname"] == "0.0000"


def test_a_zero_line_file_refuses_the_build_unless_it_may_be_left_out(tmp_path: Path) -> None:
    """An empty held-set prices every name as net-new."""
    empty, full = _write(tmp_path / "1996.txt", []), _write(tmp_path / "1997.txt", ["one.com"])
    with pytest.raises(ps.SnapshotError, match="no lines"):
        ps.build_manifest(MARKER, {f"{MARKER}/1996.txt": empty, f"{MARKER}/1997.txt": full})
    files = {"netnew/1996-ISC.txt": empty, f"{MARKER}/1997.txt": full}
    manifest, skipped = ps.build_manifest(MARKER, files, optional={"netnew/1996-ISC.txt"})
    assert skipped == ["netnew/1996-ISC.txt"] and list(manifest["files"]) == [f"{MARKER}/1997.txt"]
    (tmp_path / "x.txt").write_text("a.com\nb.com")
    assert ps.file_stats(tmp_path / "x.txt")[0] == 2, "a last line without a newline counts"


def _emptied(snapshot: Path) -> None:
    manifest, _ = ps.read_manifest(snapshot)
    (snapshot / MARKER / "1996.txt").write_text("")
    digest = ps.file_stats(snapshot / MARKER / "1996.txt")[1]
    manifest["files"][f"{MARKER}/1996.txt"] = {"lines": 0, "sha256": digest}
    (snapshot / "manifest.json").write_text(json.dumps(manifest))


@pytest.mark.parametrize(
    ("damage", "match"),
    [
        (_emptied, "no lines"),
        (lambda s: _write(s / MARKER / "1996.txt", ["one.com", "sneaked.com"]), "does not match"),
        (lambda s: (s / MARKER / "1999.txt").unlink(), "not in the snapshot"),
        (lambda s: _write(s / "netnew" / "1996.txt", ["unlisted.com"]), "not in the manifest"),
        (lambda s: (s / "manifest.json").write_text("{}"), "no 'marker'"),
        (lambda s: (s / "manifest.json").write_text('{"marker": 0, "built_at": 0}'), "no 'files'"),
        (lambda s: (s / "manifest.json").unlink(), "does not exist"),
    ],
    ids="zero-line changed-file missing-file unlisted-file no-marker no-files no-manifest".split(),
)
def test_a_snapshot_that_does_not_match_its_manifest_is_refused(tmp_path, damage, match) -> None:
    snapshot = _snapshot(tmp_path, held={1996: ["one.com"]})
    damage(snapshot)
    with pytest.raises(ps.SnapshotError, match=match):
        ps.price(snapshot, _items(tmp_path, "two.com:1996"))


def test_the_snapshot_stages_his_files_our_claim_and_his_calculator(tmp_path, monkeypatch) -> None:
    """What is hashed is what is pushed, and each unit we ship is there for all six years."""
    baseline, netnew = tmp_path / "baseline", tmp_path / "netnew"
    calculator = _write(tmp_path / "calculator" / "equivalent_english_domains.py", ["pass"])
    _write(calculator.with_name("q2_tld_top_langs.json"), ["{}"])
    for year in range(1996, 2002):
        _write(baseline / f"{year}.txt", ["his.com"])
        _write(netnew / f"{year}.txt", ["ours.com"])
        _write(netnew / f"{year}_hostnames.txt", ["a.ours.com"])
    _write(netnew / "attested_registrables.txt", ["1998\tours.com"])
    monkeypatch.setattr(sm, "EXPORT_NETNEW", netnew)
    monkeypatch.setattr(sm, "EXPORT_CANDIDATES", tmp_path / "unverified.txt")
    monkeypatch.setattr(sm, "CALCULATOR", calculator)
    # the six `-ISC` files and all five candidate exports are absent and allowed to be
    assert sm.must_be_present(absent := sm.sources(baseline, MARKER)[2]) == [] and len(absent) == 11
    # his ISC collection and unparsed names are candidates he holds, as the export diffs them
    his = ["candidate_pool.txt", "candidate_pool_unparsed_format.txt"]
    his += ["isc_survey_hostnames/1996-ISC.txt"]
    ours = ["candidate_additions.txt", "header_candidates.txt"]
    paths = [baseline / "isc_survey_hostnames/README.md", *(baseline / rel for rel in his)]
    for path in [*paths, *(netnew / name for name in ours)]:
        _write(path, ["cand.com"])
    _write(netnew / "1996-ISC.txt", [])
    files, optional, absent = sm.sources(baseline, MARKER)
    held = {rel for rel in files if rel.startswith("candidates/")}
    assert held <= optional and held == {f"candidates/{rel}" for rel in [*his, *ours]}
    claim = partial(ps.build_manifest, MARKER, files, optional, sm.claim_of(files))
    sm.stage(out := tmp_path / "stage", files, manifest := claim()[0])
    # an empty family reaches neither the manifest nor the stage
    landed = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()}
    assert landed == {"manifest.json", *manifest["files"]} and "netnew/1996-ISC.txt" not in landed
    shipped = {ps.ATTESTED, *(f"candidates/{n}" for n in ours)}
    assert shipped | {f"calculator/{n}" for n in ps.CALCULATOR_FILES} <= landed
    assert json.loads((out / "manifest.json").read_text()) == manifest
    assert (out / MARKER / "1996.txt").read_text() == "his.com\n"
    assert manifest["files"][ps.ATTESTED]["sorted"] is True
    assert sm.publish_expected(out, tmp_path) == 0, "the fleet is told the claim"
    want = {"marker": MARKER, "claim_sha256": manifest["claim_sha256"]}
    assert json.loads((tmp_path / "snapshot.json").read_text()) == want
    _write(baseline / "1996.txt", ["his.com", "more.com"])
    assert claim()[0]["claim_sha256"] == want["claim_sha256"], "his files are not the claim"
    _write(netnew / "candidate_additions.txt", ["cand.com", "more.com"])
    assert claim()[0]["claim_sha256"] != want["claim_sha256"], "ours are"
    (netnew / "1999_hostnames.txt").unlink()
    (netnew / "attested_registrables.txt").unlink()
    _files, _optional, absent = sm.sources(baseline, MARKER)
    assert sm.must_be_present(absent) == ["netnew/1999_hostnames.txt", ps.ATTESTED]
