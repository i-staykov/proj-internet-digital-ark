"""No em-dash and no en-dash in any tracked markdown, on either repository.

Rule 10, and the one house rule with no exception: the reviewer reads this prose through the
register and the report. Markdown only and every tracked one of them, so quoting a 1999
artifact that carries a dash means transcribing it as a hyphen rather than widening this
test. `tests/test_claude_harness.py` covers `.claude/` and the fleet holds its own pages.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# By code point, so this file does not itself carry the characters it bans.
DASHES = tuple(map(chr, (0x2014, 0x2013)))


def tracked_markdown() -> list[Path]:
    """Every tracked `.md`, so a generated or ignored page is never read."""
    listed = subprocess.run(
        ["git", "ls-files", "-z", "*.md"], cwd=ROOT, capture_output=True, check=True
    )
    return [ROOT / name for name in listed.stdout.decode().split("\0") if name]


def test_no_em_or_en_dash_in_any_tracked_markdown() -> None:
    paths = tracked_markdown()
    assert len(paths) > 20, paths
    bad = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for dash in DASHES:
            if dash in text:
                line = next(n for n, row in enumerate(text.splitlines(), 1) if dash in row)
                bad.append(f"{path.relative_to(ROOT)}:{line}: U+{ord(dash):04X}")
    assert bad == [], bad


def test_the_step_list_names_the_recipe_that_banks() -> None:
    """S9 replaced `just bank` with `just sync`, and the step list named neither.

    A step list whose steps carry no command is a paragraph, and the point of that list is
    that an unattended session can act on it without reading the runbook first.
    """
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "`just sync`" in text
    assert "just bank" not in text
