"""The cost table the platform ranker divides by, and the fallback for a parent without one.

`rank_platform_parents.py` ranks a parent by `headroom x TLD weight / rows_per_host`, because
a CDX page costs the same whatever it returns and only distinct (host, year) pairs are records.
The divisor comes from `data/raw/cdx/rows_per_host.tsv`, which nothing built: it was written by
hand on 2026-09-04 over 339 parents, and by 2026-09-10 the collectors had walked 3,543. So the
cost term was live for a tenth of the queue, and the other nine tenths fell through to a
fallback of 1.0, which is not a neutral guess but the cheapest value the ratio can take.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts/engines/build_rows_per_host.py"
RANKER = ROOT / "scripts/engines/rank_platform_parents.py"
LOOP = ROOT / "scripts/engines/platform_sweep_loop.sh"


def _module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _journal(directory: Path, safe: str, hosts: list[str], stamp: str = "20260910T000000Z") -> Path:
    """One uncompressed-in-name journal is enough: the builder shells out to `gzip -cd`."""
    import gzip

    path = directory / f"suffix_{safe}_{stamp}.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for host in hosts:
            fh.write(
                json.dumps({"url": f"http://{host}:80/a/b", "timestamp": "19990101000000"}) + "\n"
            )
    return path


def test_the_builder_counts_rows_and_distinct_hosts_per_parent(tmp_path, monkeypatch) -> None:
    module = _module(BUILDER, "build_rows_per_host")
    journals = tmp_path / "cdx_suffix"
    journals.mkdir()
    # six rows over three distinct hosts, so the ratio is exactly 2.0
    _journal(journals, "example_com", ["a.example.com", "a.example.com", "b.example.com"])
    _journal(
        journals,
        "example_com",
        ["b.example.com", "c.example.com", "c.example.com"],
        stamp="20260910T010000Z",
    )
    monkeypatch.setattr(module, "JOURNALS", journals)

    out = tmp_path / "rows_per_host.tsv"
    monkeypatch.setattr(sys, "argv", ["build", "--out", str(out)])
    assert module.main() == 0
    rows = [ln.split("\t") for ln in out.read_text().splitlines() if not ln.startswith("#")]
    assert rows == [["example.com", "6", "3", "2.00"]], rows


def test_the_parent_name_survives_the_round_trip_through_the_file_name(tmp_path, monkeypatch):
    """The loop writes the parent with dots as underscores; a label cannot contain one."""
    module = _module(BUILDER, "build_rows_per_host")
    journals = tmp_path / "cdx_suffix"
    journals.mkdir()
    _journal(journals, "vision_net_au", ["www.vision.net.au"])
    monkeypatch.setattr(module, "JOURNALS", journals)
    assert list(module.parents_and_journals()) == ["vision.net.au"]


def test_a_fresh_table_is_left_alone_so_the_refill_can_call_it_blind(tmp_path, monkeypatch):
    module = _module(BUILDER, "build_rows_per_host")
    journals = tmp_path / "cdx_suffix"
    journals.mkdir()
    _journal(journals, "example_com", ["a.example.com"])
    monkeypatch.setattr(module, "JOURNALS", journals)
    out = tmp_path / "rows_per_host.tsv"
    out.write_text("# untouched\n")
    monkeypatch.setattr(sys, "argv", ["build", "--out", str(out), "--max-age-hours", "6"])
    assert module.main() == 0
    assert out.read_text() == "# untouched\n"


def test_an_unmeasured_parent_is_priced_at_the_median_and_not_at_the_best_case() -> None:
    source = RANKER.read_text()
    assert "ratios.get(parent, unmeasured)" in source, "the 1.0 fallback is back"
    assert "statistics.median(ratios.values())" in source


def test_the_refill_rebuilds_the_table_it_divides_by() -> None:
    """A table nothing rebuilds goes stale silently, which is how this one reached six days."""
    text = LOOP.read_text()
    assert 'COSTS="scripts/engines/build_rows_per_host.py"' in text
    assert "--max-age-hours 6" in text
    assert subprocess.run(["bash", "-n", str(LOOP)], check=False).returncode == 0
