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
