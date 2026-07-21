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
        # garbage in, None out
        ("", None),
        ("   ", None),
        ("192.168.0.1", None),
        ("localhost", None),
        ("$b#m#e#m#b#e#r.ne.jp", None),
        ("ww[w.scoti1laxndkphhot", None),
        ("com", None),
    ],
)
def test_to_registrable(raw: str, expected: str | None) -> None:
    assert to_registrable(raw) == expected
