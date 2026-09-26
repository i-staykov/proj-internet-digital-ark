"""The snapshot pricer: what counts as net-new, and what makes it refuse to answer.

A fleet leg has no store, so nothing downstream can notice that it priced against an empty
file, a half-pushed snapshot or a stale marker. Every refusal below is a case where measuring
anyway would have produced a flattering number and no way to catch it.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from ark.baseline import calculator_path
from ark.english_share import SHARE_PATH
from ark.price_snapshot import (
    SPLIT_AUTO,
    SnapshotError,
    build_manifest,
    file_stats,
    price,
    read_manifest,
    verify_snapshot,
)

MARKER = "merged260908"
COM = 0.6321
ROOT = Path(__file__).resolve().parent.parent
# His calculator's interface and summary keys over our reader of the table beside it, since
# his package is not in a fresh clone. `test_the_ee_is_his_calculators` runs his.
STAND_IN = """
import json, sys
from decimal import Decimal
from pathlib import Path
from ark.english_share import english_weights

weights = english_weights(Path(__file__).with_name("q2_tld_top_langs.json"))
names = {line.strip() for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()}
out = Path(sys.argv[sys.argv.index("--output-dir") + 1])
out.mkdir(parents=True, exist_ok=True)
total = sum((weights.get(n.rsplit(".", 1)[-1], Decimal(0)) for n in names), Decimal(0))
summary = {"unique_valid_domains": len(names), "equivalent_english_domains": format(total, "f")}
(out / "summary.json").write_text(json.dumps(summary))
"""


def _write(path: Path, names: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{name}\n" for name in names), encoding="utf-8")
    return path


def _snapshot(
    root: Path,
    held: dict[int, list[str]] | None = None,
    netnew: dict[str, list[str]] | None = None,
    candidates: dict[str, list[str]] | None = None,
    calculator: Path | None = None,
) -> Path:
    """A snapshot of the shape `sync_fleet.sh` pushes, manifest included, with the stand-in
    calculator unless `calculator` names the directory holding his."""
    snapshot = root / "ark-data"
    files: dict[str, Path] = {}
    (snapshot / "calculator").mkdir(parents=True)
    for name in ("equivalent_english_domains.py", "q2_tld_top_langs.json"):
        files[f"calculator/{name}"] = snapshot / "calculator" / name
        if calculator is not None:
            shutil.copy(calculator / name, files[f"calculator/{name}"])
    if calculator is None:
        files["calculator/equivalent_english_domains.py"].write_text(STAND_IN)
        shutil.copy(SHARE_PATH, files["calculator/q2_tld_top_langs.json"])
    for year in range(1996, 2002):
        rel = f"{MARKER}/{year}.txt"
        files[rel] = _write(snapshot / rel, (held or {}).get(year) or [f"filler{year}.example"])
    for name, names in (netnew or {}).items():
        files[f"netnew/{name}"] = _write(snapshot / "netnew" / name, names)
    for name, names in (candidates or {}).items():
        files[f"candidates/{name}"] = _write(snapshot / "candidates" / name, names)
    manifest, skipped = build_manifest(MARKER, files)
    assert not skipped
    (snapshot / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return snapshot


def _items(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def test_the_three_item_fixture(tmp_path: Path) -> None:
    """One held, one net-new, one `www.` alias: the whole contract in three lines."""
    snapshot = _snapshot(tmp_path, held={1998: ["held.com"]})
    items = _items(
        tmp_path / "items.jsonl",
        [
            {"host": "held.com", "year": 1998},
            {"host": "fresh.com", "year": 1998},
            {"host": "www.other.com", "year": 1998},
        ],
    )
    priced = price(snapshot, items)
    manifest, sha = read_manifest(snapshot)

    assert priced["track"] == "annual"
    # every result names its split; names from a field are never split away
    assert priced["split"] == SPLIT_AUTO
    assert priced["netnew_pairs"] == 2
    assert priced["ee"] == f"{2 * COM:.4f}"
    assert priced["by_year"] == {"1998": {"pairs": 2, "ee": f"{2 * COM:.4f}"}}
    assert priced["by_tld"] == [{"tld": "com", "pairs": 2, "ee": f"{2 * COM:.4f}"}]
    # `www.other.com` is its own record and is not folded onto its parent, and the share
    # says how much of the figure arrived in that form.
    assert priced["www_alias_share"] == 0.5
    assert priced["hostname_records"] == 1
    assert priced["parent_held_share"] == 0.0
    assert priced["snapshot_marker"] == MARKER
    assert priced["snapshot_built_at"] == manifest["built_at"]
    assert priced["manifest_sha"] == sha
    assert priced["counts"]["items"] == 3
    assert priced["counts"]["already_held"] == 1
    assert priced["counts"]["www_of_parent"] == 1


def test_our_own_export_is_held_too(tmp_path: Path) -> None:
    """A name in `netnew/` was delivered, so re-finding it is not net-new."""
    snapshot = _snapshot(
        tmp_path,
        held={1999: ["his.com"]},
        netnew={"1999.txt": ["ours.com"], "1999_hostnames.txt": ["a.ours.com"]},
    )
    items = _items(
        tmp_path / "items.jsonl",
        [
            {"host": "his.com", "year": 1999},
            {"host": "ours.com", "year": 1999},
            {"host": "a.ours.com", "year": 1999},
            {"host": "b.ours.com", "year": 1999},
        ],
    )
    priced = price(snapshot, items)
    assert priced["netnew_pairs"] == 1
    assert priced["counts"]["already_held"] == 3
    # the one net-new record is a hostname whose parent we already hold that year
    assert priced["parent_held_share"] == 1.0
    assert priced["hostname_records"] == 1


def test_neither_form_infers_the_other(tmp_path: Path) -> None:
    """A held child does not make its parent held, nor a held parent its child."""
    snapshot = _snapshot(tmp_path, held={2000: ["mail.parent.com", "lone.com"]})
    items = _items(
        tmp_path / "items.jsonl",
        [
            {"host": "parent.com", "year": 2000},
            {"host": "mail.parent.com", "year": 2000},
            {"host": "sub.lone.com", "year": 2000},
        ],
    )
    priced = price(snapshot, items)
    assert priced["netnew_pairs"] == 2
    assert priced["counts"]["already_held"] == 1
    # one of the two net-new records is a hostname, and its parent is held
    assert priced["hostname_records"] == 1
    assert priced["parent_held_share"] == 1.0


def test_a_www_form_and_its_parent_are_two_records(tmp_path: Path) -> None:
    """ADR-010, in his words: neither form automatically establishes the other. The store
    carries a check for each direction, so a pricer that folded a `www.` capture onto the
    parent would quote a figure the ingest is forbidden to bank.
    """
    snapshot = _snapshot(tmp_path, held={2001: ["bare.com", "www.other.com"]})
    items = _items(
        tmp_path / "items.jsonl",
        [
            {"host": "www.bare.com", "year": 2001},  # the bare name is held, this is not
            {"host": "other.com", "year": 2001},  # the www form is held, this is not
        ],
    )
    priced = price(snapshot, items)
    assert priced["netnew_pairs"] == 2
    assert priced["counts"]["already_held"] == 0
    assert priced["www_alias_share"] == 0.5
    # the `www.` record is a hostname whose parent we hold for that year; the bare one is
    # not a hostname at all, so the share is over the one record it can describe
    assert priced["hostname_records"] == 1
    assert priced["parent_held_share"] == 1.0


def test_a_year_is_a_year(tmp_path: Path) -> None:
    """Membership is per year, a year outside the window prices on neither track, and an
    undated record is a candidate."""
    snapshot = _snapshot(tmp_path, held={1997: ["moved.com"]})
    items = _items(
        tmp_path / "items.jsonl",
        [
            {"host": "moved.com", "year": 1997},
            {"host": "moved.com", "year": 1998},
            {"host": "old.com", "year": 1995},
            {"host": "dated.com", "year": "1994-12-01"},
            {"host": "plain.com"},
        ],
    )
    priced = price(snapshot, items)
    assert priced["netnew_pairs"] == 1
    assert priced["by_year"] == {"1998": {"pairs": 1, "ee": f"{COM:.4f}"}}
    assert priced["counts"]["out_of_window"] == 1
    assert priced["counts"]["undated"] == 1
    candidate = price(snapshot, items, track="candidate")
    assert candidate["netnew_pairs"] == 1  # plain.com: moved.com is held in 1997
    assert candidate["counts"]["out_of_window"] == 1
    assert candidate["counts"]["already_held"] == 1


def test_an_error_capture_prices_on_the_candidate_track_only(tmp_path: Path) -> None:
    """A 4xx or 5xx capture shows no web presence in its year, only that the name existed."""
    snapshot = _snapshot(tmp_path)
    items = _items(
        tmp_path / "items.jsonl",
        [
            {"url": "http://ok.com/", "timestamp": "19990101000000", "status": "200"},
            {"url": "http://gone.com/x", "timestamp": "19990102000000", "status": 404},
            {"url": "http://down.org/", "timestamp": "19990103000000", "status": "503"},
            {"host": "up.com", "year": 1999, "status": "active"},
            {"host": "lost.com", "year": 1999, "status": 404},
        ],
    )
    priced = price(snapshot, items)
    assert priced["netnew_pairs"] == 2
    assert list(priced["by_year"]) == ["1999"]
    assert priced["counts"]["error_status"] == 3
    assert price(snapshot, items, track="candidate")["netnew_pairs"] == 5


def test_text_is_read_and_junk_is_dropped(tmp_path: Path) -> None:
    """`text` is accepted beside `host`, the same shape `price_hostnames.py` reads."""
    snapshot = _snapshot(tmp_path)
    items = _items(
        tmp_path / "items.jsonl",
        [
            {"item": "msg-1", "year": 2001, "text": "http://one.com/a two.org 10.0.0.1"},
            {"item": "msg-2", "year": 2001, "text": "not_a_host bare.invalidtld"},
            {"item": "msg-3", "year": 2001},
        ],
    )
    priced = price(snapshot, items, split="none")
    assert priced["netnew_pairs"] == 2
    assert priced["counts"]["rejected_host"] == 1  # the suffix list does not know it
    # the IP address, the underscore name, and the item carrying no host at all
    assert priced["counts"]["no_host"] == 3
    assert priced["ee"] == f"{COM + 0.7101:.4f}"


def test_the_ee_is_his_calculators(tmp_path: Path) -> None:
    """The EE a leg quotes is what his calculator prints for the same net-new names."""
    his = ROOT / calculator_path()
    if not his.is_file():
        pytest.skip(f"his calculator is not on disk at {his}")
    snapshot = _snapshot(tmp_path, held={1998: ["held.com"]}, calculator=his.parent)
    netnew = {
        "1998": ["a.com", "b.org", "c.co.uk"],
        "1999": ["d.de", "e.com", "www.e.com"],
    }
    rows = [{"host": "held.com", "year": 1998}]
    rows += [{"host": name, "year": int(year)} for year, names in netnew.items() for name in names]
    priced = price(snapshot, _items(tmp_path / "items.jsonl", rows))
    total = Decimal(0)
    for year, names in netnew.items():
        listing = _write(tmp_path / f"{year}.txt", names)
        results = tmp_path / f"his_{year}"
        subprocess.run(
            [sys.executable, "-B", str(his), str(listing), "--output-dir", str(results)],
            check=True,
            capture_output=True,
        )
        summary = json.loads((results / "summary.json").read_text())
        assert priced["by_year"][year]["pairs"] == summary["unique_valid_domains"] == 3
        assert Decimal(priced["by_year"][year]["ee"]) == Decimal(
            summary["equivalent_english_domains"]
        )
        total += Decimal(summary["equivalent_english_domains"])
    assert Decimal(priced["ee"]) == total


def test_a_pair_that_could_never_ship_is_not_priced(tmp_path: Path) -> None:
    """The export's own filter, so a corpus is not credited for names no file can carry."""
    snapshot = _snapshot(tmp_path)
    items = _items(
        tmp_path / "items.jsonl",
        [
            {"host": "gone.arpa", "year": 1998},
            {"host": "early.info", "year": 1998},  # .info was delegated in 2001
            {"host": "fine.com", "year": 1998},
        ],
    )
    priced = price(snapshot, items)
    assert priced["netnew_pairs"] == 1
    assert priced["counts"]["not_shippable"] == 2


def test_the_candidate_track(tmp_path: Path) -> None:
    """Undated names, priced against both candidate pools and every annual file."""
    snapshot = _snapshot(
        tmp_path,
        held={1996: ["annual.com"]},
        candidates={
            "candidate_pool.txt": ["his.com"],
            "isc_candidates.txt": ["isc.com"],
            "candidate_additions.txt": ["ours.com"],
        },
    )
    items = _items(
        tmp_path / "items.jsonl",
        [
            {"host": "his.com"},
            {"host": "isc.com"},
            {"host": "ours.com"},
            {"host": "annual.com"},
            {"host": "brand.new.com", "year": 1998},
        ],
    )
    priced = price(snapshot, items, track="candidate")
    assert priced["track"] == "candidate"
    assert priced["netnew_pairs"] == 1
    assert priced["ee"] == f"{COM:.4f}"
    # A candidate claims no year, so nothing is bucketed by one even when an item had one.
    assert priced["by_year"] == {}
    assert priced["counts"]["already_in_candidate_pool"] == 3
    assert priced["counts"]["already_held"] == 1


def test_the_candidate_figure_says_how_much_of_it_is_hostname_grain(tmp_path: Path) -> None:
    """The half that does not ship must be visible in the figure that quotes it.

    `export.py` fills the candidate pool with registrable domains plus the ISC survey
    hostnames and nothing else, while the filter here admits any name not already held. So
    a hostname-grain source prices high and exports nothing, and a leg quoting the headline
    alone reports EE the claim will never contain. `ddn-hosts-txt` was confirmed at
    6,401.3 EE on 2026-09-19 that way and ships zero.
    """
    snapshot = _snapshot(tmp_path, held={1996: ["annual.com"]})
    items = _items(
        tmp_path / "items.jsonl",
        [{"host": "plain.com"}, {"host": "deep.inside.com"}],
    )
    priced = price(snapshot, items, track="candidate")
    assert priced["netnew_pairs"] == 2
    assert priced["ee"] == f"{COM * 2:.4f}"
    # Exactly one of the two is a hostname, so exactly half the figure is unshippable.
    assert priced["ee_hostname"] == f"{COM:.4f}"
    assert priced["hostname_records"] == 1


def test_a_registrable_only_figure_reports_no_stranded_half(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, held={1996: ["annual.com"]})
    items = _items(tmp_path / "items.jsonl", [{"host": "one.com"}, {"host": "two.com"}])
    priced = price(snapshot, items, track="candidate")
    assert priced["ee_hostname"] == "0.0000"


def test_a_zero_line_file_refuses_the_build(tmp_path: Path) -> None:
    """An empty held-set prices every name as net-new, so it is fatal at build time."""
    empty = _write(tmp_path / "1996.txt", [])
    full = _write(tmp_path / "1997.txt", ["one.com"])
    with pytest.raises(SnapshotError, match="no lines"):
        build_manifest(MARKER, {f"{MARKER}/1996.txt": empty, f"{MARKER}/1997.txt": full})
    # unless the entry is one an export may legitimately leave empty, and then it is
    # left out of the snapshot rather than pushed as a zero-line file
    manifest, skipped = build_manifest(
        MARKER,
        {"netnew/1996-ISC.txt": empty, f"{MARKER}/1997.txt": full},
        optional={"netnew/1996-ISC.txt"},
    )
    assert skipped == ["netnew/1996-ISC.txt"]
    assert list(manifest["files"]) == [f"{MARKER}/1997.txt"]


def test_a_zero_line_file_refuses_the_price(tmp_path: Path) -> None:
    """The same rule again at pricing time: the manifest may have been built elsewhere."""
    snapshot = _snapshot(tmp_path, held={1996: ["one.com"]})
    manifest, _ = read_manifest(snapshot)
    (snapshot / MARKER / "1996.txt").write_text("")
    manifest["files"][f"{MARKER}/1996.txt"] = {
        "lines": 0,
        "sha256": file_stats(snapshot / MARKER / "1996.txt")[1],
    }
    (snapshot / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(SnapshotError, match="no lines"):
        verify_snapshot(snapshot, manifest)


def test_a_snapshot_that_does_not_match_its_manifest_is_refused(tmp_path: Path) -> None:
    """A file changed under the manifest, one missing, and one nobody listed."""
    snapshot = _snapshot(tmp_path, held={1996: ["one.com"]})
    items = _items(tmp_path / "items.jsonl", [{"host": "two.com", "year": 1996}])

    _write(snapshot / MARKER / "1996.txt", ["one.com", "sneaked.com"])
    with pytest.raises(SnapshotError, match="does not match the manifest"):
        price(snapshot, items)

    snapshot = _snapshot(tmp_path / "b", held={1996: ["one.com"]})
    (snapshot / MARKER / "1999.txt").unlink()
    with pytest.raises(SnapshotError, match="not in the snapshot"):
        price(snapshot, items)

    snapshot = _snapshot(tmp_path / "c", held={1996: ["one.com"]})
    _write(snapshot / "netnew" / "1996.txt", ["unlisted.com"])
    with pytest.raises(SnapshotError, match="not in the manifest"):
        price(snapshot, items)


def test_a_missing_or_broken_manifest_is_refused(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, held={1996: ["one.com"]})
    (snapshot / "manifest.json").unlink()
    with pytest.raises(SnapshotError, match="does not exist"):
        read_manifest(snapshot)
    (snapshot / "manifest.json").write_text("{}")
    with pytest.raises(SnapshotError, match="no 'marker'"):
        read_manifest(snapshot)
    (snapshot / "manifest.json").write_text(json.dumps({"marker": "m", "built_at": "x"}))
    with pytest.raises(SnapshotError, match="no 'files'"):
        read_manifest(snapshot)


def test_an_unknown_track_is_refused(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    items = _items(tmp_path / "items.jsonl", [{"host": "one.com", "year": 1996}])
    with pytest.raises(SnapshotError, match="track must be"):
        price(snapshot, items, track="pool")


def test_file_stats_counts_a_last_line_without_a_newline(tmp_path: Path) -> None:
    path = tmp_path / "x.txt"
    path.write_text("a.com\nb.com")
    assert file_stats(path)[0] == 2


_SPEC = importlib.util.spec_from_file_location(
    "snapshot_manifest",
    Path(__file__).resolve().parent.parent / "scripts/harness/snapshot_manifest.py",
)
snapshot_manifest = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(snapshot_manifest)


def test_staging_holds_exactly_what_the_manifest_names(tmp_path: Path) -> None:
    """What is hashed is what is pushed, and an empty family reaches neither."""
    files = {
        f"{MARKER}/1996.txt": _write(tmp_path / "src" / "1996.txt", ["one.com"]),
        "netnew/1996-ISC.txt": _write(tmp_path / "src" / "1996-ISC.txt", []),
    }
    manifest, skipped = build_manifest(MARKER, files, optional={"netnew/1996-ISC.txt"})
    out = tmp_path / "stage"
    snapshot_manifest.stage(out, files, manifest)
    assert skipped == ["netnew/1996-ISC.txt"]
    assert sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()) == [
        "manifest.json",
        f"{MARKER}/1996.txt",
    ]
    assert (out / MARKER / "1996.txt").read_text() == "one.com\n"
    assert json.loads((out / "manifest.json").read_text()) == manifest


def test_the_snapshot_holds_what_he_keeps_outside_his_pool(tmp_path: Path, monkeypatch) -> None:
    """His ISC collection and unparsed names are candidates he holds, as the export diffs them."""
    baseline = tmp_path / "baseline"
    _write(baseline / "candidate_pool.txt", ["his.com"])
    _write(baseline / "candidate_pool_unparsed_format.txt", ["odd_name.com"])
    _write(baseline / "isc_survey_hostnames" / "1996-ISC.txt", ["host.isc.com"])
    _write(baseline / "isc_survey_hostnames" / "README.md", ["not.a.list.com"])
    monkeypatch.setattr(snapshot_manifest, "EXPORT_NETNEW", tmp_path / "netnew")
    monkeypatch.setattr(snapshot_manifest, "EXPORT_CANDIDATES", tmp_path / "absent.txt")
    files, optional, _absent = snapshot_manifest.sources(baseline, MARKER)
    held = {rel for rel in files if rel.startswith("candidates/")}
    assert held == {
        "candidates/candidate_pool.txt",
        "candidates/candidate_pool_unparsed_format.txt",
        "candidates/isc_survey_hostnames/1996-ISC.txt",
    }
    assert held <= optional


def test_an_absent_export_family_refuses_the_build(tmp_path: Path, monkeypatch) -> None:
    """A held-set the pricer never loads reads exactly like an empty one, so absence is fatal.
    Both units we ship have to be there for all six years: a stale or half-written
    `output/netnew` would price every name we have already delivered as net-new.
    """
    netnew = tmp_path / "netnew"
    baseline = tmp_path / "baseline"
    calculator = _write(tmp_path / "calculator" / "equivalent_english_domains.py", ["pass"])
    _write(calculator.with_name("q2_tld_top_langs.json"), ["{}"])
    _write(netnew / "attested_registrables.txt", ["1996\tours.com"])
    for year in range(1996, 2002):
        _write(netnew / f"{year}.txt", ["ours.com"])
        _write(netnew / f"{year}_hostnames.txt", ["a.ours.com"])
        _write(baseline / f"{year}.txt", ["his.com"])
    monkeypatch.setattr(snapshot_manifest, "EXPORT_NETNEW", netnew)
    monkeypatch.setattr(
        snapshot_manifest, "EXPORT_CANDIDATES", tmp_path / "candidate_unverified.txt"
    )
    monkeypatch.setattr(snapshot_manifest, "CALCULATOR", calculator)

    _files, _optional, absent = snapshot_manifest.sources(baseline, MARKER)
    # the six `-ISC` files and all five candidate exports are absent and allowed to be
    assert snapshot_manifest.must_be_present(absent) == []
    assert len(absent) == 11

    (netnew / "1999_hostnames.txt").unlink()
    (netnew / "attested_registrables.txt").unlink()
    _files, _optional, absent = snapshot_manifest.sources(baseline, MARKER)
    assert snapshot_manifest.must_be_present(absent) == [
        "netnew/1999_hostnames.txt",
        "netnew/attested_registrables.txt",
    ]


def test_the_snapshot_stages_the_claim_and_his_calculator(tmp_path: Path, monkeypatch) -> None:
    """Our claim and his calculator travel with the snapshot, one digest names the claim, and
    the fleet is told which claim to expect."""
    baseline, netnew = tmp_path / "baseline", tmp_path / "netnew"
    calculator = _write(tmp_path / "calculator" / "equivalent_english_domains.py", ["pass"])
    _write(calculator.with_name("q2_tld_top_langs.json"), ["{}"])
    for year in range(1996, 2002):
        _write(baseline / f"{year}.txt", ["his.com"])
        _write(netnew / f"{year}.txt", ["ours.com"])
        _write(netnew / f"{year}_hostnames.txt", ["a.ours.com"])
    _write(netnew / "attested_registrables.txt", ["1998\tours.com"])
    _write(netnew / "candidate_additions.txt", ["cand.com"])
    _write(netnew / "header_candidates.txt", ["header.com"])
    monkeypatch.setattr(snapshot_manifest, "EXPORT_NETNEW", netnew)
    monkeypatch.setattr(snapshot_manifest, "EXPORT_CANDIDATES", tmp_path / "unverified.txt")
    monkeypatch.setattr(snapshot_manifest, "CALCULATOR", calculator)

    def staged(out: Path) -> dict:
        files, optional, absent = snapshot_manifest.sources(baseline, MARKER)
        assert snapshot_manifest.must_be_present(absent) == []
        manifest, _ = build_manifest(MARKER, files, optional, snapshot_manifest.claim_of(files))
        snapshot_manifest.stage(out, files, manifest)
        return manifest

    first = staged(tmp_path / "a")
    for rel in (
        "candidates/candidate_additions.txt",
        "candidates/header_candidates.txt",
        "netnew/attested_registrables.txt",
        "calculator/equivalent_english_domains.py",
        "calculator/q2_tld_top_langs.json",
    ):
        assert rel in first["files"] and (tmp_path / "a" / rel).is_file()
    assert first["files"]["netnew/attested_registrables.txt"]["sorted"] is True
    # his files are not the claim; ours are
    _write(baseline / "1996.txt", ["his.com", "more.com"])
    assert staged(tmp_path / "b")["claim_sha256"] == first["claim_sha256"]
    _write(netnew / "candidate_additions.txt", ["cand.com", "more.com"])
    last = staged(tmp_path / "c")
    assert last["claim_sha256"] != first["claim_sha256"]

    fleet = tmp_path / "fleet"
    fleet.mkdir()
    assert snapshot_manifest.publish_expected(tmp_path / "c", fleet) == 0
    assert json.loads((fleet / "snapshot.json").read_text()) == {
        "marker": MARKER,
        "claim_sha256": last["claim_sha256"],
    }
