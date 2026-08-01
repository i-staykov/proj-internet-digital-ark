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
    body = "19980101000000 http://a.com/\n19990101000000 http://a.com/b\nrubbish\n"
    assert parse_captures(body, 1998) == [("19980101000000", "http://a.com/")]


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
    def cdx_fetch(url: str) -> tuple[int, str]:
        return cdx_status, cdx_body

    def page_fetch(url: str) -> tuple[int, bytes]:
        if url in pages:
            return 200, pages[url]
        return 0, b""

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
