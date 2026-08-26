"""Every source that dates a year must be reachable from a documented command.

`README.md` says of the justfile recipes: "the recipes are the authoritative list of what
gets ingested". On 2026-08-18 that was false, and the gap was not small. Three specs had
been run by hand and had reached **11.5% of all assignments** in the store:
`domain_creation_bulk` (2,165,506), `dartmouth_nber_captures` (227,273) and
`udrp_proceedings` (7,837). Nothing detected it, because nothing compared the two lists.

It matters for D1 of the submission standard, "the complete runnable code ... and
execution instructions used for discovery and processing". A reviewer following the
documented route would rebuild a store missing an eighth of the result and would have no
way to know which eighth.

This test compares the ingest specs the justfile names against the spec registry, in the
direction that catches the failure: a spec whose evidence type can DATE A YEAR and which
no recipe mentions. It deliberately does not read the store, so it works in a fresh clone.
"""

import re
from pathlib import Path

from ark.evidence_types import MASTER_TYPES
from ark.sources import SOURCES

ROOT = Path(__file__).resolve().parents[1]

# Specs that exist to be run against a one-off input a recipe cannot name, or that are
# invoked by a script rather than by the justfile. Each needs a reason, because an empty
# allowance list is the only version of this test worth having and every entry weakens it.
ALLOWED_UNDOCUMENTED = {
    # Written by `scripts/build_promotion_journals.py --write`, which is documented in
    # README.md under its own row and takes a `--tag` rather than a fixed path.
    "promotion",
    # Measured and REJECTED on 2026-08-01: 6,281,952 lines for 60 net-new pairs, a
    # 99.998% overlap, because it samples the same Internet Archive CDX the baseline
    # already drains. `docs/sources.md` carries the working. The parser is kept, tested
    # and wired so a future release of the family can be priced without rebuilding it,
    # and it has zero rows in the store. Putting it in the reproduction recipe would
    # tell a reviewer to ingest something this project measured and threw away.
    "nypw_firstcdx",
}


def _documented_specs() -> set[str]:
    text = (ROOT / "justfile").read_text(encoding="utf-8")
    return set(re.findall(r"ark ingest\s+([a-z0-9_]+)", text))


def test_every_master_eligible_spec_is_named_by_a_recipe() -> None:
    documented = _documented_specs()
    missing = sorted(
        key
        for key, spec in SOURCES.items()
        if spec.evidence_type in MASTER_TYPES
        and key not in documented
        and key not in ALLOWED_UNDOCUMENTED
    )
    assert not missing, (
        "these specs can date a year and no justfile recipe ingests them, so the "
        f"documented reproduction would omit them: {missing}"
    )


def test_the_three_that_were_missing_are_named_now() -> None:
    """Pinned by name, not only by the rule above, because these three are the proof."""
    documented = _documented_specs()
    for key in ("domain_creation_bulk", "dartmouth_nber_captures", "udrp_proceedings"):
        assert key in documented, f"{key} reached 11.5% of assignments undocumented once"


def test_every_documented_spec_actually_exists() -> None:
    """The mirror direction: a recipe naming a spec the registry has dropped would fail
    at run time, in the middle of a reproduction, with nothing having said so earlier."""
    unknown = sorted(k for k in _documented_specs() if k not in SOURCES)
    assert not unknown, f"the justfile ingests specs that are not in the registry: {unknown}"
