"""Tests for the English-website verification engine.

Every network path is exercised through injected fetchers, so the suite runs
offline and deterministically. The cases that matter are the ones where a wrong
answer would silently change the admitted set: a failure recorded as a verdict,
a mis-decoded page counted as undetermined, and an exact-half share admitted.
"""

import gzip
import json

import pytest

from ark.db import connect, ensure_source, init_db
from ark.language import (
    ENGLISH_THRESHOLD,
    MIN_TEXT_CHARS,
    Sample,
    answered,
    body_text,
    captures_url,
    classify_pair,
    classify_text,
    decode_page,
    ingest_language_journal,
    pair_key,
    parse_captures,
    read_targets,
    score_samples,
    write_lang_targets,
)

ENGLISH = "The quick brown fox jumps over the lazy dog near the river bank. " * 8
GERMAN = "Der schnelle braune Fuchs springt ueber den faulen Hund am Flussufer. " * 8


def _page(text: str) -> bytes:
    return f"<html><body><p>{text}</p></body></html>".encode()


# --- query construction -----------------------------------------------------


def test_captures_url_keeps_both_filters():
    """urlencode cannot express a repeated key, and dropping one silently
    widens the sample to redirects or images."""
    url = captures_url("example.com", 1998)
    assert "filter=statuscode%3A200" in url
    assert "filter=mimetype%3Atext%2Fhtml" in url
    assert "matchType=domain" in url
    assert "from=1998" in url and "to=1998" in url


def test_parse_captures_rejects_out_of_year_rows():
    body = "19980101000000 http://a.com/ 500\n19990101000000 http://a.com/b 500\nrubbish\n"
    assert parse_captures(body, 1998) == [("19980101000000", "http://a.com/", 500)]


def test_parse_captures_tolerates_a_missing_length():
    """A capture with no usable length must still be considered, sorting last
    rather than being dropped."""
    body = "19980101000000 http://a.com/ -\n19980202000000 http://a.com/b 900\n"
    assert parse_captures(body, 1998) == [
        ("19980101000000", "http://a.com/", 0),
        ("19980202000000", "http://a.com/b", 900),
    ]


def test_captures_url_asks_for_far_more_candidates_than_it_fetches():
    """The limit used to be the sample count, so a run at --samples 2 asked the
    index for two rows and reported captures_found: 2 whatever the archive held.
    Measured on adguys.com 2000: 2 seen, 33 actually available, and the pair was
    stored undetermined. One index row is bytes; a page fetch is a request."""
    from ark.language import CANDIDATE_LIMIT

    assert CANDIDATE_LIMIT >= 20
    assert f"limit={CANDIDATE_LIMIT}" in captures_url("example.com", 1998)
    assert "length" in captures_url("example.com", 1998)


# --- decoding and text extraction -------------------------------------------


def test_decode_page_recovers_non_utf8_bytes():
    """A latin-1 page decoded as UTF-8 becomes mojibake, which classifies as
    undetermined and quietly inflates the measured English share."""
    raw = "Institut fur Fremdsprachen: Uber uns. Grusse aus Munchen.".replace("u", "ü").encode(
        "latin-1"
    )
    text = decode_page(raw)
    assert "�" not in text


def test_body_text_drops_script_and_style():
    html = "<html><style>p{color:red}</style><body><p>Hello</p>"
    html += "<script>var x='Bonjour le monde';</script></body></html>"
    assert "Bonjour" not in body_text(html)
    assert "Hello" in body_text(html)


def test_body_text_separates_tag_boundaries():
    """Concatenating across tags invents n-grams the classifier reads as
    evidence of another language."""
    assert body_text("<p>Test</p><p>Hello</p>") == "Test Hello"


def test_body_text_survives_malformed_markup():
    assert "Hello" in body_text("<html><body><p>Hello<div><span></body>")


# --- classification ---------------------------------------------------------


def test_classify_text_refuses_short_text():
    assert classify_text("hello world") == (None, 0.0)
    assert len("hello world") < MIN_TEXT_CHARS


def test_classify_text_separates_languages():
    assert classify_text(ENGLISH)[0] == "en"
    assert classify_text(GERMAN)[0] == "de"


# --- the share rule ---------------------------------------------------------


def test_score_weights_by_text_length():
    """A substantial English page must outweigh a one-line notice rather than
    each capture counting once."""
    result = score_samples([Sample("a", "en", 0.99, 1000), Sample("b", "de", 0.99, 100)])
    assert result["verdict"] == "english"
    assert result["english_share"] == pytest.approx(1000 / 1100)


def test_score_exact_half_is_not_english():
    """Section 6 says 'more than 50%', so an exact half fails admission."""
    result = score_samples([Sample("a", "en", 0.99, 500), Sample("b", "de", 0.99, 500)])
    assert result["english_share"] == pytest.approx(ENGLISH_THRESHOLD)
    assert result["verdict"] == "other"


def test_score_no_usable_samples_is_undetermined():
    result = score_samples([Sample("a", None, 0.0, 10)])
    assert result["verdict"] == "undetermined"
    assert result["english_share"] is None
    assert result["samples"] == 0


def test_score_excludes_low_confidence_from_the_denominator():
    """Low-confidence captures are 'unverified' under section 6, so they must
    not count as non-English and drag an English site out of the annual file."""
    result = score_samples([Sample("a", "en", 0.99, 500), Sample("b", "de", 0.10, 5000)])
    assert result["verdict"] == "english"
    assert result["samples"] == 1


def test_score_names_the_top_other_language():
    result = score_samples([Sample("a", "de", 0.99, 900), Sample("b", "fr", 0.99, 100)])
    assert result["verdict"] == "other"
    assert result["top_other"] == "de"


# --- the pair pipeline ------------------------------------------------------


def _fetchers(cdx_body: str, pages: dict[str, bytes], cdx_status: int = 200):
    """Fake fetchers that also RECORD the CDX url, so a test can assert on the
    limit that was actually requested. Without that the fake answers whatever it
    likes regardless of the limit, and a test cannot tell the difference between
    asking for 2 candidates and asking for 40. That is exactly how the censored
    `captures_found` defect survived its own test."""

    asked: list[str] = []

    def cdx_fetch(url: str) -> tuple[int, str]:
        asked.append(url)
        return cdx_status, cdx_body

    def page_fetch(url: str) -> tuple[int, bytes]:
        if url in pages:
            return 200, pages[url]
        return 0, b""

    cdx_fetch.asked = asked  # type: ignore[attr-defined]
    return cdx_fetch, page_fetch


def test_classify_pair_reads_captures_and_verdicts_english():
    cdx = "19980101000000 http://example.com/\n"
    snap = "https://web.archive.org/web/19980101000000id_/http://example.com/"
    cdx_fetch, page_fetch = _fetchers(cdx, {snap: _page(ENGLISH)})
    record = classify_pair("example.com", 1998, cdx_fetch, page_fetch)
    assert record["status"] == 200
    assert record["verdict"] == "english"
    assert record["evidence_urls"] == [snap]
    assert record["registered_domain"] == "example.com"
    assert record["year"] == 1998
    assert record["domain"] == pair_key("example.com", 1998)


def test_classify_pair_records_the_snapshot_urls_it_read():
    """The audit trail is the whole difference from a TLD prior: a reviewer must
    be able to refetch exactly what was classified."""
    cdx = "19980101000000 http://example.com/\n19980202000000 http://example.com/b\n"
    snaps = {
        "https://web.archive.org/web/19980101000000id_/http://example.com/": _page(ENGLISH),
        "https://web.archive.org/web/19980202000000id_/http://example.com/b": _page(GERMAN),
    }
    cdx_fetch, page_fetch = _fetchers(cdx, snaps)
    record = classify_pair("example.com", 1998, cdx_fetch, page_fetch)
    assert set(record["evidence_urls"]) == set(snaps)
    assert record["samples"] == 2


def test_classify_pair_with_no_captures_is_a_settled_undetermined():
    """An empty archive for a past year does not change, so re-asking is waste;
    the pair is settled as undetermined rather than left eligible."""
    cdx_fetch, page_fetch = _fetchers("", {})
    record = classify_pair("example.com", 1998, cdx_fetch, page_fetch)
    assert record["status"] == 200
    assert record["verdict"] == "undetermined"
    assert record["captures_found"] == 0
    assert answered(record)


def test_cdx_failure_does_not_settle_the_pair():
    cdx_fetch, page_fetch = _fetchers("", {}, cdx_status=503)
    record = classify_pair("example.com", 1998, cdx_fetch, page_fetch)
    assert record["status"] == 503
    assert not answered(record)


def test_unfetchable_captures_do_not_settle_the_pair():
    """Captures exist but none could be read, so nothing was learned. Recording
    that as undetermined would permanently exclude a possibly-English domain,
    which is the failure that cost the RDAP engine 12,888 domains."""
    cdx = "19980101000000 http://example.com/\n"
    cdx_fetch, page_fetch = _fetchers(cdx, {})  # no page resolves
    record = classify_pair("example.com", 1998, cdx_fetch, page_fetch)
    assert record["fetch_failures"] == 1
    assert record["status"] == 0
    assert not answered(record)


# --- work list --------------------------------------------------------------


def test_read_targets_parses_and_skips_comments():
    lines = ["# header", "", "example.com\t1998", "other.org 2001", "broken-line"]
    assert read_targets(lines) == [("example.com", 1998), ("other.org", 2001)]


def _store():
    conn = connect(":memory:")
    init_db(conn)
    return conn


def _add_pair(conn, domain: str, year: int, evidence_type: str) -> None:
    source_id = ensure_source(conn, f"src_{evidence_type}", "timestamped")
    conn.execute(
        "INSERT OR IGNORE INTO domain (domain, tld, discovered_source) VALUES (?, ?, ?)",
        [domain, domain.split(".", 1)[1], source_id],
    )
    evidence_id = conn.execute(
        "INSERT INTO evidence (domain, source_id, evidence_year, evidence_type, evidence_value) "
        "VALUES (?, ?, ?, ?, 'v') RETURNING evidence_id",
        [domain, source_id, year, evidence_type],
    ).fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO domain_year (domain, assigned_year, evidence_id) VALUES (?, ?, ?)",
        [domain, year, evidence_id],
    )


def test_targets_exclude_baseline_pairs(tmp_path):
    """The work list is the marginal contribution. Classifying the baseline
    would cost several page fetches per pair to measure what is not ours."""
    conn = _store()
    _add_pair(conn, "new.com", 1998, "cdx_timestamp")
    _add_pair(conn, "old.com", 1998, "prior_reused")
    out = tmp_path / "targets.txt"
    stats = write_lang_targets(conn, out)
    assert stats["targets"] == 1
    assert out.read_text().strip() == "new.com\t1998"


def test_targets_exclude_pairs_already_classified(tmp_path):
    conn = _store()
    _add_pair(conn, "new.com", 1998, "cdx_timestamp")
    conn.execute(
        "INSERT INTO domain_language (domain, assigned_year, verdict) VALUES (?, ?, ?)",
        ["new.com", 1998, "english"],
    )
    assert write_lang_targets(conn, tmp_path / "t.txt")["targets"] == 0


def test_targets_put_capture_backed_pairs_first(tmp_path):
    """A registry-dated pair usually has no capture to read, so spending a
    request on it cannot change the admitted set. Capture-backed pairs must be
    worked first however the years sort: measured, 1996 additions are 0.4%
    capture-backed against 93.5% for 2000."""
    conn = _store()
    _add_pair(conn, "registry.com", 2000, "whois_creation")
    _add_pair(conn, "captured.com", 1999, "cdx_timestamp")
    out = tmp_path / "t.txt"
    stats = write_lang_targets(conn, out)
    lines = out.read_text().splitlines()
    assert lines[0].startswith("captured.com")
    assert stats["capture_backed"] == 1


def test_targets_order_years_by_volume_within_the_capture_backed_group(tmp_path):
    conn = _store()
    for year in (1999, 1998, 2000):
        _add_pair(conn, f"d{year}.com", year, "cdx_timestamp")
    out = tmp_path / "t.txt"
    write_lang_targets(conn, out)
    years = [int(line.split("\t")[1]) for line in out.read_text().splitlines()]
    assert years.index(2000) < years.index(1998) < years.index(1999)


# --- ingest -----------------------------------------------------------------


def _journal(tmp_path, records: list[dict]):
    path = tmp_path / "lang_20260801T000000Z.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record) + "\n")
    return path


def test_ingest_writes_verdicts(tmp_path):
    conn = _store()
    _add_pair(conn, "new.com", 1998, "cdx_timestamp")
    path = _journal(
        tmp_path,
        [
            {
                "domain": "new.com#1998",
                "registered_domain": "new.com",
                "year": 1998,
                "status": 200,
                "verdict": "english",
                "english_share": 0.9,
                "samples": 2,
                "top_other": None,
                "evidence_urls": ["u1", "u2"],
            }
        ],
    )
    summary = ingest_language_journal(conn, path)
    assert summary["verdicts_written"] == 1
    row = conn.execute(
        "SELECT verdict, english_share, samples, evidence_urls FROM domain_language"
    ).fetchone()
    assert row[0] == "english"
    assert row[1] == pytest.approx(0.9)
    assert row[3] == "u1 u2"


def test_ingest_skips_unanswered_records(tmp_path):
    """A failed run must not write a verdict; it wrote no answer."""
    conn = _store()
    _add_pair(conn, "new.com", 1998, "cdx_timestamp")
    path = _journal(
        tmp_path,
        [
            {
                "domain": "new.com#1998",
                "registered_domain": "new.com",
                "year": 1998,
                "status": 503,
                "verdict": "undetermined",
            }
        ],
    )
    summary = ingest_language_journal(conn, path)
    assert summary["verdicts_written"] == 0
    assert summary["unanswered"] == 1
    assert conn.execute("SELECT count(*) FROM domain_language").fetchone()[0] == 0


def test_ingest_is_idempotent_by_content_hash(tmp_path):
    conn = _store()
    _add_pair(conn, "new.com", 1998, "cdx_timestamp")
    path = _journal(
        tmp_path,
        [
            {
                "domain": "new.com#1998",
                "registered_domain": "new.com",
                "year": 1998,
                "status": 200,
                "verdict": "english",
                "english_share": 1.0,
                "samples": 1,
                "evidence_urls": ["u"],
            }
        ],
    )
    ingest_language_journal(conn, path)
    assert ingest_language_journal(conn, path)["skipped"] is True
    assert conn.execute("SELECT count(*) FROM domain_language").fetchone()[0] == 1


def test_ingest_replaces_an_earlier_verdict(tmp_path):
    """A later run may reach captures an earlier one could not, so the newer
    reading of the same pages wins. Evidence accumulates; a verdict is current."""
    conn = _store()
    _add_pair(conn, "new.com", 1998, "cdx_timestamp")
    base = {
        "domain": "new.com#1998",
        "registered_domain": "new.com",
        "year": 1998,
        "status": 200,
        "samples": 1,
        "evidence_urls": ["u"],
    }
    first = _journal(tmp_path, [{**base, "verdict": "undetermined", "english_share": None}])
    ingest_language_journal(conn, first)
    second = tmp_path / "lang_20260801T010000Z.jsonl.gz"
    with gzip.open(second, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({**base, "verdict": "english", "english_share": 0.8}) + "\n")
    ingest_language_journal(conn, second)
    rows = conn.execute("SELECT verdict FROM domain_language").fetchall()
    assert rows == [("english",)]


def test_ingest_refuses_a_changed_file(tmp_path):
    """The ledger keys on content, so a journal edited after ingest is refused
    rather than double counted."""
    conn = _store()
    _add_pair(conn, "new.com", 1998, "cdx_timestamp")
    record = {
        "domain": "new.com#1998",
        "registered_domain": "new.com",
        "year": 1998,
        "status": 200,
        "verdict": "english",
        "english_share": 1.0,
        "samples": 1,
        "evidence_urls": ["u"],
    }
    path = _journal(tmp_path, [record])
    ingest_language_journal(conn, path)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({**record, "verdict": "other"}) + "\n")
    with pytest.raises(ValueError, match="sha256 mismatch"):
        ingest_language_journal(conn, path)


def test_targets_interleave_years_within_the_capture_backed_group(tmp_path):
    """A run reaches only a fraction of the list, and section 6.1 wants the mix
    reported per year. Working one year to exhaustion first would spend the whole
    budget producing a single year's rate."""
    conn = _store()
    for year in (1998, 2000, 2001):
        for i in range(3):
            _add_pair(conn, f"d{year}x{i}.com", year, "cdx_timestamp")
    out = tmp_path / "t.txt"
    write_lang_targets(conn, out)
    years = [int(line.split("\t")[1]) for line in out.read_text().splitlines()]
    # the first three targets must cover all three years, not three of one
    assert set(years[:3]) == {1998, 2000, 2001}


# --- the section 6.1 report -------------------------------------------------


def _classify(conn, domain: str, year: int, verdict: str) -> None:
    conn.execute(
        "INSERT INTO domain_language (domain, assigned_year, verdict, english_share, samples) "
        "VALUES (?, ?, ?, ?, 1)",
        [domain, year, verdict, 1.0 if verdict == "english" else 0.0],
    )


def test_summary_counts_unclassified_apart_from_undetermined(tmp_path):
    """A pair the engine has not reached is not the same claim as one it judged
    and could not resolve. Collapsing them would overstate coverage to the
    reviewer, and section 6.1 is a reporting requirement."""
    from ark.language import language_summary

    conn = _store()
    _add_pair(conn, "seen.com", 1998, "cdx_timestamp")
    _add_pair(conn, "unseen.com", 1998, "cdx_timestamp")
    _classify(conn, "seen.com", 1998, "undetermined")
    row = next(r for r in language_summary(conn) if r["year"] == 1998)
    assert row["added_records"] == 2
    assert row["undetermined"] == 1
    assert row["unclassified"] == 1


def test_summary_excludes_the_baseline(tmp_path):
    """6.1 asks for the language profile of records this submission added, not
    of the baseline, which is Ding's to measure and ours to leave alone."""
    from ark.language import language_summary

    conn = _store()
    _add_pair(conn, "mine.com", 1998, "cdx_timestamp")
    _add_pair(conn, "theirs.com", 1998, "prior_reused")
    row = next(r for r in language_summary(conn) if r["year"] == 1998)
    assert row["added_records"] == 1


def test_summary_carries_a_total_and_a_unique_domain_rollup():
    """6.1 requires both domain-year records and cross-year unique domains."""
    from ark.language import language_summary

    conn = _store()
    for year in (1998, 1999):
        _add_pair(conn, "both.com", year, "cdx_timestamp")
        _classify(conn, "both.com", year, "english")
    rows = {r["year"]: r for r in language_summary(conn)}
    assert rows["TOTAL"]["english"] == 2  # two domain-year records
    assert rows["UNIQUE_DOMAINS"]["english"] == 1  # one domain across both


def test_english_annual_files_hold_only_english_net_new(tmp_path):
    """The admitted file must be a strict subset of the additions, carrying only
    verdicts of english. Anything else would ship a domain the standard does not
    admit, which is the one failure this cannot have."""
    from ark.language import write_partitioned_annual_files

    conn = _store()
    _add_pair(conn, "yes.com", 1998, "cdx_timestamp")
    _add_pair(conn, "no.com", 1998, "cdx_timestamp")
    _add_pair(conn, "quiet.com", 1998, "cdx_timestamp")
    _add_pair(conn, "baseline.com", 1998, "prior_reused")
    _classify(conn, "yes.com", 1998, "english")
    _classify(conn, "no.com", 1998, "other")
    _classify(conn, "quiet.com", 1998, "undetermined")
    _classify(conn, "baseline.com", 1998, "english")
    out = tmp_path / "eng"
    counts = write_partitioned_annual_files(conn, out, tmp_path / "un", tmp_path / "d.csv")
    assert counts["english_1998"] == 1
    assert (out / "1998.txt").read_text().split() == ["yes.com"]


def test_the_two_sets_partition_the_additions_exactly(tmp_path):
    """Disjoint and complete. The old shape shipped a subset inside the whole,
    so a reviewer adding the two files together double-counted every admitted
    domain."""
    from ark.language import write_partitioned_annual_files

    conn = _store()
    for name, verdict in (
        ("yes.com", "english"),
        ("no.com", "other"),
        ("quiet.com", "undetermined"),
        ("later.com", None),
    ):
        _add_pair(conn, name, 1998, "cdx_timestamp")
        if verdict:
            _classify(conn, name, 1998, verdict)
    english, unverified = tmp_path / "e", tmp_path / "u"
    counts = write_partitioned_annual_files(conn, english, unverified, tmp_path / "d.csv")

    left = set((english / "1998.txt").read_text().split())
    right = set((unverified / "1998.txt").read_text().split())
    assert left == {"yes.com"}
    assert right == {"no.com", "quiet.com", "later.com"}
    assert not (left & right), "a pair may appear on exactly one side"
    assert len(left) + len(right) == 4
    assert counts["disqualified"] == 2, "judged and rejected"
    assert counts["unchecked"] == 1, "not reached, and not a rejection"


def test_unchecked_pairs_are_never_reported_as_rejections(tmp_path):
    """The register is the per-item justification for excluding a domain. A pair
    the engine never reached has no justification and must not be in it."""
    from ark.language import write_partitioned_annual_files

    conn = _store()
    _add_pair(conn, "later.com", 1998, "cdx_timestamp")
    register = tmp_path / "d.csv"
    write_partitioned_annual_files(conn, tmp_path / "e", tmp_path / "u", register)
    assert "later.com" not in register.read_text()
    unverified_csv = (tmp_path / "u" / "1998.csv").read_text()
    assert "unchecked" in unverified_csv
    assert "no_capture_in_year" not in unverified_csv


def test_format_language_summary_renders_the_unique_row():
    """`unclassified` is None for the unique-domain roll-up, because a domain is
    not unreached in the way a pair is. It must render, not crash."""
    from ark.language import format_language_summary

    text = format_language_summary(
        [
            {
                "year": 1998,
                "added_records": 10,
                "english": 5,
                "other": 2,
                "undetermined": 1,
                "unclassified": 2,
            },
            {
                "year": "UNIQUE_DOMAINS",
                "added_records": 8,
                "english": 4,
                "other": 2,
                "undetermined": 1,
                "unclassified": None,
            },
        ]
    )
    assert "UNIQUE_DOMAINS" in text
    assert text.strip().endswith("-")


# --- placeholder pages are not websites -------------------------------------


def test_registrar_parking_page_is_not_a_website():
    """A parking page reading 'currently has no web site' is fluent English, so
    the classifier is confident and wrong. ajpca.com earned an english verdict
    at confidence 1.000 this way and entered output/netnew_english/2000.txt: a
    domain that provably had no site admitted under a rule about websites."""
    from ark.language import is_non_site_text

    park = (
        "ajpca.com currently has no web site. The domain ajpca.com does not "
        "currently have a web site. This domain is registered. Please contact "
        "your registrar for more information about setting up a web site. "
    ) * 2
    assert is_non_site_text(park)
    assert classify_text(park) == (None, 0.0)


def test_frames_notice_is_not_a_website():
    """alpinvest.com scored english 1.0 on a Netscape-frames notice while its
    other capture was 2,110 characters of Dutch."""
    from ark.language import is_non_site_text

    notice = (
        "This page is designed to be viewed by a browser which supports "
        "Netscape Frames extension. If you are seeing this message you are "
        "using a browser which does not support frames. Please upgrade. "
    )
    assert is_non_site_text(notice)
    assert classify_text(notice) == (None, 0.0)


def test_a_real_page_mentioning_construction_is_still_a_website():
    """The marker has to be the whole page, not a passing remark. A real site
    with 'under construction' in one corner carries far more text."""
    from ark.language import is_non_site_text

    real = (
        "Welcome to the Acme Widget Company of Ohio. We manufacture precision "
        "widgets for the automotive and aerospace industries and have done so "
        "since 1948. Our catalogue lists over four hundred parts, and our "
        "engineering staff can produce custom tooling to your specification. "
        "Please telephone or write for a quotation. Our new online ordering "
        "system is still under construction and will open later this year. "
    ) * 3
    assert not is_non_site_text(real)
    assert classify_text(real)[0] == "en"


def test_classification_is_case_folded():
    """py3langid's model is trained on prose, and an all-capitals page is out of
    distribution for it. Folding only ever raises confidence."""
    shout = (
        "GREAT SAVINGS ON PILLOW TOP MATTRESS SETS. WE CARRY ALL MAJOR BRANDS "
        "OF FURNITURE AND BEDDING AT DISCOUNT PRICES. VISIT OUR SHOWROOM TODAY. "
    ) * 3
    lang, confidence = classify_text(shout)
    assert lang == "en"
    assert confidence > 0.99


def test_classify_pair_fetches_the_largest_captures_first():
    """Page size is the best proxy for 'has body text' available without
    spending a fetch. Taking the first rows instead sampled whatever sorted
    first by URL key, which is how framesets came to dominate."""
    cdx = (
        "19980101000000 http://example.com/tiny 120\n"
        "19980202000000 http://example.com/big 9000\n"
        "19980303000000 http://example.com/mid 3000\n"
    )
    big = "https://web.archive.org/web/19980202000000id_/http://example.com/big"
    mid = "https://web.archive.org/web/19980303000000id_/http://example.com/mid"
    cdx_fetch, page_fetch = _fetchers(cdx, {big: _page(ENGLISH), mid: _page(ENGLISH)})
    record = classify_pair("example.com", 1998, cdx_fetch, page_fetch, samples=2)
    assert record["captures_found"] == 3
    assert set(record["evidence_urls"]) == {big, mid}


def test_the_index_limit_is_the_candidate_count_not_the_fetch_count():
    """The defect this guards: classify_pair passed `samples` as the CDX limit,
    so a run at --samples 2 asked the index for two rows and reported
    captures_found: 2 whatever the archive held. adguys.com 2000 was stored
    undetermined on 2 rows while the archive held 33 including 5 KB pages.

    The first version of this test could not catch it, because the fake fetcher
    answered the same rows regardless of the limit. It asserts on the requested
    URL now."""
    from ark.language import CANDIDATE_LIMIT

    cdx_fetch, page_fetch = _fetchers("19980101000000 http://example.com/ 500\n", {})
    classify_pair("example.com", 1998, cdx_fetch, page_fetch, samples=2)
    assert f"limit={CANDIDATE_LIMIT}" in cdx_fetch.asked[0]
    assert "limit=2" not in cdx_fetch.asked[0]


# --- "no capture" must be a measurement, never an assumption ----------------


def _two_stage_fetchers(filtered_body: str, probe_body: str, probe_status: int = 200):
    """Answer the filtered capture query and the unfiltered probe differently.

    The single-body fake cannot express the case that matters here: a year in
    which the archive holds captures that the filtered query excludes. The probe
    is the request carrying `limit=1`, which is the only one asking "does
    anything at all exist".
    """
    asked: list[str] = []

    def cdx_fetch(url: str) -> tuple[int, str]:
        asked.append(url)
        if "limit=1&" in url or url.endswith("limit=1"):
            return probe_status, probe_body
        return 200, filtered_body

    def page_fetch(url: str) -> tuple[int, bytes]:
        return 0, b""

    cdx_fetch.asked = asked  # type: ignore[attr-defined]
    return cdx_fetch, page_fetch


def test_no_capture_is_only_recorded_after_the_unfiltered_question():
    """The filtered query asks for statuscode:200 AND mimetype:text/html. A year
    holding only redirects answers it empty, and calling that "no capture in this
    year" disqualifies a domain on a question that was never asked."""
    cdx_fetch, page_fetch = _two_stage_fetchers("", "19980101000000\n")
    record = classify_pair("example.com", 1998, cdx_fetch, page_fetch)
    assert record["status"] == 200
    assert record["verdict"] == "undetermined"
    assert record["reason"] == "no_readable_html_capture"
    assert len(cdx_fetch.asked) == 2, "the unfiltered probe must actually be sent"


def test_no_capture_in_year_when_the_unfiltered_probe_is_also_empty():
    cdx_fetch, page_fetch = _two_stage_fetchers("", "")
    record = classify_pair("example.com", 1998, cdx_fetch, page_fetch)
    assert record["reason"] == "no_capture_in_year"
    assert answered(record)


def test_a_failed_probe_leaves_the_pair_unsettled():
    """If the probe itself fails we still do not know, so nothing may be
    recorded. This is the same rule the CDX failure path follows."""
    cdx_fetch, page_fetch = _two_stage_fetchers("", "", probe_status=503)
    record = classify_pair("example.com", 1998, cdx_fetch, page_fetch)
    assert record["status"] == 503
    assert not answered(record)
    assert record["reason"] is None


def test_the_probe_carries_no_filters():
    from ark.language import any_capture_url

    url = any_capture_url("example.com", 1998)
    assert "filter=" not in url
    assert "from=1998" in url and "to=1998" in url


# --- the reason vocabulary --------------------------------------------------


def test_reason_separates_no_english_from_mixed_below_the_threshold():
    """Both fail, and they fail differently. A reviewer weighing whether the 50%
    line sits in the right place needs to see how many pairs are near it."""
    only_other = score_samples([Sample("u", "de", 0.99, 1000)])
    assert only_other["verdict"] == "other"
    assert only_other["reason"] == "other_language"

    mixed = score_samples([Sample("a", "en", 0.99, 400), Sample("b", "de", 0.99, 600)])
    assert mixed["verdict"] == "other"
    assert mixed["reason"] == "mixed_below_threshold"


def test_english_verdicts_carry_no_reason():
    admitted = score_samples([Sample("u", "en", 0.99, 1000)])
    assert admitted["verdict"] == "english"
    assert admitted["reason"] is None


def test_undetermined_reasons_name_which_failure_it_was():
    from ark.language import sample_rejection

    short = score_samples([Sample("u", None, 0.0, 10, sample_rejection("hi"))])
    assert short["reason"] == "insufficient_text"

    parked = "This domain currently has no web site. " * 6
    assert sample_rejection(parked) == "non_site_text"
    assert score_samples([Sample("u", None, 0.0, 200, "non_site_text")])["reason"] == (
        "non_site_text"
    )

    unsure = score_samples([Sample("u", "en", 0.10, 900)])
    assert unsure["verdict"] == "undetermined"
    assert unsure["reason"] == "low_confidence"


def test_the_reason_survives_into_the_store(tmp_path):
    """A reason that is computed and then dropped at the database boundary is
    worth nothing: the per-item register reads from the store, not the journal."""
    conn = connect(":memory:")
    init_db(conn)
    source_id = ensure_source(conn, "seed", "timestamped")
    conn.execute(
        "INSERT INTO domain (domain, discovered_source) VALUES (?, ?)",
        ["example.com", source_id],
    )
    journal = tmp_path / "lang_test.jsonl.gz"
    with gzip.open(journal, "wt") as fh:
        fh.write(
            json.dumps(
                {
                    "domain": pair_key("example.com", 1998),
                    "registered_domain": "example.com",
                    "year": 1998,
                    "status": 200,
                    "verdict": "other",
                    "english_share": 0.4,
                    "samples": 2,
                    "top_other": "de",
                    "evidence_urls": ["https://web.archive.org/web/1998id_/http://example.com/"],
                    "reason": "mixed_below_threshold",
                }
            )
            + "\n"
        )
    ingest_language_journal(conn, journal)
    stored = conn.execute("SELECT verdict, reason FROM domain_language").fetchone()
    assert stored == ("other", "mixed_below_threshold")
