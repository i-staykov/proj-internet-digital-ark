"""Registrable-domain extraction against the vendored PSL, no network."""

import pytest

from ark.canonical import PSL_PATH, extract, to_registrable


def test_psl_snapshot_is_vendored() -> None:
    assert PSL_PATH.is_file()
    text = PSL_PATH.read_text(encoding="utf-8")
    assert "co.uk" in text


def test_multi_label_suffix() -> None:
    result = extract("news.bbc.co.uk")
    assert (result.domain, result.suffix) == ("bbc", "co.uk")


def test_plain_com() -> None:
    result = extract("www.example.com")
    assert (result.domain, result.suffix) == ("example", "com")
    assert result.subdomain == "www"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # normalization: case, scheme, port, path, trailing dot, userinfo
        ("http://WWW.Example.COM:80/page.html", "example.com"),
        ("https://news.bbc.co.uk/politics?id=1#top", "bbc.co.uk"),
        ("example.com.", "example.com"),
        ("//cdn.example.org", "example.org"),
        ("user:pass@ftp.example.org", "example.org"),
        # subdomains and hosting platforms collapse to the registered domain
        ("www.example.com", "example.com"),
        ("members.tripod.com", "tripod.com"),
        # mis-encoded seed-file lines
        ("%20agfood-alliance.ab.ca", "agfood-alliance.ab.ca"),
        # stray separator punctuation around the name is removed
        (".www.comdo-it.com", "comdo-it.com"),
        (",cp-ii.com", "cp-ii.com"),
        # a leading hyphen would alter the name itself, so it stays invalid
        ("-s-love.com", None),
        # underscores in discarded subdomains are tolerated
        ("a_ashe.howard.edu", "howard.edu"),
        # retired ccTLDs of the early web resolve via HISTORICAL_SUFFIXES
        ("beograd.yu", "beograd.yu"),
        ("adder.labis.fon.bg.ac.yu", "bg.ac.yu"),
        # garbage in, None out
        ("", None),
        ("   ", None),
        ("192.168.0.1", None),
        ("localhost", None),
        ("$b#m#e#m#b#e#r.ne.jp", None),
        ("ww[w.scoti1laxndkphhot", None),
        ("com", None),
        # a bare public suffix is not a registered domain
        ("ab.ca", None),
        # underscore in the registered label itself stays invalid
        ("ace_daikin.com.sg", None),
    ],
)
def test_to_registrable(raw: str, expected: str | None) -> None:
    assert to_registrable(raw) == expected


@pytest.mark.parametrize(
    ("raw", "reason_part"),
    [
        ("ab.ca", "bare public suffix"),
        ("192.168.0.1", "ip address"),
        ("ace_daikin.com.sg", "registered label"),
        ("chevrolet-online", "no known public suffix"),
        ("example.com", None),
    ],
)
def test_reject_reason(raw: str, reason_part: str | None) -> None:
    from ark.canonical import reject_reason

    reason = reject_reason(raw)
    if reason_part is None:
        assert reason is None
    else:
        assert reason is not None and reason_part in reason
