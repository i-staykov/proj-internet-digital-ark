"""Page expansion: link extraction, seed parsing, capture fetching (offline)."""

from ark.cdx import RateGovernor
from ark.expand import (
    answered,
    expand_page,
    outbound_domains,
    page_captures_url,
    read_seeds,
    snapshot_url,
)


def _no_sleep(_seconds: float) -> None:
    return None


def _gov() -> RateGovernor:
    return RateGovernor(delay=0.0, min_delay=0.0, sleep=_no_sleep)


PAGE = """
<html><body>
  <a href="http://www.example.com/index.html">absolute</a>
  <a href="http://shop.example.com/">same registered domain as the one above</a>
  <a href="/local/page.html">relative, resolves to the page's own domain</a>
  <a href="#section">fragment only</a>
  <a href="mailto:someone@nowhere.org">not a web link</a>
  <a href="https://other.co.uk/deep/path?q=1">another domain, https</a>
  <a>no href at all</a>
  <a href="http://dir.example.org/">third domain</a>
</body>
"""


def test_outbound_domains_collapses_and_excludes_the_page_itself() -> None:
    found = outbound_domains(PAGE, "http://www.host.com/dir/index.html")
    # subdomains collapse to one registered domain, order preserved, self excluded
    assert found == ["example.com", "other.co.uk", "example.org"]


def test_outbound_domains_excludes_the_page_domain_even_via_a_relative_link() -> None:
    # the relative link resolves to host.com, which must not be reported
    assert "host.com" not in outbound_domains(PAGE, "http://host.com/a/b.html")


def test_outbound_domains_survives_malformed_markup() -> None:
    broken = '<a href="http://ok.com/">unclosed <b> <a href=http://bare.net/>bare attr'
    found = outbound_domains(broken, "http://page.org/")
    assert "ok.com" in found and "bare.net" in found


def test_mailto_and_javascript_links_are_ignored() -> None:
    page = '<a href="mailto:a@b.com">m</a><a href="javascript:void(0)">j</a>'
    assert outbound_domains(page, "http://page.org/") == []


def test_read_seeds_parses_the_directory_assertion() -> None:
    seeds = read_seeds(
        [
            "http://plain.example/page.html",
            "http://curated.example/dir.html\tdirectory",
            "# a comment",
            "   ",
            "http://spaced.example/\tDIRECTORY",
        ]
    )
    assert seeds == [
        ("http://plain.example/page.html", False),
        ("http://curated.example/dir.html", True),
        ("http://spaced.example/", True),
    ]


def test_snapshot_url_asks_for_the_original_bytes() -> None:
    # the id_ modifier is what stops Wayback rewriting the hrefs
    assert snapshot_url("19980101000000", "http://x.com/") == (
        "https://web.archive.org/web/19980101000000id_/http://x.com/"
    )


def test_page_captures_url_bounds_the_window_and_collapses_years() -> None:
    url = page_captures_url("http://x.com/", 1996, 2001, limit=3)
    assert "from=1996" in url and "to=2001" in url
    assert "collapse=timestamp%3A4" in url and "limit=3" in url


def test_expand_page_returns_one_record_per_capture_year() -> None:
    def fetch(url: str) -> tuple[int, str]:
        if "cdx/search" in url:
            return 200, "19970101000000\n19990101000000\n"
        return 200, '<a href="http://found.com/">x</a>'

    records = expand_page("http://seed.org/", 1996, 2001, fetch, _gov(), curated=True)

    # a page captured in two years evidences its entries in each year separately
    assert [r["year"] for r in records] == [1997, 1999]
    assert all(r["domains"] == ["found.com"] for r in records)
    assert all(r["curated"] is True for r in records)


def test_expand_page_records_a_failed_page_fetch_without_domains() -> None:
    def fetch(url: str) -> tuple[int, str]:
        return (200, "19970101000000\n") if "cdx/search" in url else (503, "")

    records = expand_page("http://seed.org/", 1996, 2001, fetch, _gov())
    assert len(records) == 1
    assert records[0]["status"] == 503
    assert records[0]["domains"] == []
    # a failure is not an answer, so a later round retries the page
    assert answered(records[0]) is False


def test_expand_page_reports_a_page_with_no_in_window_captures() -> None:
    records = expand_page(
        "http://seed.org/", 1996, 2001, lambda _u: (200, "20080101000000\n"), _gov()
    )
    assert records[0]["timestamp"] is None
    assert records[0]["domains"] == []
    # settled: the archive answered, it simply holds nothing in window
    assert answered(records[0]) is True


def test_answered_requires_a_real_reply() -> None:
    assert answered({"status": 200}) is True
    assert answered({"status": 0}) is False
    assert answered({"status": 504}) is False
