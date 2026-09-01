"""A host that answers is not a source that exists.

`web-caching.com`, the IRCache proxy-trace host, went from TIMEOUT to a 27,223-byte
HTTP 200 on 2026-08-15 and the re-prober reported it as a resurrected source. The body
is a consent-manager parking page. The register's own note for the sibling host says
"now serves a squatted blog", so the failure is known and the status check cannot see
it. These tests pin the content check that can.
"""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "reprobe_closed", Path(__file__).resolve().parent.parent / "scripts/harness/reprobe_closed.py"
)
reprobe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reprobe)


def test_a_consent_manager_parking_page_is_parked() -> None:
    """The exact shape that fooled the re-prober: a GDPR consent stub, no content."""
    body = b'<html><head><script>if (!"gdprAppliesGlobally" in window) { }</script>'
    assert reprobe.looks_parked(body)


def test_a_sale_page_is_parked() -> None:
    assert reprobe.looks_parked(b"<html><body>This domain is for sale. Buy this domain.</body>")


def test_a_real_directory_listing_is_not_parked() -> None:
    """The thing we are actually hunting must survive the filter."""
    body = b'<html><title>Index of /Traces/</title><a href="1998-01-15.gz">1998-01-15.gz</a>'
    assert not reprobe.looks_parked(body)


def test_detection_is_case_insensitive_and_survives_bad_bytes() -> None:
    """A truncated 2 KB read can cut a multi-byte character in half."""
    assert reprobe.looks_parked(b"\xff\xfe<HTML>SEDOParking\xc3")


def test_a_bot_interstitial_is_not_a_revival() -> None:
    """The case that exposed the gap: New Zealand's National Library answers HTTP 200 on
    two hosts and serves a 952-byte Incapsula block page on both. The register had already
    recorded that verdict; only the checker could not see it."""
    body = b"<html><body>Request unsuccessful. Incapsula incident ID: 65600015-771715</body></html>"
    assert reprobe.looks_parked(body)


def test_a_cloudflare_challenge_is_not_a_revival() -> None:
    assert reprobe.looks_parked(b"<title>Just a moment...</title>Checking your browser before")


# The third way a dead source answers 200, after parking pages and bot walls.
#
# `bl.iro.bl.uk` reported NOW ANSWERS, UNEXPECTED on 2026-08-16. Its homepage was up;
# the data tree was exactly as dead as the register said. `webarchive.org.uk` serves a
# 159-byte HTML "400 Redirect" body under HTTP 200 for every path under `/datasets/`,
# and the positive control is what makes this safe to assert rather than infer:
# `host-linkage.tsv.gz` is a file we demonstrably hold, and it returns the same stub.
# So a 200 in that tree proves nothing, and the largest closed prize in the register
# would otherwise re-open itself on every wake.


def test_html_where_a_gzip_should_be_is_a_stub() -> None:
    assert reprobe.looks_like_a_stub(
        "https://www.webarchive.org.uk/datasets/ukwa.ds.2/cdx/1996.cdx.gz", "text/html", 159
    )


def test_the_positive_control_reads_as_a_stub_too() -> None:
    """A file we are known to hold returns the same 159 bytes, which is the whole proof."""
    assert reprobe.looks_like_a_stub(
        "https://www.webarchive.org.uk/datasets/ukwa.ds.2/linkage/host-linkage.tsv.gz",
        "text/html",
        159,
    )


def test_a_real_gzip_is_not_a_stub() -> None:
    assert not reprobe.looks_like_a_stub(
        "https://example.org/1996.cdx.gz", "application/gzip", 2048
    )


def test_a_page_that_is_meant_to_be_a_page_is_not_a_stub() -> None:
    """The check must not fire on every HTML URL, or it silences real revivals."""
    assert not reprobe.looks_like_a_stub("https://bl.iro.bl.uk/", "text/html; charset=utf-8", 2048)


def test_a_large_html_body_is_not_the_stub_shape() -> None:
    """A big page at a .tsv address is something else, and worth a human look."""
    assert not reprobe.looks_like_a_stub("https://example.org/big.tsv", "text/html", 50_000)


# The fourth way a live host reads as a revival, and the only one where the host is
# working perfectly: it was never the thing that was tried.
#
# `just cycle` reported two unexpected revivals on 2026-08-18, `bbc.co.uk` and
# `ftp.funet.fi`. Both hosts are healthy and neither is a source. The verdicts name the
# first as contaminated data, three typos of it carrying two Squid error pages each, and
# the second in a claim about what it does not contain: zero Wayback captures matching
# `zone`. A status check cannot distinguish either from a dead host coming back, so the
# distinction has to be made where the targets are chosen and where the prediction is read.


def test_a_host_named_as_data_is_not_a_probe_target() -> None:
    """The JANET refutation quotes bbc.co.uk as proof, not as a host that was tried."""

    class Entry:
        name = "Era web traces and proxy logs, the whole family (2026-08-16)"
        verdict = (
            "The byte field is a MONTHLY SUM: any host requested twice carries two error "
            "pages and clears the threshold. Straight out of the file, three typos of "
            "`bbc.co.uk` each carrying exactly two error pages, all passing."
        )

    assert reprobe.targets_in(Entry()) == []


def test_a_content_absence_claim_expects_a_live_host() -> None:
    """funet has always answered. The verdict says it holds nothing, not that it is down."""
    verdict = (
        "**Academic FTP mirrors were never captured**: `wuarchive.wustl.edu`, `ftp.uu.net`, "
        "`ftp.cdrom.com` and `ftp.funet.fi` return **zero** Wayback captures matching "
        "`zone`, `domain-info` or `internic`."
    )
    predicted = reprobe.prediction_for(verdict, "ftp.funet.fi")
    assert predicted, "the host must be found in its own sentence"
    assert any(sign in predicted.lower() for sign in reprobe.EXPECTED_ALIVE)


def test_a_genuinely_dead_host_still_reads_as_unexpected() -> None:
    """The filters must not silence the one thing this tool exists to find."""
    verdict = "`data.webarchive.org.uk` does not resolve. A third distinct host tried."
    predicted = reprobe.prediction_for(verdict, "data.webarchive.org.uk")
    assert predicted
    assert not any(sign in predicted.lower() for sign in reprobe.EXPECTED_ALIVE)


def test_a_real_host_named_in_a_verdict_is_still_probed() -> None:
    """The skip set is enumerated, so an ordinary lead keeps its targets."""

    class Entry:
        name = "IRCache / NLANR proxy traces (2026-08-06)"
        verdict = "`web-caching.com` served the index and `ircache.net` is gone."

    assert reprobe.targets_in(Entry()) == [
        "https://web-caching.com/",
        "https://ircache.net/",
    ]


# The negative that proves nothing, which is the inverse defect and the more dangerous one.
#
# CLAUDE.md's rule is that a search finding nothing has either proved something or been
# pointed at the wrong place, and the two look identical. A re-probe run is exactly that
# search, and macOS makes it worse by reporting a refused route as "[Errno 50] Network is
# down": a reader seeing that beside every host concludes our network failed, and a reader
# seeing "still closed" beside every host concludes the leads are dead. Only a host that
# ANSWERED separates the two.


def test_a_run_where_nothing_answered_says_it_proves_nothing() -> None:
    results = [
        reprobe.Probe("lead", 1, "https://a/", status="DNS"),
        reprobe.Probe("lead", 1, "https://b/", status="ERROR"),
    ]
    note = " ".join(reprobe.control_note(results))
    assert "NO POSITIVE CONTROL" in note
    assert "proves NOTHING" in note


def test_one_answering_host_is_enough_of_a_control() -> None:
    results = [
        reprobe.Probe("lead", 1, "https://a/", status="DNS"),
        reprobe.Probe("lead", 1, "https://b/", status="200"),
    ]
    note = " ".join(reprobe.control_note(results))
    assert "Positive control held" in note
    assert "NO POSITIVE CONTROL" not in note


def test_a_redirect_counts_as_answering() -> None:
    """vefsafn.is answers 302, and it was one of the two controls on 2026-08-18."""
    results = [reprobe.Probe("lead", 1, "https://vefsafn.is/", status="302")]
    assert "Positive control held" in " ".join(reprobe.control_note(results))


def test_an_empty_run_makes_no_claim_either_way() -> None:
    assert reprobe.control_note([]) == []


# The fifth shape, and the one my own register rows produced within an hour of writing them.
#
# Four leads reported NOW ANSWERS on 2026-08-18 after the non-IA hunt's verdicts were
# recorded: lists.debian.org, seclists.org, marc.info and keys.openpgp.org. None had ever
# been down. In three of the four the verdict names the exact failing URL, and the prober
# had harvested the bare host root alongside it and asked a question the verdict never
# asked. Where a path is named, the path is what was tried.


def test_a_named_path_suppresses_the_bare_host_on_the_same_host() -> None:
    class Entry:
        name = "Machine-written mail headers in bulk mailing-list archives"
        verdict = (
            "`https://lists.debian.org/debian-devel/1999/debian-devel-199901.txt.gz` returns "
            "HTTP 404, 303 bytes. `seclists.org` is MHonArc-rendered HTML: "
            "`https://seclists.org/bugtraq/1999/Jan/1` is one page per message."
        )

    targets = reprobe.targets_in(Entry())
    assert "https://lists.debian.org/" not in targets
    assert "https://seclists.org/" not in targets
    assert "https://lists.debian.org/debian-devel/1999/debian-devel-199901.txt.gz" in targets


def test_a_query_string_counts_as_a_named_path() -> None:
    """marc.info's mbox export is a query, not a path, and it is what was tried."""

    class Entry:
        name = "marc.info mbox export"
        verdict = (
            "The site root is live but `https://marc.info/?l=bugtraq&m=91752236024417&q=mbox` "
            "returns HTTP 410 Gone, 18 bytes."
        )

    targets = reprobe.targets_in(Entry())
    assert "https://marc.info/" not in targets
    assert any("q=mbox" in url for url in targets)


def test_a_bare_host_survives_when_no_path_is_named() -> None:
    """The rule must not empty the rotation for the leads that only name a host."""

    class Entry:
        name = "IRCache / NLANR proxy traces"
        verdict = "`web-caching.com` served the index and `ircache.net` is gone."

    assert reprobe.targets_in(Entry()) == [
        "https://web-caching.com/",
        "https://ircache.net/",
    ]


def test_a_payload_absence_claim_expects_a_live_host() -> None:
    """keys.openpgp.org has no failing URL to name: it publishes no dump by design."""
    verdict = (
        "`keys.openpgp.org` publishes no dump by design, its FAQ stating that exact-match "
        "search exists so nobody can discover any new email addresses."
    )
    predicted = reprobe.prediction_for(verdict, "keys.openpgp.org")
    assert predicted
    assert any(sign in predicted.lower() for sign in reprobe.EXPECTED_ALIVE)
