"""The suffix converter reads only new or grown journals and dates exact hosts only."""

from __future__ import annotations

import gzip
import importlib.util
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "cdx_suffix_convert", ROOT / "scripts/engines/cdx_suffix_convert.py"
)
conv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conv)


def _journal(path: Path, rows: list[tuple[str, str]], mode: str = "wb") -> None:
    """Capture rows as one gzip member; "ab" appends a member, as a live sweep grows a file."""
    with gzip.open(path, mode) as fh:
        for url, ts in rows:
            fh.write((json.dumps({"url": url, "timestamp": ts}) + "\n").encode())


def _run(tmp: Path, tag: str, out: str = "out", state: str | None = "state.tsv") -> None:
    argv = ["--glob", str(tmp / "in/*.jsonl.gz"), "--out", str(tmp / out), "--tag", tag]
    conv.main(argv + (["--state", str(tmp / state)] if state else []))


def _claim(out: Path) -> dict[str, set[int]]:
    """Every output journal's rows, unioned per domain."""
    claim: dict[str, set[int]] = {}
    for path in out.glob("cdx_suffix_*.jsonl.gz"):
        with gzip.open(path, "rt") as fh:
            for line in fh:
                row = json.loads(line)
                claim.setdefault(row["domain"], set()).update(row["years"])
    return claim


def test_a_rerun_reads_no_journal_and_writes_nothing(tmp_path, capsys):
    (tmp_path / "in").mkdir()
    _journal(tmp_path / "in/suffix_x_com_1.jsonl.gz", [("http://x.com/", "19990101000000")])
    _run(tmp_path, "first", state=None)
    state = tmp_path / "out" / conv.STATE_NAME
    before = state.stat().st_mtime_ns
    capsys.readouterr()

    _run(tmp_path, "second", state=None)

    out = capsys.readouterr().out
    assert "0 journal(s) read, 1 unchanged" in out and "nothing written" in out
    assert {p.name for p in (tmp_path / "out").iterdir()} == {
        "cdx_suffix_first.jsonl.gz",
        conv.STATE_NAME,
    }
    assert state.stat().st_mtime_ns == before


def test_only_an_exact_host_dates_a_registrable_and_the_increments_add_up(tmp_path):
    """A www, sub or underscore capture never dates the bare name, and a journal that grows
    between runs gives, over both runs, what one fresh full run gives."""
    (tmp_path / "in").mkdir()
    grown = tmp_path / "in/suffix_x_com_1.jsonl.gz"
    _journal(
        grown,
        [
            ("http://x.com/", "19980101000000"),
            ("http://www.x.com/", "19970101000000"),
            ("http://nt_srv.x.com/", "19990101000000"),
            ("http://x.com/later", "20050101000000"),
            ("https://www.y.com/", "19990101000000"),
            ("http://sub.z.com:80/a", "20000101000000"),
        ],
    )
    _run(tmp_path, "one")
    _journal(grown, [("http://X.com./", "20010101000000")], mode="ab")
    _journal(tmp_path / "in/suffix_y_com_2.jsonl.gz", [("http://x.com:8080/", "19960101000000")])
    _run(tmp_path, "two")

    _run(tmp_path, "full", out="fresh", state="fresh.tsv")

    assert _claim(tmp_path / "out") == _claim(tmp_path / "fresh") == {"x.com": {1996, 1998, 2001}}


def test_a_corrupt_journal_is_named_and_the_others_convert(tmp_path, capsys):
    """Bad magic raises BadGzipFile and a corrupt deflate stream raises zlib.error, which is
    not an OSError. A live journal's missing end-of-stream marker keeps the rows before it."""
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "suffix_magic_1.jsonl.gz").write_bytes(b"not a gzip at all\n")
    (inp / "suffix_deflate_1.jsonl.gz").write_bytes(gzip.compress(b"")[:10] + b"\xff" * 64)
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as fh:
        fh.write(b'{"url": "http://live.com/", "timestamp": "19990101000000"}\n')
        fh.flush()
        cut = buf.tell()
    (inp / "suffix_live_1.jsonl.gz").write_bytes(buf.getvalue()[:cut])
    _journal(inp / "suffix_good_1.jsonl.gz", [("http://good.com/", "20000101000000")])

    _run(tmp_path, "one")

    out = capsys.readouterr().out
    assert "bad gzip, skipped: suffix_magic_1.jsonl.gz" in out
    assert "bad gzip, skipped: suffix_deflate_1.jsonl.gz" in out
    assert "4 journal(s) read, 0 unchanged, 2 bad" in out
    assert _claim(tmp_path / "out") == {"good.com": {2000}, "live.com": {1999}}

    _run(tmp_path, "two")

    out = capsys.readouterr().out
    assert "still bad: suffix_magic_1.jsonl.gz" in out and "still bad: suffix_deflate_1" in out
    assert "0 journal(s) read, 4 unchanged, 2 bad" in out
