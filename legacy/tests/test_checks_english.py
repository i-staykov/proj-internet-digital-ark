"""The three English-partition invariants, retired with the standard in August 2026.

Kept for posterity and deliberately not run: `pyproject.toml` sets
`testpaths = ["tests"]`, so nothing under `legacy/` is collected. The invariants
these cover were removed from `src/ark/checks.py` in the same commit, and
`collect_checks` no longer accepts the `english_dir` and `unverified_dir`
arguments these tests pass, so they would fail on the signature alone. That is
expected. See `legacy/README.md`.
"""

def test_detects_an_english_file_admitting_an_unverified_domain(tmp_path) -> None:
    """The English annual files are a deliverable now, and the failure that
    matters is one admitting a domain the standard does not: no verdict at all,
    or a verdict for a different year. Neither is visible by inspection."""
    conn = _clean_store()
    english_dir = tmp_path / "netnew_english"
    english_dir.mkdir()
    # verified english for 1998, but shipped in the 2000 file
    conn.execute(
        "INSERT INTO domain_language (domain, assigned_year, verdict) VALUES (?, ?, ?)",
        ["sub.co.uk", 1998, "english"],
    )
    (english_dir / "2000.txt").write_text("sub.co.uk\n")
    result = _results_by_name(conn, english_dir=english_dir)[
        "english_files_hold_only_verified_english"
    ]
    assert not result["ok"]
    assert result["offending"] == 1


def test_english_check_passes_when_the_verdict_matches_the_year(tmp_path) -> None:
    conn = _clean_store()
    english_dir = tmp_path / "netnew_english"
    english_dir.mkdir()
    conn.execute(
        "INSERT INTO domain_language (domain, assigned_year, verdict) VALUES (?, ?, ?)",
        ["sub.co.uk", 2000, "english"],
    )
    (english_dir / "2000.txt").write_text("sub.co.uk\n")
    result = _results_by_name(conn, english_dir=english_dir)[
        "english_files_hold_only_verified_english"
    ]
    assert result["ok"], result


def test_english_check_skips_when_the_export_is_absent() -> None:
    """A fresh clone has no output/, and an absent export must not read as a
    satisfied invariant."""
    result = _results_by_name(_clean_store())["english_files_hold_only_verified_english"]
    assert result.get("skipped")


def test_english_check_skips_when_the_export_is_present_but_empty(tmp_path) -> None:
    """Distinct from an absent export, and it broke the gate when it first
    happened: every English annual file is empty whenever nothing has been
    verified yet, so read_csv infers no columns and the query cannot bind. An
    empty admitted set trivially satisfies an invariant about what the admitted
    set may contain, but a check that examined nothing must not read as one that
    found nothing wrong."""
    conn = _clean_store()
    english_dir = tmp_path / "netnew_english"
    english_dir.mkdir()
    for year in range(1996, 2002):
        (english_dir / f"{year}.txt").write_text("")
    result = _results_by_name(conn, english_dir=english_dir)[
        "english_files_hold_only_verified_english"
    ]
    assert result.get("skipped")
    assert result["ok"]


def test_disjointness_check_catches_a_domain_in_both_sets(tmp_path) -> None:
    """The partition is the contract with the reviewer. If a domain leaked into
    both files, adding the two shipped sets together would double-count it, and
    the report's headline would be wrong in a way prose cannot catch."""
    english = tmp_path / "english"
    unverified = tmp_path / "unverified"
    english.mkdir()
    unverified.mkdir()
    (english / "1998.txt").write_text("both.com\n")
    (unverified / "1998.txt").write_text("both.com\n")

    results = _results_by_name(_clean_store(), None, english, unverified)
    check = results["the_two_shipped_sets_are_disjoint"]
    assert not check["ok"]
    assert check["offending"] == 1


def test_same_domain_in_different_years_is_not_an_overlap(tmp_path) -> None:
    """A domain can be English in one year and unverified in another: the unit
    is the pair, not the domain, so the check must be anchored to the year."""
    english = tmp_path / "english"
    unverified = tmp_path / "unverified"
    english.mkdir()
    unverified.mkdir()
    (english / "1998.txt").write_text("site.com\n")
    (unverified / "1999.txt").write_text("site.com\n")

    results = _results_by_name(_clean_store(), None, english, unverified)
    assert results["the_two_shipped_sets_are_disjoint"]["ok"]
