"""The queue must not put a measured lead in front of Ivo at its guessed price."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/round"))

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
        self.tmp = Path(__file__).resolve().parents[1] / "data/_t_lead_queue"
        self.tmp.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        for p in self.tmp.iterdir():
            p.unlink()
        self.tmp.rmdir()

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
        for p in fleet.iterdir():
            p.unlink()
        fleet.rmdir()

    def test_only_a_ruling_reaches_his_table(self):
        """A download is the laptop's disk and an ingest is the standing rule: neither is
        his to settle, and a queue that lists them spends the attention it exists to save."""

        def lead(slug, ask, low):
            return {
                "slug": slug,
                "low": low,
                "high": low,
                "ask": ask,
                "track": "ships",
                "held": "",
                "measured": False,
                "class": "c",
                "status": "scouted",
            }

        page = lead_queue.render([lead("his", "rule", 9000), lead("mine", "download", 80000)])
        table = page[page.index("## Yours to rule") : page.index("- **rule**")]
        self.assertIn("`his`", table)
        self.assertNotIn("`mine`", table)
        self.assertIn("are mine to work", page)

    def test_the_foot_does_not_call_a_stranded_lead_one_that_needs_nothing(self):
        """The page said the same leads ship NOWHERE and need no ruling, which are opposite
        claims about the same rows. Starting them needs no ruling; reaching the claim does."""

        def lead(slug, ask, low, track="ships"):
            return {
                "slug": slug,
                "low": low,
                "high": low,
                "ask": ask,
                "track": track,
                "held": "",
                "measured": False,
                "class": "c",
                "status": "scouted",
            }

        page = lead_queue.render(
            [lead("his", "rule", 9000), lead("mine", "download", 80000, "stranded")]
        )
        self.assertIn("All of them are in the class the outlet row above governs", page)
        self.assertNotIn("need no ruling", page)


if __name__ == "__main__":
    unittest.main()
