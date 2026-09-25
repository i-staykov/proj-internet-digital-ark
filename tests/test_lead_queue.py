"""The queue must not put a measured lead in front of Ivo at its guessed price."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_only_a_measured_figure_is_a_row_and_a_ruling_heads_its_group(self):
        """Ivo's approval list: a rule decision is a heading, the measured stranded leads sit
        under the outlet heading with their own shares, and a lead a scout only estimated is
        named at the foot rather than asked about. Nothing is marked as the laptop's to do."""

        def lead(slug, ask, low, track="ships", measured=False, cls="c"):
            return {
                "slug": slug,
                "low": low,
                "high": low,
                "ask": ask,
                "track": track,
                "held": "",
                "measured": measured,
                "class": cls,
                "status": "scouted",
                "url": f"https://example.org/{slug}",
                "dates": "Received: ... ; Tue, 4 May 1999 11:02:13 -0700",
                "terms": "",
                "said": "parked (outlet), measured on 2.8%",
            }

        outlet = lead(
            "Give the XIII-excluded hostnames a candidate outlet",
            "rule",
            26370.0,
            measured=True,
            cls="decision in key-decisions.md",
        )
        page = lead_queue.render(
            [
                outlet,
                lead("relay-hosts", "download", 445.1, track="stranded", measured=True),
                lead("guessed", "download", 80000.0, track="stranded"),
            ]
        )
        heading = page.index("### Give the XIII-excluded hostnames")
        foot = page.index("## Not yet measured")
        group = page[heading:foot]
        self.assertIn("26,815 EE", group, "the ruling's worth is the store plus its sources")
        self.assertIn("[`relay-hosts`](https://example.org/relay-hosts)", group)
        self.assertIn("445.1", group)
        self.assertNotIn("guessed", group, "an estimate is not a row")
        self.assertIn("`guessed`", page[foot:])
        self.assertNotIn("mine to work", page)
        self.assertNotIn("80,000", page)

    def test_an_empty_foot_says_everything_is_priced(self):
        page = lead_queue.render([])
        self.assertIn("None. Every live lead has been read and priced.", page)


class CachedTest(unittest.TestCase):
    def test_cached_reads_only_the_slug_list_and_says_when_it_is_missing(self):
        """The hourly tick opens no store: `--cached` drops what the slug list names even
        with a store beside it naming others, and with no list the page says so."""
        import duckdb

        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            store, cache = tmp / "ark.duckdb", tmp / "banked_slugs.txt"
            conn = duckdb.connect(str(store))
            conn.execute("CREATE TABLE ingested_file AS SELECT 'store_only' AS source_name")
            conn.execute("CREATE TABLE evidence AS SELECT 'store_only' AS acquisition_method")
            conn.close()
            (tmp / "leads").mkdir()
            for slug in ("t-banked", "t-live", "store-only"):
                (tmp / "leads" / f"{slug}.json").write_text(
                    json.dumps({"slug": slug, "status": "scouted"}), encoding="utf-8"
                )
            cache.write_text("t-banked\n", encoding="utf-8")

            def page() -> str:
                out = io.StringIO()
                argv = ["lead_queue.py", "--fleet", str(tmp), "--cached"]
                with patch.object(sys, "argv", argv), contextlib.redirect_stdout(out):
                    self.assertEqual(lead_queue.main(), 0)
                return out.getvalue()

            with (
                patch.object(lead_queue, "STORE", store),
                patch.object(lead_queue, "CACHE", cache),
                patch.object(lead_queue, "DECISIONS", tmp / "none.md"),
                patch.object(lead_queue, "measured", lambda *a, **k: {}),
            ):
                self.assertEqual(lead_queue.banked(store, cached=True), ({"t-banked"}, True))
                text = page()
                self.assertNotIn("`t-banked`", text)
                self.assertIn("`store-only`", text, "the store was never read")
                self.assertNotIn("could not be read", text)
                self.assertEqual(cache.read_text(encoding="utf-8"), "t-banked\n")
                cache.unlink()
                text = page()
                self.assertIn("`t-banked`", text)
                self.assertIn("**The store could not be read this run**", text)
                # The store would have dropped `store-only`, had it been read.
                self.assertEqual(lead_queue.banked(store), ({"store-only"}, True))


if __name__ == "__main__":
    unittest.main()
