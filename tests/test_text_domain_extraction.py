"""The prose extractor and the wide one for hostname lists never invent a domain out of a longer
host or a filename; the wide one keeps every TLD that carries an English weight."""

import importlib.util
import json
from pathlib import Path

import pytest

PRICING = Path(__file__).resolve().parents[1] / "scripts/pricing"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, PRICING / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


texts, price_items = _load("probe_texts_corpus"), _load("price_items")
NARROW, WIDE = texts.domains_in, price_items.wide_domains_in


CASES = {
    "narrow-edu-tw-host": (NARROW, "see www.nctu.edu.tw for the mirror", set()),
    "narrow-edu-tw-address": (NARROW, "mail x@dept.tku.edu.tw please", set()),
    "narrow-mil-under-au-label": (NARROW, "host tuvok.au.af.mil answered", {"af.mil"}),
    "narrow-co-uk": (NARROW, "the site www.bbc.co.uk works", {"bbc.co.uk"}),
    "narrow-edu-au": (NARROW, "try www.unimelb.edu.au now", {"unimelb.edu.au"}),
    "narrow-com-au": (NARROW, "real foo.com.au host", {"foo.com.au"}),
    "narrow-two-labels": (NARROW, "plain foo.com here", {"foo.com"}),
    "narrow-sentence-period": (NARROW, "ends a sentence at foo.com.", {"foo.com"}),
    "narrow-url-path": (NARROW, "go to http://foo.org/index.html now", {"foo.org"}),
    "narrow-dotted-filename": (NARROW, "a file foo.org.html on disk", set()),
    "narrow-mil": (NARROW, "see www.army.mil today", {"army.mil"}),
    "narrow-zip-file": (NARROW, "a file archive.zip here", set()),
    "narrow-so-and-ps-files": (NARROW, "lib.so and doc.ps", set()),
    "wide-low-english-tail": (
        WIDE,
        "www.uni-koeln.de and www.sony.co.jp and baz.dk",
        {"uni-koeln.de", "sony.co.jp", "baz.dk"},
    ),
    "wide-two-labels": (WIDE, "plain foo.com here", {"foo.com"}),
    "wide-co-uk": (WIDE, "the site www.bbc.co.uk works", {"bbc.co.uk"}),
    "wide-unweighted-tld": (WIDE, "file foo.invalidtld here", set()),
    "wide-edu-tw-whole": (WIDE, "see www.nctu.edu.tw for the mirror", {"nctu.edu.tw"}),
    "wide-md-file-upper-bound": (WIDE, "open readme.md now", {"readme.md"}),
}


@pytest.mark.parametrize(("extract", "text", "found"), CASES.values(), ids=CASES.keys())
def test_the_extractors_find_exactly_these_names(extract, text, found) -> None:
    """Exactly these names: none cut out of a longer host, a filename or a sentence."""
    assert extract(text) == found


def test_an_items_own_host_field_is_a_name_whatever_its_text_says() -> None:
    """The `host` and `domain` fields are read as names; prose in `text` is not."""
    record = {"host": "0---0-animal.dk", "year": 2001, "text": "DK Zonen header 20010413"}
    assert price_items.field_names(record) == {"0---0-animal.dk"}
    assert price_items.field_names({"text": "just prose"}) == set()
    assert price_items.field_names({"domain": "www.example.co.uk"}) == {"example.co.uk"}


def test_the_ocr_file_name_comes_from_metadata_not_from_the_identifier(monkeypatch) -> None:
    """The djvu text's name is read from the item's metadata, since a scan may be named freely."""
    calls: list[str] = []
    files = [
        {"name": "Internet Magazine 031 [1997-06].pdf", "format": "Image Container PDF"},
        {"name": "Internet Magazine 031 [1997-06]_djvu.txt", "format": "DjVuTXT"},
    ]
    monkeypatch.setattr(
        texts, "fetch", lambda url: calls.append(url) or json.dumps({"files": files}).encode()
    )
    assert texts.djvu_name("internet-magazine-031-1997-06") == (
        "Internet Magazine 031 [1997-06]_djvu.txt"
    )
    assert calls == ["https://archive.org/metadata/internet-magazine-031-1997-06"]
