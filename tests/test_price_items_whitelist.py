"""The prose whitelist is wrong for a list of hostnames, and it flatters in both directions.

`price_items.py` extracts through `probe_texts_corpus.domains_in`, whose TLD whitelist is
com|net|org|edu|gov|us|uk|au|ca|nz|ie|za|sg. That narrowness is correct for OCR and prose,
where a permissive pattern turns sentence punctuation into fabricated names, and wrong when
an item's text is already a clean list of hostnames.

Measured on the squidGuard blacklists, 2026-08-18: the whitelist silently dropped 2,333 of
30,916 names, almost all low-weight (.de 1,377, .dk 158, .nl 136, .nu 91). That understated
the pair count by 7.5% and raised the reported mean weight from 0.5725 to 0.6249, across the
0.6 line the acceptance bar tests. Both errors flattered, which is why the drop is now
reported rather than silent.
"""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "price_items", Path(__file__).resolve().parent.parent / "scripts/pricing/price_items.py"
)
price_items = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(price_items)


def test_the_wide_extractor_keeps_the_low_english_tail() -> None:
    """The names the whitelist drops are exactly the ones that lower a mean weight."""
    found = price_items.wide_domains_in("www.uni-koeln.de and www.sony.co.jp and baz.dk")
    assert "uni-koeln.de" in found
    assert "sony.co.jp" in found
    assert "baz.dk" in found


def test_the_wide_extractor_still_finds_whitelisted_names() -> None:
    assert "foo.com" in price_items.wide_domains_in("plain foo.com here")
    assert "bbc.co.uk" in price_items.wide_domains_in("the site www.bbc.co.uk works")


def test_the_wide_extractor_refuses_a_tld_that_carries_no_english_weight() -> None:
    """The narrowing that replaces the whitelist: a TLD the metric does not know cannot
    be scored, so admitting it would only add unweighable rows."""
    assert price_items.wide_domains_in("file foo.invalidtld here") == set()


def test_the_wide_extractor_does_not_truncate_a_multi_label_cctld() -> None:
    """The same fabrication that the narrow pattern was fixed for this morning."""
    found = price_items.wide_domains_in("see www.nctu.edu.tw for the mirror")
    assert "nctu.edu" not in found
    assert "nctu.edu.tw" in found


def test_a_filename_with_a_real_tld_suffix_is_the_known_upper_bound() -> None:
    """`.md`, `.py` and `.sh` are real TLDs as well as file extensions, so the wide
    pattern over prose overcounts. The report says so rather than pretending otherwise:
    this test pins the behaviour so the caveat cannot quietly stop being true."""
    assert price_items.wide_domains_in("open readme.md now") == {"readme.md"}


def test_an_items_own_host_field_is_a_name_whatever_its_text_says() -> None:
    """2026-09-15: 358,529 dated .dk names priced at 0 EE because the text held only the
    stamp and the name sat in `host`, which nothing read."""
    record = {"host": "0---0-animal.dk", "year": 2001, "text": "DK Zonen header 20010413"}
    assert price_items.field_names(record) == {"0---0-animal.dk"}
    assert price_items.field_names({"text": "just prose"}) == set()
    assert price_items.field_names({"domain": "www.example.co.uk"}) == {"example.co.uk"}
