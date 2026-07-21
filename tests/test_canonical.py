"""Registrable-domain extraction against the vendored PSL, no network."""

from ark.canonical import PSL_PATH, extract


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
