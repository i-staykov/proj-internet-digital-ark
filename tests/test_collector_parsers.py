"""What each collector parser reads from its source and what it refuses; loaded by path."""

import gzip
import importlib.util
from collections import Counter
from pathlib import Path

import pytest

SOURCES = Path(__file__).resolve().parents[1] / "scripts/sources"


def _load(path: str):
    spec = importlib.util.spec_from_file_location(Path(path).stem, SOURCES / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


attrition = _load("directories/collect_attrition.py")
maillists = _load("mail_corpora/collect_mailing_lists.py")
udrp = _load("directories/collect_udrp_proceedings.py")
pandora = _load("directories/seed_pandora_titles.py")

CORONUS = (
    '[99.11.30] Li [potus] <a href="1999/11/30/www.coronus.com/">Coronus</a>'
    ' (<a href="http://www.coronus.com">www.coronus.com</a>)'
)
YEAR_OFF = '[99.08.23] Li [x] <a href="1998/08/23/www.prim-nov.si/">Org</a> ( www.prim-nov.si )'
DAY_OFF = '[99.08.09] Li [x] <a href="1999/08/08/www.phonefun.com/">Org</a> ( www.phonefun.com )'
MAIL_INDEX = """
  <a href="1999-January.txt.gz">[ Gzip'd Text ]</a> <a href="2001-December.txt">[ Text ]</a>
  <a href="2004-March.txt.gz">out</a> <a href="1995-July.txt">out</a>
  <a href="1999-January/thread.html">a thread page, not an archive file</a>
"""
MBOX = (
    "From someone@example.com Mon Jan  4 09:00:00 1999\nDate: Mon, 4 Jan 1999 09:00:00 +0000\n"
    "Subject: one\n\nsee http://widgets.example.org/ for details\n\n"
    "From other@example.net Tue Jan  5 09:00:00 1999\nDate: Tue, 5 Jan 1999 09:00:00 +0000\n"
    "Subject: two\n\nnothing here\n"
)
WIPO = "https://www.wipo.int/amc/en/domains/decisions/html/"
PANDORA = (
    "tep_id,name,gathered_url,surt\n"
    '/tep/1,"A title",http://www.acoss.org.au/some/path.pdf,"au,org,acoss)/some/path.pdf"\n'
    '/tep/2,"Another",http://lawlink.nsw.gov.au/x,"au,gov,nsw,lawlink)/x"\n'
    '/tep/3,"Same domain again",http://www.acoss.org.au/other,"au,org,acoss)/other"\n'
)


@pytest.mark.parametrize(
    "line, rows, counts",
    [
        (CORONUS, [("www.coronus.com", 1999, 11, 30, "1999/11/30/www.coronus.com")],
         {"date_confirmed_twice": 1}),
        ("[01.05.02] NT [x] Something ( www.example.com )",
         [("www.example.com", 2001, 5, 2, None)], {}),
        (YEAR_OFF, [], {"dropped_year_disagreement": 1}),
        (DAY_OFF, [("www.phonefun.com", 1999, 8, 9, "1999/08/08/www.phonefun.com")],
         {"kept_day_disagreement": 1, "dropped_year_disagreement": 0}),
        ("[00.01.02] NT [x] Org ( www.example.com )",
         [("www.example.com", 2000, 1, 2, None)], {"dated_1_or_2_january": 1}),
        ('[<a href="/news">Attrition News</a>]--[<a href="stats.html">Stats</a>]', [], {"rows": 0}),
        ("[99.11.30] Li [somebody] An organisation with no site listed", [],
         {"row_without_host": 1}),
    ],
    ids=["mirror-path", "two-digit-year", "year-disagreement-dropped",
         "day-disagreement-kept", "new-year-counted", "navigation", "no-host"],
)  # fmt: skip
def test_attrition_rows_need_the_two_witnesses_to_agree_on_the_year(tmp_path, line, rows, counts):
    """The index date and the mirror path must agree on the year; a day slip is kept."""
    page = tmp_path / "1999-11.html"
    page.write_text(line + "\n")
    stats: Counter = Counter()
    assert attrition.rows_in(page, stats) == rows
    assert {key: stats[key] for key in counts} == counts


def test_attrition_reads_only_index_pages_not_the_breakouts_that_reslice_them():
    assert all(attrition.INDEX.match(name) for name in ("1999-11.html", "1998.html"))
    assert not any(attrition.INDEX.match(name) for name in ("com.html", "ytcracker.html"))


def test_mailing_lists_take_only_in_window_month_archives():
    found = sorted(maillists._MONTH_FILE.findall(MAIL_INDEX))
    assert found == ["1995-July.txt", "1999-January.txt.gz",
                     "2001-December.txt", "2004-March.txt.gz"]  # fmt: skip
    in_window = sorted(n for n in found if int(n[:4]) in maillists.YEARS)
    assert in_window == ["1999-January.txt.gz", "2001-December.txt"]


def test_a_list_gatewayed_to_usenet_is_skipped_so_one_lineage_counts_once():
    assert {"python-list", "python-announce-list"} <= maillists.SKIP_LISTS
    assert "gtk-list" not in maillists.SKIP_LISTS


def test_mailing_list_messages_split_alike_plain_or_gzipped(tmp_path):
    plain = tmp_path / "gtk-list__1999-January.txt"
    plain.write_text(MBOX, encoding="utf-8")
    packed = tmp_path / "gtk-list__1999-January.txt.gz"
    packed.write_bytes(gzip.compress(MBOX.encode()))
    assert len(maillists.read_messages(plain)) == 2
    assert maillists.read_messages(packed) == maillists.read_messages(plain)


def test_the_mail_address_pattern_reads_a_host_and_refuses_a_sentence():
    assert maillists._ADDR.findall("mail bob@widgets.example.com today") == ["widgets.example.com"]
    assert maillists._ADDR.findall("end of sentence.Next one") == []


def _udrp(*rows: tuple[str, ...]) -> str:
    heads = ("Date Commenced", "Date Decided", "Proceeding Number", "Domain Name(s)", "Case Type")
    table = [[f"<th>{h}</th>" for h in (*heads, "Status")]]
    table += [[f"<td>{c}</td>" for c in (*row, "UDRP (1)", "Name transfer(21)")] for row in rows]
    return "<table>" + "".join(f"<tr>{''.join(cells)}</tr>" for cells in table) + "</table>"


@pytest.mark.parametrize(
    "rows, want, counts",
    [
        ([("2000-01-03", "2000-02-21", "WIPO D2000-0001", "musicweb.com")],
         [{"domain": "musicweb.com", "year": 2000, "proceeding": "WIPO D2000-0001",
           "commenced": "2000-01-03", "url": f"{WIPO}2000/d2000-0001.html"}], {}),
        ([("2000-12-20", "2001-03-04", "NAF FA0092015", "buyerschoice.com")],
         [{"year": 2000, "commenced": "2000-12-20"}], {}),
        ([("2004-05-06", "2004-07-01", "WIPO D2004-0001", "later.com"),
          ("1999-12-09", "2000-01-18", "WIPO D1999-0001", "worldwrestlingfederation.com")],
         [{"domain": "worldwrestlingfederation.com"}], {"out_of_window": 1}),
        ([("2000-06-01", "-", "WIPO D2000-0500", "one.com, two.net and three.org")],
         [{"domain": "one.com"}, {"domain": "three.org"}, {"domain": "two.net"}], {}),
        ([("2000-06-01", "-", "", "orphan.com")], [], {"no_proceeding_number": 1}),
        ([("2001-02-02", "-", "WIPO D2001-0002", "www.example.co.uk")],
         [{"domain": "example.co.uk"}], {}),
        ([("2000-03-03", "-", "WIPO D2000-0300", "dup.com and dup.com again")],
         [{"domain": "dup.com"}], {}),
        ([], [], {"rows_with_a_date": 0}),
        ([("2000-05-26", "-", "WIPO D2000-0599", "teliasystems.com")],
         [{"url": f"{WIPO}2000/d2000-0599.html"}], {}),
        ([("2001-05-15", "-", "WIPO D2000-1762", "late.com")],
         [{"commenced": "2001-05-15", "proceeding": "WIPO D2000-1762", "year": 2001,
           "url": f"{WIPO}2000/d2000-1762.html"}], {}),
        ([("2000-01-11", "-", "NAF FA0092016", "example.com")], [{"url": udrp.LIST_URL}], {}),
    ],
    ids=["full-record", "year-from-commencement", "out-of-window", "several-names-in-a-cell",
         "no-proceeding-number", "registrable-not-host", "one-record-per-domain", "header-only",
         "wipo-case-url", "url-year-from-case-number", "naf-cites-the-list"],
)  # fmt: skip
def test_udrp_records_carry_an_auditable_case_and_the_commencement_year(rows, want, counts):
    """No corroboration split sits behind this source, so every record it emits is master."""
    stats: Counter = Counter()
    got = sorted(udrp.records_in(_udrp(*rows), stats), key=lambda record: record["domain"])
    assert [{k: record[k] for k in part} for record, part in zip(got, want, strict=True)] == want
    assert {key: stats[key] for key in counts} == counts


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"], ids=["plain", "bom"])
def test_pandora_titles_give_deduped_registrable_domains_bom_or_not(tmp_path, encoding):
    """`lawlink.nsw.gov.au` gives `nsw.gov.au`: the pinned suffix list has `gov.au` only."""
    path = tmp_path / "titles.csv"
    path.write_text(PANDORA, encoding=encoding)
    domains, stats = pandora.registrable_domains(path)
    assert domains == {"acoss.org.au", "nsw.gov.au"}
    assert stats == {"rows": 3, "with_url": 3, "unparsed": 0}


def test_pandora_without_a_url_column_raises_and_counts_rows_with_no_url(tmp_path):
    wrong = tmp_path / "wrong.csv"
    wrong.write_text("tep_id,name\n/tep/1,A title\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="gathered_url"):
        pandora.registrable_domains(wrong)
    gaps = tmp_path / "gaps.csv"
    gaps.write_text(PANDORA.splitlines()[0] + '\n/tep/9,"No url",,"au,org)/"\n', encoding="utf-8")
    assert pandora.registrable_domains(gaps) == (set(), {"rows": 1, "with_url": 0, "unparsed": 0})
