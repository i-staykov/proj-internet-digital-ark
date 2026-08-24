"""The IEDR register parser dates a page by its own line.

A page whose own line falls outside 1996-2001 is dropped whole.
"""

from collections import Counter

from ark.sources import parse_iedr_register

PAGE = """<html><body>
<p>[ <a href="0-9-doms.html">0-9</a> | <a href="a-doms.html">A</a> ]</p>
aardvark.ie<br>
a-and-d.ie<br>
WWW.Mixed-Case.IE<br>
sub.deeper.ie<br>
domainregistry.ie<br>
<p><font size="1">This page was <b>updated automatically</b>
 at 14:51 GMT on Friday, 21 December 2001</font></p>
</body></html>
"""


def _records(tmp_path, text, name="a-doms.html"):
    path = tmp_path / name
    path.write_text(text)
    stats = Counter()
    return list(parse_iedr_register(path, stats)), stats


def test_the_page_dates_every_name_on_it(tmp_path):
    records, _ = _records(tmp_path, PAGE)
    assert {r.year for r in records} == {2001}
    assert "iedr register listing" in records[0].evidence_value


def test_names_are_reduced_to_the_registrable_domain(tmp_path):
    records, _ = _records(tmp_path, PAGE)
    names = {r.raw for r in records}
    assert "aardvark.ie" in names
    assert "a-and-d.ie" in names
    # A www- or subdomain-prefixed form is the same registration, counted once.
    assert "mixed-case.ie" in names
    assert "deeper.ie" in names
    assert len(names) == len(records)


def test_the_registrys_own_host_is_not_a_registration_it_found(tmp_path):
    records, stats = _records(tmp_path, PAGE)
    assert "domainregistry.ie" not in {r.raw for r in records}
    assert stats["registry_own_host"] >= 1


def test_a_page_dated_outside_the_window_is_dropped_whole(tmp_path):
    out = PAGE.replace("21 December 2001", "28 March 2002")
    records, stats = _records(tmp_path, out, name="l-doms.html")
    assert records == []
    assert stats["out_of_window_page"] == 1


def test_the_date_is_read_with_tags_stripped(tmp_path):
    # The footer spans a <b> in the real artifact, and a regex over raw HTML misses it.
    assert "<b>updated automatically</b>" in PAGE
    records, stats = _records(tmp_path, PAGE)
    assert records and stats["no_footer_date"] == 0


def test_a_page_with_no_date_line_yields_nothing(tmp_path):
    records, stats = _records(tmp_path, "<html><body>orphan.ie<br></body></html>")
    assert records == []
    assert stats["no_footer_date"] == 1


LISTS_PAGE = """<html><body>
<p>[ 0-9 | A | B ]</p>
oldname.ie<br>
another.ie<br>
<p>Last updated 27 Nov 1999</p>
</body></html>
"""


def test_the_earlier_lists_tree_wording_is_also_read(tmp_path):
    records, stats = _records(tmp_path, LISTS_PAGE, name="19991128191652_a-doms.html")
    assert {r.year for r in records} == {1999}
    assert {r.raw for r in records} == {"oldname.ie", "another.ie"}
    assert stats["no_footer_date"] == 0


def test_a_pending_applications_page_is_never_read_as_a_register(tmp_path):
    # stalled.html lists names nobody had registered yet.
    stalled = LISTS_PAGE.replace("oldname.ie", "notyetregistered.ie")
    records, stats = _records(tmp_path, stalled, name="19991128233948_stalled.html")
    assert records == []
    assert stats["not_a_register_page"] == 1


def test_the_registrys_own_prose_pages_are_not_registers(tmp_path):
    for name in ("19991129020519_weekly.html", "19991128213509_dom-list.html"):
        records, stats = _records(tmp_path, LISTS_PAGE, name=name)
        assert records == []
        assert stats["not_a_register_page"] == 1
