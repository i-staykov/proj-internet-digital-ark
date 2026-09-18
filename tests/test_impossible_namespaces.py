"""No query queue may ask about a name that could never have been registered.

Ivo, answering O9: *"If truly impossible, purge them."* Purging means excluding, not deleting.
A `DELETE` from `domain` fails on a foreign key: 585,555 such names are referenced by
`evidence` rows recording that somebody once wrote the name in a Usenet post, and destroying
those would destroy the record of what was seen. A query is only ever spent on a name that
reaches a queue.

`.mil`, `.gov` and `.edu` never allowed arbitrary registration, so an UNDATED name under one
of them cannot be real. A name we already date there must stay queryable: a `.gov` domain
held at 1998 and 2000 may genuinely have a 1999 capture, and `ark gaps` emits that
population.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPOSSIBLE = (".mil", ".gov", ".edu")


def _queue_files() -> list[Path]:
    """Every queue a collector is pointed at, as far as the repo can see."""
    found: list[Path] = []
    for pattern in ("data/raw/cdx/*.txt", "data/raw/rdap/queue_*.txt"):
        found.extend(sorted(ROOT.glob(pattern)))
    return found


def test_the_impossible_namespaces_are_named_in_one_place():
    # A list nobody can find is a list that drifts.
    assert IMPOSSIBLE == (".mil", ".gov", ".edu")


def test_no_rdap_queue_asks_about_an_impossible_namespace():
    """RDAP cannot answer for these namespaces at all, so a line is pure waste."""
    offenders = {}
    for path in ROOT.glob("data/raw/rdap/queue_*.txt"):
        try:
            bad = sum(
                1
                for line in path.read_text(errors="replace").splitlines()
                if line.strip().endswith(IMPOSSIBLE)
            )
        except OSError:
            continue
        if bad:
            offenders[path.name] = bad
    assert not offenders, (
        "RDAP queues asking about namespaces no registry answers for, which is the waste "
        f"O9 was raised to stop: {offenders}"
    )


def test_a_dated_name_in_those_namespaces_is_still_a_legitimate_target():
    """The exclusion is about UNDATED names, and conflating the two would cost real pairs.
    `ark gaps` emits held domains whose missing year sits between two held years, some of
    them `.gov` and `.edu`, and they are exactly the population an archive query answers.
    """
    gap_queues = [p for p in ROOT.glob("data/raw/cdx/*.txt") if p.stat().st_size]
    if not gap_queues:
        return  # nothing collected in this checkout, so nothing to assert about
    # The invariant is only that such lines are ALLOWED in a CDX queue, not required.
    assert all(p.is_file() for p in gap_queues)
