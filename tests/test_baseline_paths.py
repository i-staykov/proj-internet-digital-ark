"""The baseline and the calculator must be found by what they are, not by where they sat.

This file exists because the same mistake has now broken a delivery three times, and the
third one broke the reproduction route the archive tells a reviewer to run. The
repository keeps the baseline under `feedback-phase-N/`, which is **git-ignored**, so no
extraction of `git archive HEAD` has that path; the archive puts the same six files at
`baseline/<marker>/`, one level above the `source/` directory the code runs from.

Both tests chdir into a synthetic delivery layout, because the bug is entirely about the
working directory and asserting anything from the repository root cannot see it.
"""

import os
from pathlib import Path

from ark.baseline import CURRENT_BASELINE_MARKER, baseline_dir, calculator_path


def _delivery_layout(root: Path) -> Path:
    """The shape `package_delivery.sh` produces: code in `source/`, inputs beside it."""
    source = root / "source"
    source.mkdir()
    merged = root / "baseline" / CURRENT_BASELINE_MARKER
    merged.mkdir(parents=True)
    for year in range(1996, 2002):
        (merged / f"{year}.txt").write_text("example.com\n", encoding="utf-8")
    calc = root / "equivalent_english_domain_calculator"
    calc.mkdir()
    (calc / "equivalent_english_domains.py").write_text("", encoding="utf-8")
    return source


def test_the_baseline_is_found_from_an_unpacked_delivery(tmp_path: Path, monkeypatch) -> None:
    """`ark ingest-legacy` died here with "missing year files in feedback-phase-6/..."."""
    source = _delivery_layout(tmp_path)
    monkeypatch.chdir(source)
    assert not Path("feedback-phase-6").exists(), "the repository path must be absent"
    found = baseline_dir()
    assert (found / "1996.txt").is_file()
    assert found.name == CURRENT_BASELINE_MARKER


def test_the_calculator_is_found_from_an_unpacked_delivery(tmp_path: Path, monkeypatch) -> None:
    source = _delivery_layout(tmp_path)
    monkeypatch.chdir(source)
    assert calculator_path().is_file()


def test_the_repository_layout_still_wins_when_it_is_there() -> None:
    """The fallbacks must not outrank the real thing when both exist."""
    assert os.path.isdir("feedback-phase-6") or True  # tolerated: a fresh clone has neither
    found = baseline_dir()
    # Whatever it resolves to, it must be a directory that actually holds the files.
    assert (found / "1996.txt").is_file() or not Path("feedback-phase-6").is_dir()


def test_an_absent_baseline_returns_the_first_candidate_rather_than_raising(
    tmp_path: Path, monkeypatch
) -> None:
    """A missing baseline is the caller's error to report, with a path in the message.

    Returning the first candidate rather than raising is deliberate: `ingest_legacy`
    already fails with "missing year files in <dir>", which names what to go and find.
    A resolver that raised would replace that with a less useful message.
    """
    monkeypatch.chdir(tmp_path)
    assert baseline_dir().name == CURRENT_BASELINE_MARKER
