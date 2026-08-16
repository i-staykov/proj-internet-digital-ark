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
    "reprobe_closed", Path(__file__).resolve().parent.parent / "scripts" / "reprobe_closed.py"
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
