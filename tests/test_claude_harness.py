"""The skills, agents, rules and output style the harness loads, kept as pointers.

A file here that restates a `docs/` page is a second copy, and the second copy is the one
that goes stale. Two properties: each is SHORT, the 40-line ceiling being the enforcement,
and every `docs/` page it names resolves.

The fleet runs `claude -p` in a clone of this branch and reads this directory unattended, so
`ark.hygiene`, the pre-commit hook's own scan, refuses a machine address, an account name or
a path outside the repository. `settings.local.json`, the lock file and the worktrees are
machine-local and untracked, so they stay outside it.
"""

import re
from pathlib import Path

import pytest

from ark.hygiene import scan

ROOT = Path(__file__).resolve().parents[1]
CLAUDE = ROOT / ".claude"
SKILLS = CLAUDE / "skills"
RULES = CLAUDE / "rules"
AGENTS = CLAUDE / "agents"
STYLES = CLAUDE / "output-styles"
WORKFLOWS = CLAUDE / "workflows"

MAX_LINES = 40

# Repo-relative docs references, in prose or in a markdown link: docs/lore/laws.md,
# docs/brief/ding/project-brief.md, docs/registers/hypotheses.tsv.
DOCS_REF = re.compile(r"docs/[A-Za-z0-9_./-]+\.(?:md|tsv|txt|docx)")

# A generated page is git-ignored and absent from a fresh clone, so its .gitignore line is what
# proves the reference is live. docs/ROUND.md is the one that matters.
IGNORED = {
    line.strip()
    for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.startswith("#")
}


def pointer_files() -> list[Path]:
    """Every file under skills/ and rules/, which are the two pointer surfaces."""
    return sorted(path for path in [*SKILLS.rglob("*"), *RULES.rglob("*")] if path.is_file())


def harness_files() -> list[Path]:
    """The tracked half of `.claude/`: what a fleet clone reads."""
    trees = [p for tree in (SKILLS, RULES, AGENTS, STYLES, WORKFLOWS) for p in tree.rglob("*")]
    return sorted([p for p in trees if p.is_file()] + [CLAUDE / "settings.json"])


def frontmatter(path: Path) -> dict[str, str | list[str]]:
    """The leading `---` block, flat keys and dash lists only. No YAML dependency."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = next((n for n, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    assert end is not None, f"{path}: unterminated frontmatter"
    fields: dict[str, str | list[str]] = {}
    key = ""
    for line in lines[1:end]:
        if line.lstrip().startswith("- ") and key:
            fields.setdefault(key, [])
            value = fields[key]
            if isinstance(value, list):
                value.append(line.lstrip()[2:].strip())
        elif ":" in line:
            key, _, rest = line.partition(":")
            key = key.strip()
            if rest.strip():
                fields[key] = rest.strip()
    return fields


@pytest.mark.parametrize("path", pointer_files(), ids=lambda p: p.relative_to(CLAUDE).as_posix())
def test_pointer_files_stay_short(path: Path) -> None:
    """Under 40 lines, so a page's method cannot be copied into one."""
    count = len(path.read_text(encoding="utf-8").splitlines())
    assert count < MAX_LINES, f"{path.relative_to(ROOT)} is {count} lines, ceiling {MAX_LINES}"


@pytest.mark.parametrize("path", pointer_files(), ids=lambda p: p.relative_to(CLAUDE).as_posix())
def test_every_docs_reference_resolves(path: Path) -> None:
    """Each `docs/` page a pointer names exists, or is git-ignored because it is generated."""
    text = path.read_text(encoding="utf-8")
    assert DOCS_REF.search(text), f"{path.relative_to(ROOT)} names no docs page, so it is prose"
    for ref in sorted(set(DOCS_REF.findall(text))):
        assert (ROOT / ref).exists() or ref in IGNORED, f"{path.relative_to(ROOT)} names {ref}"


def test_skills_are_named_directories_that_say_when_to_use_them() -> None:
    """One directory per skill holding SKILL.md, its `name` matching the directory."""
    skills = sorted(p for p in SKILLS.iterdir() if p.is_dir())
    assert skills
    for skill in skills:
        fields = frontmatter(skill / "SKILL.md")
        assert fields.get("name") == skill.name, skill
        assert "Use " in str(fields.get("description", "")), f"{skill}: say when to use it"
    assert not [p for p in SKILLS.iterdir() if p.is_file()], "a skill is a directory, not a file"


def test_rules_are_path_scoped() -> None:
    """A rule with no `paths` is always in context, and always-on content is CLAUDE.md's job."""
    rules = sorted(RULES.glob("*.md"))
    assert rules
    for rule in rules:
        paths = frontmatter(rule).get("paths")
        assert isinstance(paths, list) and paths, f"{rule.relative_to(ROOT)}: needs `paths`"


def test_at_most_three_agents_each_saying_when_to_use_it() -> None:
    """The roster stays small enough to hold in mind, and each entry earns its place."""
    agents = sorted(AGENTS.glob("*.md"))
    assert 0 < len(agents) <= 3, [p.name for p in agents]
    for agent in agents:
        fields = frontmatter(agent)
        assert fields.get("name") == agent.stem, agent
        assert "Use " in str(fields.get("description", "")), f"{agent}: say when to use it"


def test_the_output_style_declares_itself() -> None:
    """The laptop chat contract is tracked; only switching it on is machine-local."""
    fields = frontmatter(STYLES / "ark.md")
    assert fields.get("name"), fields
    assert fields.get("description"), fields


def test_nothing_here_names_a_machine_an_account_or_an_outside_path() -> None:
    """The fleet reads these files unattended and `origin` is public."""
    files = harness_files()
    assert len(files) > 10, files
    findings = scan(files)
    assert findings == [], [str(finding) for finding in findings]
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        assert "~/" not in text, f"{path.relative_to(ROOT)}: a home path is machine-local"
        # by code point, so this file does not itself carry the characters it bans
        for dash in map(chr, (0x2014, 0x2013)):
            assert dash not in text, f"{path.relative_to(ROOT)}: no em-dashes or en-dashes"
