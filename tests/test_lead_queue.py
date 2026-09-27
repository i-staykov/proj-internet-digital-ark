"""The owner's queue lists a measured new evidence class and the send, and never opens a store."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/round"))
import lead_queue  # noqa: E402

HOSTS = {"grain": "hostname", "evidence_class": "artifact_listing"}
LEADS = {
    **dict.fromkeys("t-line t-string t-false ipac spacekookie relay-hosts usenet-hops".split(), {}),
    "t-status": {"status": "banked"},
    "t-class": {"blocked_on": "two rule decisions: (1) a new evidence class for targets"},
    "t-download": {"blocked_on": "download decision: 57.6 GB, over the 1 GB fetch cap"},
    "stranded": HOSTS,
    "guessed": {**HOSTS, "size_estimate": {"ee_low": 80000, "ee_high": 90000}},
}
REGISTERS = {
    "sources.md": """| source | date | net-new EE (date) | verdict |
|---|---|---|---|
| ipac | d | fleet 35,429.9 EE, store 3,681.7 EE | FIND |
| spacekookie | d | fleet 1,450.5 EE | FIND (pending) |
| spacekookie-reprice | d | 120 host-years, 93.9 EE | CLOSED |
| usenet | d | 0 EE | CLOSED |
| t-class | d | 9,000 EE | FIND |
| stranded | d | 445.1 EE | FIND |
""",
    "sources-closed.md": """| source | date | measured | reason |
|---|---|---|---|
| relay-hosts / received | d | 445.1 EE | RETIRED. Under the floor. |
""",
}
PAST = {"round": "Round 11", "baseline": "b1", "field5_percent": 5.2, "gate_pct": 5.0}
UNDER = {"round": "9", "baseline": "m", "field5_percent": 0.3823, "distance_to_gate_ee": 9876.4}
GONE = {"round": "10", "round_percent": 6.0, "percent": 6.0, "round_distance_to_gate_ee": 1}


@pytest.mark.parametrize(
    ("blocked", "ask"),
    [
        ("download decision: 57.6 GB, over the 1 GB fetch cap", ""),
        ("a download decision admitting content type application/x-rpm", ""),
        ("a terms answer and a download decision", ""),
        ("approval: RIPE NCC permission to read the files", ""),
        ("a re-run of the pricing cmd", ""),
        ("download decision. Then a rule on author_mail_host as an evidence class.", "class"),
        ("rule: whether a hostname in a FAQ body is master-eligible", "class"),
        ("ask whether to send the round under the 5% gate", "send"),
    ],
)
def test_only_a_class_or_the_send_is_asked(blocked, ask) -> None:
    assert lead_queue.ask_of(blocked) == ask


def test_the_page_lists_a_measured_class_ask_and_the_send(tmp_path, monkeypatch, capsys) -> None:
    banked = {"t-line": True, "t-string": "true", "t-false": False}
    lines = [json.dumps({"kind": "outcome", "slug": s, "banked": b}) for s, b in banked.items()]
    files = {**REGISTERS, "brief.json": json.dumps(PAST), "ledger/2026-09.jsonl": "\n".join(lines)}
    for slug, extra in LEADS.items():
        doc = {"slug": slug, "status": "scouted", "evidence_class": "cdx_x", "grain": "registrable"}
        doc |= {"artifact": {"url": f"https://e.org/{slug}"}, **extra}
        files[f"leads/{slug}.json"] = json.dumps(doc)
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(exist_ok=True)
        (tmp_path / name).write_text(text + "\n", encoding="utf-8")
    reg = lead_queue.measured(tuple(tmp_path / name for name in REGISTERS))
    monkeypatch.setitem(sys.modules, "duckdb", store := MagicMock())
    monkeypatch.setattr(lead_queue, "BRIEF", tmp_path / "brief.json")
    monkeypatch.setattr(lead_queue, "measured", lambda *a, **k: reg)
    assert (held := lead_queue.banked(tmp_path)) == {"t-line", "t-status"}, "only JSON true banks"
    rows = {r["slug"]: r for r in lead_queue.leads(tmp_path, held)}
    assert not {"spacekookie", "relay-hosts", "t-line", "t-status"} & set(rows), "closed or banked"
    assert {"t-false", "t-string", "usenet-hops"} <= set(rows), "unbanked, and no prefix closes"
    assert (rows["ipac"]["low"], rows["ipac"]["high"]) == (3681.7, 3681.7), "the store's figure"
    assert lead_queue.main(["--fleet", str(tmp_path)]) == 0
    page = capsys.readouterr().out
    sections = [line for line in page.splitlines() if line.startswith("## ")]
    assert sections == ["## The send", "## New evidence classes, biggest first"]
    assert "**Round 11 crossed the 5% gate** at 5.2000% against `b1`" in page
    assert "just ship" in page, "past the gate, the send is the owner's"
    assert "### Admit `cdx_x`" in page and "[`t-class`](https://e.org/t-class)" in page
    assert "`t-download`" not in page and "80,000" not in page and "mine to work" not in page
    outlet, _, foot = page.partition("### Give the XIII-excluded")[2].partition("estimate alone")
    assert "**445 EE**" in outlet and "| 445.1 | [`stranded`](https://e.org/stranded)" in outlet
    assert "guessed" not in outlet and "`guessed`" in foot, "an estimate is not a row"
    assert "None. No measured lead asks" in lead_queue.render([], send="x")
    (brief := tmp_path / "brief.json").write_text(json.dumps(GONE), encoding="utf-8")
    assert lead_queue.main(["--fleet", str(tmp_path / "absent")]) == 0
    assert "no leads/" in (said := capsys.readouterr().out) and "queue is not there" in said
    assert "Not known here" in said, "a key the bank stopped writing is no figure"
    assert "Not known here" in lead_queue.send_line(tmp_path / "none.json"), "never guessed"
    brief.write_text(json.dumps(UNDER), encoding="utf-8")
    assert lead_queue.send_line(brief) == (
        "Nothing to send: Round 9 stands at 0.3823% against `m`, under the 5% gate, 9,876 EE short."
    )
    assert store.mock_calls == [], "the queue opened the store"
