"""The text extractor must not invent a domain out of a longer real hostname.

`probe_texts_corpus.domains_in` is the shared extractor for every corpus of prose or OCR
this project prices or ingests: `price_items.py` imports it, so does the trade-press
collector and the RTFM FAQ splitter. It had no test until 2026-08-18, which is how the
following survived.

Its TLD whitelist carries `uk` and `au` because both are worth having, and the pattern
had no right boundary, so `www.nctu.edu.tw` matched `www.nctu.edu` and collapsed to
`nctu.edu`, and `tuvok.au.af.mil` matched `tuvok.au`. Both results are well-formed
domains, so no store invariant could see them, and the error ran in the flattering
direction twice over: the real host is lost, so the pair count falls, and the invented
TLD outweighs the real one, so the equivalent-English rises. `.edu` is 0.9717 against
`.edu.tw` at 0.1338.

Measured over both affected corpora at the whole-corpus level, the old pattern invented
534 names in the trade-press OCR and 1,442 in the RTFM FAQs, 1,934 distinct. 128 of them
reached the annual files, worth 85.2549 equivalent-English, and every one of those 128
also carries same-year evidence from another source, which is the corroboration split
doing exactly what it is for. So the register was contained and the pricing was not.
"""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "probe_texts_corpus",
    Path(__file__).resolve().parent.parent / "scripts" / "probe_texts_corpus.py",
)
texts = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(texts)


def test_a_multi_label_cctld_host_is_not_truncated_to_a_fake_edu() -> None:
    """The exact case found while pricing arXiv: nctu.edu.tw must not become nctu.edu."""
    assert "nctu.edu" not in texts.domains_in("see www.nctu.edu.tw for the mirror")


def test_an_academic_cctld_in_an_address_is_not_truncated() -> None:
    assert "tku.edu" not in texts.domains_in("mail x@dept.tku.edu.tw please")


def test_a_military_host_is_not_truncated_to_a_fake_au() -> None:
    """`.au` is 0.9904 and `.mil` is 0.9981, so this one swapped a real name for a fake
    one of almost equal weight, which is the version hardest to notice."""
    assert "tuvok.au" not in texts.domains_in("host tuvok.au.af.mil answered")


def test_the_whole_extraction_is_empty_rather_than_wrong() -> None:
    """Refusing the match is deliberate. An omission is survivable, a fabrication is not,
    and this module already trades recall on low-weight ccTLDs for exactly that reason."""
    assert texts.domains_in("see www.nctu.edu.tw only") == set()


def test_a_real_second_level_uk_host_still_extracts() -> None:
    """The fix must not cost the multi-label TLDs the whitelist exists to catch."""
    assert "bbc.co.uk" in texts.domains_in("the site www.bbc.co.uk works")


def test_a_real_second_level_au_host_still_extracts() -> None:
    assert "unimelb.edu.au" in texts.domains_in("try www.unimelb.edu.au now")
    assert "foo.com.au" in texts.domains_in("real foo.com.au host")


def test_a_bare_two_label_name_still_extracts() -> None:
    """The 2026-08 widening that found 12,788 rows in cached OCR must survive this."""
    assert "foo.com" in texts.domains_in("plain foo.com here")


def test_a_trailing_sentence_period_is_not_a_label() -> None:
    """The lookahead needs a letter after the dot, so prose punctuation still reads."""
    assert "foo.com" in texts.domains_in("ends a sentence at foo.com.")


def test_a_url_path_still_extracts_the_host() -> None:
    assert "foo.org" in texts.domains_in("go to http://foo.org/index.html now")


def test_a_dotted_filename_no_longer_reads_as_a_domain() -> None:
    """A small recall loss in the safe direction: foo.org.html is a file, not a host."""
    assert texts.domains_in("a file foo.org.html on disk") == set()


# `.mil` is 0.9981, the highest real weight in the model, and it was missing from the whitelist.
#
# Measured 2026-08-18 over both corpora this extractor feeds: 46 `.mil` names recovered, mostly
# famous (`army.mil`, `darpa.mil`, `ddn.mil`, `dtic.mil`), so it is taken for correctness rather
# than yield. Before this, `au.af.mil` extracted as the fabricated `tuvok.au` and then, after the
# morning's boundary fix, as nothing at all.
#
# The same measurement REFUSED widening any further, and that is the part worth pinning. A
# whitelist-free pattern over the same corpora finds 34,494 more hostname-shaped names worth
# 12,033.9 equivalent-English as a ceiling, and the largest single contributor is `.zip` at 3,547
# names and 2,056.2 EE, which is a file extension. So are `.so`, `.ps`, `.st` and `.in`. Only
# 21,114 of the 34,494 are undated, and an undated name scores zero under the corroboration split
# by definition, so the whole apparent gain is fabricated candidates.


def test_a_military_host_now_extracts_correctly() -> None:
    """The case that was fabricated, then dropped, and is now right."""
    assert texts.domains_in("host tuvok.au.af.mil answered") == {"af.mil"}


def test_a_plain_mil_host_extracts() -> None:
    assert "army.mil" in texts.domains_in("see www.army.mil today")


def test_a_zip_file_is_still_not_a_domain() -> None:
    """The largest single prize a whitelist-free pattern offers on prose, and it is a filename.
    `.zip` became a real TLD in 2023 and carries weight 0.5797, which is why this matters."""
    assert texts.domains_in("a file archive.zip here") == set()


def test_a_shared_object_and_a_postscript_file_are_not_domains() -> None:
    """`.so` and `.ps` are both real ccTLDs and both common extensions."""
    assert texts.domains_in("lib.so and doc.ps") == set()
