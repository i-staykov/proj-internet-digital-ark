"""The pricers hold a pair that is ours or his by exact name in that year, date nothing by an
error capture, refuse a snapshot off its manifest, and quote his calculator's EE."""

import gzip
import importlib.util
import json
import shutil
import subprocess
import sys
from collections import Counter
from decimal import Decimal
from functools import partial
from pathlib import Path

import pytest
from his_release import WEB_METHOD, capture

from ark import english_share, held
from ark import price_snapshot as ps
from ark.baseline import calculator_path
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts/harness"))
import snapshot_manifest as sm  # noqa: E402


def _load(rel: str):
    spec = importlib.util.spec_from_file_location(Path(rel).stem, ROOT / "scripts" / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ph, probe = _load("pricing/price_hostnames.py"), _load("pricing/probe_source.py")
texts, price_items = _load("pricing/probe_texts_corpus.py"), _load("pricing/price_items.py")

# In 1998: ours.com is ours and already-his.com is his; fresh.com is ours in another year;
# seeded.com is a candidate of ours with no row; no file of his holds his-filed.com or rolled.com;
# ourss.com and already-hiss.com are one edit from a known name
NAMES = "ours.com already-his.com fresh.com seeded.com his-filed.com held-candidate.com "
NAMES += "lonely.com ourss.com already-hiss.com rolled.com"


def test_the_pricers_hold_by_exact_name(tmp_path: Path, his_files: Path, monkeypatch, capsys):
    """price_items, probe_texts_corpus and request_approval ask `held`, against one store. The
    typo bound asks the one-edit neighbourhood of a name, never the name itself."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    conn = connect(store := tmp_path / "data/ark.duckdb")
    init_db(conn)
    ours = ensure_source(conn, "ia_cdx", "timestamped")
    for name in ("ours.com", "fresh.com", "seeded.com"):
        add_candidate(conn, name, ours)
    for name, year in (("ours.com", 1998), ("fresh.com", 2000)):
        value = capture(name, year)
        row = record_evidence(conn, name, ours, year, "cdx_timestamp", value, None, WEB_METHOD)
        assign_year(conn, row)
    conn.close()

    def run(module, *argv: str) -> str:
        monkeypatch.setattr(sys, "argv", ["script", *argv])
        module.main()
        return capsys.readouterr().out

    items = tmp_path / "items.jsonl"
    items.write_text(json.dumps({"item": "i1", "year": 1998, "text": NAMES}) + "\n")
    monkeypatch.setattr(price_items, "STORE", store)
    out = run(price_items, "--items", str(items))
    assert "already held, ours or his  : 2\n" in out
    assert "net-new AFTER the split    : 1 pairs" in out
    assert "to the candidate pool      : 7 pairs, 5 names new to the pool" in out
    assert "typo upper bound         : 2 of 8 sampled net-new names" in out
    variants = price_items.one_edit_variants("ab.com")
    assert "ab.com" not in variants and "ba.com" not in variants  # a transposition is two edits
    assert {"a.com", "abc.com", "ax.com", "b.com", "aab.com"} <= variants

    monkeypatch.setattr(texts, "search", lambda query, rows: [{"identifier": "i1", "year": 1998}])
    monkeypatch.setattr(texts, "full_text", lambda identifier, cache: NAMES)
    out = run(texts, "--query", "q", "--cache", str(tmp_path / "c"))
    assert "net-new pairs        8\nnet-new domains      7\n" in out
    assert "corroborated (domain already in an annual file): 1\n" in out
    assert "never seen at all (not even a candidate): 5\n" in out

    approval = _load("harness/request_approval.py")
    register = tmp_path / "approvals.md"
    register.write_text("## Pending requests\n\nNone.\n", encoding="utf-8")
    monkeypatch.setattr(approval, "ROOT", tmp_path)
    monkeypatch.setattr(approval, "APPROVALS", register)
    monkeypatch.setattr(approval, "nearest_closed", lambda name: "nothing close.")
    journal = tmp_path / "udrp.jsonl"
    journal.write_text(
        "".join(json.dumps({"domain": d, "year": 1998}) + "\n" for d in NAMES.split())
    )
    run(approval, "udrp_proceedings", "--journal", str(journal))
    table = register.read_text(encoding="utf-8")
    assert "| already held, ours or his | 2 |" in table
    assert "| `master` (taking the corroboration split) | 1 |" in table


def _journal(path: Path, rows: list[tuple[str, ...]]) -> Path:
    with gzip.open(path, "wt") as fh:
        for url, ts, *status in rows:
            fh.write(
                json.dumps({"url": url, "timestamp": ts, "status": (*status, "200")[0]}) + "\n"
            )
    return path


def test_the_hostname_funnel_is_the_ingests_and_holds_by_exact_name(tmp_path, his_files) -> None:
    """A 4xx or 5xx capture stays on the candidate track: only a capture that answered dates a
    hostname year or a registrable one. His `www.rolled.com` holds neither `rolled.com` nor its
    hosts, and a name his file holds in any year makes its parent held."""
    journal = _journal(
        tmp_path / "x.jsonl.gz",
        [
            ("http://new.held.com/a", "19990301000000"),  # net-new hostname year
            ("http://new.held.com/b", "19990101000000"),  # same host-year, earlier stamp
            ("http://old.held.com/", "19990101000000", "301"),  # already in the store
            ("http://www.held.com/", "19990101000000"),  # the parent's own site
            ("http://held.com/", "19990101000000"),  # a registrable row: our pair
            ("http://a.fresh.org/", "20010101000000"),  # parent held by no one
            ("http://fresh.org/", "20010601000000"),  # a registrable row, its pair net-new
            ("http://gone.fresh.org/", "19990101000000", "404"),
            ("http://down.fresh.org/", "19990101000000", "503"),
            ("http://x.example.com/", "19950101000000"),  # out of window
            ("http://bad_host.example.com/", "19990101000000"),  # underscore, refused
            ("http://deep.his-host.net/", "20010101000000"),  # his 2001 file lists it
            ("http://early.his.org/", "19990101000000"),  # his 1996 line holds no other year
            ("http://www.deep.his-host.net/", "20010101000000"),  # his file holds the bare name
            ("http://his-host.net/", "20010101000000"),  # net-new: his line is `deep.`
            ("http://sub.rolled.com/", "19990101000000"),
            ("http://rolled.com/", "19990101000000"),  # net-new: his `www.` is another name
            ("http://new.already-his.com/", "19990101000000"),
            ("http://already-his.com/", "19990101000000"),  # his file holds it
        ],
    )
    seen, counts = ph.read_rows([journal], items=False, head=None)
    rows, pairs = ph.funnel(seen, counts)
    assert (counts["out_of_window"], counts["no_host"], counts["error_status"]) == (1, 1, 2)
    assert counts["registrable_row"] == 5 and counts["www_of_parent"] == 1
    # only a row naming the registrable itself dates it: `www.held.com` and `a.fresh.org` do not
    names = "already-his.com fresh.org held.com his-host.net rolled.com".split()
    assert pairs == list(zip(names, (1999, 2001, 1999, 2001, 1999), strict=True))
    conn = connect(":memory:")
    init_db(conn)
    cdx = ensure_source(conn, "ia_cdx_hostnames", "timestamped")
    add_candidate(conn, "held.com", cdx)
    assign_year(conn, eid := record_evidence(conn, "held.com", cdx, 1999, "cdx_timestamp", "x"))
    insert = "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id)"
    conn.execute(f"{insert} VALUES ('old.held.com', 'held.com', 1999, ?)", [eid])
    priced = ph.price(conn, rows, pairs, held.load())
    assert (priced["candidates"], priced["in_store"], priced["in_baseline_only"]) == (8, 1, 1)
    assert priced["registrable_candidates"] == 5, "the pairs the same rows assert"
    assert sorted(priced["netnew_rows"]) == [
        ("a.fresh.org", 2001, False),
        ("early.his.org", 1999, False),
        ("new.already-his.com", 1999, False),
        ("new.held.com", 1999, False),
        ("sub.rolled.com", 1999, False),
        ("www.deep.his-host.net", 2001, True),
    ]
    assert priced["www_of_held_name"] == 1 and priced["netnew_ee"] > 0
    assert priced["netnew_by_year"] == {1999: 4, 2001: 2} and priced["netnew_hostname_years"] == 6
    # held.com is ours and already-his.com his; fresh.org, rolled.com and his-host.net no one's
    assert priced["parent_held_share"] == 3 / 8 and priced["parent_pairs_netnew"] == 3


def test_items_mode_takes_a_year_and_several_hosts_and_head_cuts_each_file(tmp_path) -> None:
    items = tmp_path / "items.jsonl"
    records = [{"item": "p1", "year": 2000, "text": "ftp.held.com mail.held.com"}]
    records.append({"item": "p2", "date": "12 Mar 1994", "text": "gone.held.com"})
    items.write_text("".join(json.dumps(r) + "\n" for r in records))
    seen, counts = ph.read_rows([items], items=True, head=None)
    assert counts["undated_or_out_of_window"] == 1
    assert sorted(seen) == [("ftp.held.com", 2000), ("mail.held.com", 2000)]
    hosts = [(f"http://h{i}.held.com/", "19990101000000") for i in range(10)]
    _seen, counts = ph.read_rows([_journal(tmp_path / "y.jsonl.gz", hosts)], items=False, head=3)
    assert counts["lines"] == 3 and counts["head_cut_files"] == 1


# **The snapshot pricer.** A fleet leg prices against name lists, his calculator and a manifest.

MARKER = "merged260908"
COM = 0.6321
# His calculator's interface, for a fresh clone that lacks his; the parity test runs his. It
# imports the English-share module alone: `import ark` would load the whole package.
STAND_IN = f"""import json, sys; from decimal import Decimal; from pathlib import Path
sys.path.insert(0, {str(Path(english_share.__file__).parent)!r}); import english_share as share
weights = share.english_weights(Path(__file__).with_name("q2_tld_top_langs.json"))
names = {{line.strip() for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()}}
out = Path(sys.argv[sys.argv.index("--output-dir") + 1]); out.mkdir(parents=True, exist_ok=True)
ee = sum((weights.get(n.rsplit(".", 1)[-1], Decimal(0)) for n in names), Decimal(0))
summary = {{"unique_valid_domains": len(names), "equivalent_english_domains": format(ee, "f")}}
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
        shutil.copy(calculator / path.name if calculator else english_share.SHARE_PATH, path)
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


def test_held_is_the_exact_name_in_its_year_and_neither_form_holds_the_other(tmp_path) -> None:
    """Our export is held too, and a held child, parent or `www.` form holds no other form."""
    held = {1998: ["held.com"], 1999: ["his.com"], 2000: ["mail.parent.com", "lone.com"]}
    held[2001] = ["bare.com", "www.other.com"]
    ours = {"1999.txt": ["ours.com"], "1999_hostnames.txt": ["a.ours.com"]}
    items = [f"{h}:1998" for h in ("held.com", "fresh.com", "www.other.com")]
    items += [f"{h}:1999" for h in ("his.com", "ours.com", "a.ours.com", "b.ours.com")]
    items += [f"{h}:2000" for h in ("parent.com", "mail.parent.com", "sub.lone.com")]
    items += ["www.bare.com:2001", "other.com:2001"]
    snapshot = _snapshot(tmp_path, held=held, netnew=ours)
    priced, ee = ps.price(snapshot, _items(tmp_path, *items)), f"{7 * COM:.4f}"
    manifest, sha = ps.read_manifest(snapshot)
    _check(priced, track="annual", split=ps.SPLIT_AUTO, netnew_pairs=7, ee=ee, items=12)
    pairs = {year: row["pairs"] for year, row in priced["by_year"].items()}
    assert pairs == {"1998": 2, "1999": 1, "2000": 2, "2001": 2}
    assert priced["by_tld"] == [{"tld": "com", "pairs": 7, "ee": ee}]
    _check(priced, already_held=5, www_of_parent=2, hostname_records=4, www_alias_share=0.2857)
    _check(priced, parent_held_share=0.75, snapshot_marker=MARKER, manifest_sha=sha)
    assert priced["snapshot_built_at"] == manifest["built_at"]
    with pytest.raises(ps.SnapshotError, match="track must be"):
        ps.price(snapshot, _items(tmp_path, "one.com:1998"), track="pool")


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
    """What is hashed is what is pushed, each unit we ship is there for all six years, and a
    zero-line file refuses the build unless it may be left out."""
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
    empty = _write(netnew / "1996-ISC.txt", [])
    with pytest.raises(ps.SnapshotError, match="no lines"):
        ps.build_manifest(MARKER, {"netnew/1996-ISC.txt": empty})
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
    absent = sm.sources(baseline, MARKER)[2]
    assert sm.must_be_present(absent) == ["netnew/1999_hostnames.txt", ps.ATTESTED]
    (tmp_path / "x.txt").write_text("a.com\nb.com")
    assert ps.file_stats(tmp_path / "x.txt")[0] == 2, "a last line without a newline counts"


# **The extractors.** The prose one and the wide one for hostname lists never invent a domain
# out of a longer host or a filename; the wide one keeps every TLD that carries an English weight.

NARROW, WIDE = texts.domains_in, price_items.wide_domains_in
PROSE = "it ends at foo.com. then http://bar.org/index.html, www.bbc.co.uk, try www.unimelb.edu.au"
LIST = "www.uni-koeln.de, www.sony.co.jp, see www.nctu.edu.tw, baz.dk, foo.invalidtld"
EXTRACTED = {
    "longer-host": (NARROW, "see www.nctu.edu.tw or mail x@dept.tku.edu.tw please", set()),
    "label-inside-a-host": (NARROW, "host tuvok.au.af.mil answered", {"af.mil"}),
    "filenames": (NARROW, "files foo.org.html, archive.zip, lib.so and doc.ps on disk", set()),
    "prose": (NARROW, PROSE, {"foo.com", "bar.org", "bbc.co.uk", "unimelb.edu.au"}),
    "wide": (WIDE, LIST, {"uni-koeln.de", "sony.co.jp", "nctu.edu.tw", "baz.dk"}),
}


@pytest.mark.parametrize(("extract", "prose", "found"), EXTRACTED.values(), ids=EXTRACTED.keys())
def test_the_extractors_find_exactly_these_names(extract, prose, found) -> None:
    assert extract(prose) == found


def test_an_items_own_host_field_is_a_name_and_an_ocr_file_is_named_by_its_metadata(monkeypatch):
    """The `host` and `domain` fields are read as names; prose in `text` is not. A scan may be
    named freely, so the djvu text's name is read from the item's metadata."""
    record = {"host": "0---0-animal.dk", "year": 2001, "text": "DK Zonen header 20010413"}
    assert price_items.field_names(record) == {"0---0-animal.dk"}
    assert price_items.field_names({"text": "just prose"}) == set()
    assert price_items.field_names({"domain": "www.example.co.uk"}) == {"example.co.uk"}
    calls, name = [], "Internet Magazine 031 [1997-06]"
    files = [{"name": f"{name}.pdf"}, {"name": f"{name}_djvu.txt", "format": "DjVuTXT"}]
    reply = json.dumps({"files": files}).encode()
    monkeypatch.setattr(texts, "fetch", lambda url: calls.append(url) or reply)
    assert texts.djvu_name("internet-magazine-031-1997-06") == f"{name}_djvu.txt"
    assert calls == ["https://archive.org/metadata/internet-magazine-031-1997-06"]


# **The declarative probe** counts every row it drops under a reason and never guesses a column.

HOST = r"(?i)\b([a-z0-9][a-z0-9\-]{0,62}(?:\.[a-z0-9][a-z0-9\-]{0,62})*\.[a-z]{2,6})\b"
TABLE = {"kind": "html_table", "domain_column": 1, "date_column": 0}


def _table(*rows: tuple[str, ...]) -> str:
    cells = ("".join(f"<td>{cell}</td>" for cell in row) for row in rows)
    return "<table>" + "".join(f"<tr>{row}</tr>" for row in cells) + "</table>"


def test_a_table_counts_every_row_it_drops_and_splits_a_cell_of_several_names() -> None:
    """The UDRP dockets put every disputed name of a case in one cell."""
    got = list(probe.pairs_from(TABLE, _table(("1998-04-02", "example.com")), Counter()))
    assert got == [("row 0", "example.com", "1998-04-02", "1998-04-02 | example.com")]
    spec, stats = {**TABLE, "domain_pattern": HOST, "header_rows": 1}, Counter()
    cells = [("Date", "Domain"), ("2000-01-05", "one.com, two.net and three.org")]
    page = _table(*cells, ("1998",), ("1999", "none"))
    names = [name for _i, name, _d, _w in probe.pairs_from(spec, page, stats)]
    assert names == ["one.com", "two.net", "three.org"]
    # the header row is skipped, not counted as seen or refused
    assert stats == {"rows_seen": 3, "refused_short_row": 1, "refused_no_hostname_in_cell": 1}
    for bad, match in (({"kind": "html_table"}, "not guess"), ({**TABLE, "table": 3}, "index 3")):
        with pytest.raises(SystemExit, match=match):
            list(probe.pairs_from(bad, _table(("a", "b")), Counter()))


def test_lines_take_group_1_of_the_date_and_a_year_outside_the_window_is_refused() -> None:
    page = "1996-11-30  widgets.co.uk  some description\nnothing useful here\n"
    for date, when in (
        (r"\b(\d{4})-\d{2}-\d{2}\b", "1996"),
        (r"\b\d{4}-\d{2}-\d{2}\b", "1996-11-30"),
    ):
        spec, stats = {"kind": "lines", "domain_pattern": HOST, "date_pattern": date}, Counter()
        got = [(name, w) for _i, name, w, _r in probe.pairs_from(spec, page, stats)]
        assert got == [("widgets.co.uk", when)] and probe.year_of(spec, when, Counter()) == 1996
        assert stats == {"rows_seen": 2, "refused_no_hostname_match": 1}
    stats = Counter()
    assert probe.year_of({}, "2004-01-01", stats) is probe.year_of({}, "no date", stats) is None
    assert (stats["refused_year_out_of_window"], stats["refused_no_date"]) == (1, 1)
    assert probe.year_of({"year": 1997}, "", Counter()) == 1997
    assert probe.year_of({"year": 2005}, "", Counter()) is None


def test_jsonl_reads_a_dotted_path_and_bad_json_is_not_a_missing_field() -> None:
    spec = {"kind": "jsonl", "domain_field": "ldhName", "date_field": "events.0.eventDate"}
    page = 'not json at all\n{"other": "x"}\n'
    page += '{"ldhName": "thing.org", "events": [{"eventDate": "1999-02-01"}]}\n'
    stats = Counter()
    got = [(name, when) for _i, name, when, _w in probe.pairs_from(spec, page, stats)]
    assert got == [("thing.org", "1999-02-01")]
    assert stats == {"rows_seen": 3, "refused_unparseable_json": 1, "refused_field_absent": 1}
    record = {"a": [{"b": 1}]}
    assert probe.dotted(record, "a.0.b") == 1
    assert [probe.dotted(record, path) for path in ("a.9.b", "a.0.missing", "a.b")] == [None] * 3
