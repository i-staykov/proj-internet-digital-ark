"""The queue must not put a measured lead in front of Ivo at its guessed price, nor put anything
in front of him but a new evidence class and the send."""

import contextlib
import io
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts/round"))

import lead_queue  # noqa: E402

HEAD = (
    "| source | version or date | coverage period | retrieval method | what dates one item "
    "| baseline overlap | net-new EE (date) | quality issues | effort | verdict | link |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|\n"
)


def row(slug, ee, verdict):
    return f"| {slug} | d | n/a | n/a | n/a | n/a | {ee} | n/a | n/a | {verdict} | n/a |\n"


def register(tmp: Path, *rows: str) -> Path:
    path = tmp / "sources.md"
    path.write_text(HEAD + "".join(rows), encoding="utf-8")
    return path


class MeasuredTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_the_store_figure_beats_the_fleet_figure(self):
        """`store 3,681.7 EE` beside `fleet 35,429.9 EE` means the fleet counted rows the
        store already holds, so the smaller one is the net-new and the one worth reading."""
        path = register(self.tmp, row("ipac", "fleet 35,429.9 EE, store 3,681.7 EE", "FIND"))
        self.assertEqual(lead_queue.measured((path,))["ipac"][0], 3681.7)

    def test_a_closed_row_is_the_last_word_however_many_precede_it(self):
        path = register(
            self.tmp,
            row("spacekookie", "fleet 1,450.5 EE", "FIND (pending)"),
            row("spacekookie-reprice", "120 host-years, 93.9 EE", "CLOSED"),
        )
        self.assertEqual(
            lead_queue.verdict_of("spacekookie", lead_queue.measured((path,)))[1], "closed"
        )

    def test_a_closed_page_row_is_closed_whatever_word_its_reason_opens_with(self):
        path = self.tmp / "sources-closed.md"
        path.write_text(
            "| source | date | measured | reason | link |\n|---|---|---|---|---|\n"
            "| relay-hosts / received | d | 445.1 EE | RETIRED. Under the floor. |  |\n",
            encoding="utf-8",
        )
        reg = lead_queue.measured((path,))
        self.assertEqual(lead_queue.verdict_of("relay-hosts", reg), (445.1, "closed"))

    def test_a_shorter_name_never_speaks_for_a_longer_lead(self):
        """`usenet` must not answer for `usenet-path-relay-hops`: a prefix match either way
        lets one closed row silently retire every lead that starts with the same word."""
        reg = lead_queue.measured((register(self.tmp, row("usenet", "0 EE", "CLOSED")),))
        self.assertEqual(lead_queue.verdict_of("usenet-path-relay-hops", reg), (None, ""))

    def test_a_measured_lead_loses_its_range_and_a_closed_one_is_dropped(self):
        fleet = self.tmp / "leads"
        fleet.mkdir()
        for slug, low, high in (("alive", 9000, 90000), ("dead", 200000, 300000)):
            (fleet / f"{slug}.json").write_text(
                json.dumps(
                    {
                        "slug": slug,
                        "status": "scouted",
                        "size_estimate": {"ee_low": low, "ee_high": high},
                        "evidence_class": "cdx",
                        "blocked_on": "rule",
                    }
                ),
                encoding="utf-8",
            )
        path = register(
            self.tmp, row("alive", "store 12,000 EE", "FIND"), row("dead", "1,389.1 EE", "CLOSED")
        )
        rows = lead_queue.leads(self.tmp, set(), lead_queue.measured((path,)))
        self.assertEqual([r["slug"] for r in rows], ["alive"])
        self.assertEqual((rows[0]["low"], rows[0]["high"]), (12000.0, 12000.0))

    def test_only_a_measured_figure_is_a_row_and_the_outlet_is_worth_its_leads(self):
        """The measured stranded leads sit under the outlet heading with their own shares, the
        heading is worth what they sum to, and a lead a scout only estimated is named in one
        line rather than asked about. Nothing is marked as the laptop's to do."""

        def lead(slug, ask, low, track="ships", measured=False):
            return {
                "slug": slug,
                "low": low,
                "high": low,
                "ask": ask,
                "track": track,
                "measured": measured,
                "class": "c",
                "status": "scouted",
                "url": f"https://example.org/{slug}",
                "dates": "Received: ... ; Tue, 4 May 1999 11:02:13 -0700",
                "terms": "",
                "said": "parked (outlet), measured on 2.8%",
            }

        page = lead_queue.render(
            [
                lead("relay-hosts", "", 445.1, track="stranded", measured=True),
                lead("guessed", "", 80000.0, track="stranded"),
            ],
            send="Nothing to send.",
        )
        heading = page.index("### Give the XIII-excluded hostnames")
        foot = page.index("on a scout's estimate alone")
        group = page[heading:foot]
        self.assertIn("**445 EE**", group, "the outlet is worth its measured leads alone")
        self.assertIn("[`relay-hosts`](https://example.org/relay-hosts)", group)
        self.assertIn("445.1", group)
        self.assertNotIn("guessed", group, "an estimate is not a row")
        self.assertIn("`guessed`", page[foot:])
        self.assertNotIn("mine to work", page)
        self.assertNotIn("80,000", page)

    def test_an_empty_page_asks_for_no_class(self):
        page = lead_queue.render([], send="Nothing to send.")
        self.assertIn("None. No measured lead asks for a new evidence class.", page)


class NoStore(types.ModuleType):
    """A stand-in `duckdb` that fails the test on any use, so a store read cannot hide
    behind a fallback."""

    def __init__(self):
        super().__init__("duckdb")
        self.touched: list[str] = []

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        self.touched.append(name)
        raise AssertionError(f"the store was opened: duckdb.{name}")


class OnlyTheOwnersAsksTest(unittest.TestCase):
    """The page is the owner's: a new evidence class and the send, read from the fleet's
    lead files and ledger and the bank's brief, with no store and no cached list of it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.fleet = self.tmp / "fleet"
        self.store = NoStore()
        self.brief = self.tmp / "brief.json"
        self.out = self.tmp / "queue.md"
        self.reg: dict = {}
        for target, value in (
            ("REPO", self.tmp),
            ("BRIEF", self.brief),
            ("OUT", self.out),
            ("measured", lambda *a, **k: self.reg),
        ):
            patcher = patch.object(lead_queue, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.dict(sys.modules, {"duckdb": self.store})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        shutil.rmtree(self.tmp)
        self.assertEqual(self.store.touched, [], "the queue opened the store")

    def lead(self, slug, status="scouted", blocked=None, grain="registrable", cls="cdx_x"):
        (self.fleet / "leads").mkdir(parents=True, exist_ok=True)
        doc = {
            "slug": slug,
            "status": status,
            "size_estimate": {"ee_low": 1.0, "ee_high": 2.0},
            "evidence_class": cls,
            "grain": grain,
            "blocked_on": blocked,
            "artifact": {"url": f"https://example.org/{slug}"},
        }
        (self.fleet / "leads" / f"{slug}.json").write_text(json.dumps(doc), encoding="utf-8")

    def outcome(self, slug, banked):
        (self.fleet / "ledger").mkdir(parents=True, exist_ok=True)
        line = {"kind": "outcome", "slug": slug, "decision": "master", "banked": banked}
        with (self.fleet / "ledger/2026-09.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line) + "\n")

    def run_main(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = lead_queue.main(["--fleet", str(self.fleet), *argv])
        return code, out.getvalue()

    def test_banked_reads_outcome_lines_and_lead_statuses_and_never_opens_a_store(self):
        for slug in ("t-line", "t-string", "t-false", "t-live"):
            self.lead(slug)
        self.lead("t-status", status="banked")
        self.outcome("t-line", True)
        self.outcome("t-string", "true")
        self.outcome("t-false", False)
        held = lead_queue.banked(self.fleet)
        self.assertEqual(held, {"t-line", "t-status"}, "only a JSON true banks a line")
        rows = lead_queue.leads(self.fleet, held, {})
        self.assertEqual(sorted(r["slug"] for r in rows), ["t-false", "t-live", "t-string"])
        self.assertFalse(hasattr(lead_queue, "STORE"))
        self.assertFalse(hasattr(lead_queue, "CACHE"))

    def test_no_store_and_no_leads_exits_0_and_writes_a_page_saying_so(self):
        code, said = self.run_main("--write")
        self.assertEqual(code, 0)
        self.assertIn("no leads/", said)
        page = self.out.read_text(encoding="utf-8")
        self.assertIn("The fleet queue is not there", page)
        self.assertIn("## The send", page)
        self.assertIn("Not known here", page, "no brief, so the send is not guessed")

    def test_the_page_lists_only_a_new_class_ask_and_the_send(self):
        self.lead("t-class", blocked="two rule decisions: (1) a new evidence class for targets")
        self.lead("t-download", blocked="download decision: 57.6 GB, over the 1 GB fetch cap")
        self.lead("t-terms", blocked="a terms answer: the host publishes no terms page")
        self.lead("t-rerun", blocked="a re-run of the pricing cmd")
        self.lead("t-plain")
        self.reg = {
            f"t-{name}": (9000.0, "FIND")
            for name in ("class", "download", "terms", "rerun", "plain")
        }
        self.brief.write_text(
            json.dumps({"round": "11", "baseline": "b1", "field5_percent": 5.2, "gate_pct": 5.0}),
            encoding="utf-8",
        )
        code, _ = self.run_main("--write")
        self.assertEqual(code, 0)
        page = self.out.read_text(encoding="utf-8")
        sections = [line for line in page.splitlines() if line.startswith("## ")]
        self.assertEqual(sections, ["## The send", "## New evidence classes, biggest first"])
        self.assertIn("**Round 11 crossed the 5% gate** at 5.2000% against `b1`", page)
        self.assertIn("### Admit `cdx_x`", page)
        self.assertIn("[`t-class`](https://example.org/t-class)", page)
        for other in ("`t-download`", "`t-terms`", "`t-rerun`", "`t-plain`"):
            self.assertNotIn(other, page)

    def test_cached_is_gone_and_no_caller_passes_it(self):
        with self.assertRaises(SystemExit) as refused, contextlib.redirect_stderr(io.StringIO()):
            lead_queue.main(["--fleet", str(self.fleet), "--cached"])
        self.assertEqual(refused.exception.code, 2)
        calls = [
            line
            for line in (REPO / "justfile").read_text(encoding="utf-8").splitlines()
            if "lead_queue.py" in line
        ]
        self.assertTrue(calls)
        self.assertEqual([line for line in calls if "--cached" in line], [])


class SendTest(unittest.TestCase):
    """The send is read from the bank's brief, the figure the gate issue is opened on."""

    def line(self, brief: dict | None) -> str:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "brief.json"
            if brief is not None:
                path.write_text(json.dumps(brief), encoding="utf-8")
            return lead_queue.send_line(path)

    def test_under_the_gate_there_is_nothing_to_send(self):
        said = self.line(
            {
                "round": "10",
                "baseline": "merged260922",
                "field5_percent": 0.3823,
                "gate_pct": 5.0,
                "distance_to_gate_ee": 3008271.3436,
            }
        )
        self.assertEqual(
            said,
            "Nothing to send: Round 10 stands at 0.3823% against `merged260922`, under the 5% "
            "gate, 3,008,271 EE short.",
        )

    def test_past_the_gate_the_send_is_the_owners(self):
        said = self.line({"round": "Round 11", "baseline": "b1", "field5_percent": 5.01})
        self.assertTrue(said.startswith("**Round 11 crossed the 5% gate** at 5.0100%"), said)
        self.assertIn("just ship", said)

    def test_no_brief_is_said_and_never_guessed(self):
        self.assertIn("Not known here", self.line(None))
        self.assertIn("Not known here", self.line({"round": "10"}))
        # The keys the brief no longer carries are no figure at all, so the send never
        # quotes a round the bank stopped writing.
        gone = {"round": "10", "round_percent": 6.0, "percent": 6.0, "round_distance_to_gate_ee": 1}
        self.assertIn("Not known here", self.line(gone))


class AskTest(unittest.TestCase):
    def test_a_class_or_a_ruling_on_evidence_is_an_ask_and_the_loops_own_work_is_not(self):
        for blocked, ask in (
            ("download decision: 57.6 GB, over the 1 GB fetch cap", ""),
            ("a download decision admitting content type application/x-rpm", ""),
            ("a terms answer and a download decision", ""),
            ("approval: RIPE NCC permission to read the files", ""),
            ("a re-run of the pricing cmd", ""),
            ("download decision. Then a rule on author_mail_host as an evidence class.", "class"),
            ("rule: whether a hostname in a FAQ body is master-eligible", "class"),
            ("ask whether to send the round under the 5% gate", "send"),
        ):
            with self.subTest(blocked=blocked):
                self.assertEqual(lead_queue.ask_of(blocked), ask)


if __name__ == "__main__":
    unittest.main()
