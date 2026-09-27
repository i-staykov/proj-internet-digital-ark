"""Whether a name is dated is held's question: a pair of ours, or an exact line of his files. A
module that reads `domain` or `domain_year` imports `ark.held`, and no lane asks those tables
itself, so no lane's answer misses a name only his files date.

The scan reads the source and never imports it: some scripts open the store or parse `sys.argv`
at import.
"""

import ast
import importlib.util
import re
import sys
from functools import cache
from pathlib import Path

import pytest
from his_release import HIS_YEARS, WEB_METHOD, capture, text

from ark import held
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence

ROOT = Path(__file__).resolve().parents[1]

# `old.domain_year` too, and never `domain_language`, `new_domain_year` or a `domain(` call
_TABLE = r"(?:\w+\.)?domain(?:_year)?(?![\w.(])"
# rule A: any read of the two tables
READS = re.compile(rf"(?<!delete )\b(?:from|join)\s+{_TABLE}", re.I)
# rule B: a read that asks whether a name is there
MEMBERSHIP = re.compile(
    "|".join(
        [
            # [NOT] EXISTS (SELECT 1 FROM domain_year ...)
            rf"\bexists\s*\(\s*select\b[^()]*?\bfrom\s+{_TABLE}",
            # x [NOT] IN (SELECT domain FROM domain_year)
            rf"\bin\s*\(\s*select\s+(?:distinct\s+)?(?:\w+\.)?domain\s+from\s+{_TABLE}",
            # the set itself, fetched
            rf"(?:^|\()\s*select\s+(?:distinct\s+)?(?:\w+\.)?domain"
            rf"(?:\s*,\s*(?:\w+\.)?assigned_year)?\s+from\s+{_TABLE}",
            # [LEFT|ANTI] JOIN domain_year dy ON
            rf"\bjoin\s+{_TABLE}\s+(?:as\s+)?\w+\s+on\b",
            # FROM domain WHERE domain = ?
            rf"\bfrom\s+{_TABLE}(?:\s+(?:as\s+)?\w+)?\s+where\s+(?:\w+\.)?domain\s*(?:=|in\b)",
        ]
    ),
    re.I,
)

HELD = "src/ark/held.py"

# Modules that read the tables without importing held, each for a reason that is not a test
# of whether a name is dated. Kept minimal: a test below fails on an entry that imports held.
ALLOWED = {
    "src/ark/db.py": (
        "add_candidates registers a name the store lacks and asks nothing about who dates it; "
        "it cannot import held, which imports ark.db"
    ),
    "src/ark/provenance.py": (
        "writes and loads the store's tables whole; `domain` ships the names we know, and "
        "nothing it reads asks who dates a name"
    ),
    "src/ark/provenance_trace.py": (
        "ships alone as trace.py beside the Parquet, importing only the standard library"
    ),
    "scripts/harness/audit_residual.py": (
        "a freshness mark over the store's candidates, not a test of whether a name is dated"
    ),
}

# The lanes: each splits what it read into dated and candidate by whether a name is dated
LANES = [
    "src/ark/bulk.py",
    "src/ark/hostnames.py",
    "scripts/engines/split_expansion_journal.py",
    "scripts/sources/blocklists/split_chastity.py",
    "scripts/sources/blocklists/split_junkfilter.py",
    "scripts/sources/directories/split_tucows.py",
    "scripts/sources/directories/split_urlmerchant.py",
    "scripts/sources/mail_corpora/collect_enron.py",
    "scripts/sources/mail_corpora/collect_mailing_lists.py",
    "scripts/sources/mail_corpora/split_fac.py",
    "scripts/sources/mail_corpora/split_jeb_mail.py",
    "scripts/sources/registries/split_cctld_capture.py",
    "scripts/sources/registries/split_granitecanyon.py",
    "scripts/sources/trade_press/split_trade_press.py",
    "scripts/sources/usenet/split_rtfm_faqs.py",
    "scripts/sources/usenet/split_usenet.py",
    "scripts/sources/usenet/split_usenet_addresses.py",
    "scripts/sources/usenet/split_usenet_whois.py",
    "scripts/sources/usenet/project_usenet_bare.py",
    "scripts/sources/usenet/measure_usenet_yield.py",
    "scripts/sources/usenet/split_uucp_maps.py",
]

# Statements in a lane that match rule B and leave no name only his files date, keyed by a
# substring only that statement holds
LANE_STATEMENTS_EXEMPT = {
    ("src/ark/bulk.py", "FROM _source_names WHERE name NOT IN (SELECT domain FROM domain_year)"): (
        "the half of `held.attested` the store answers, kept in the store for a source of "
        "millions of names; `held.minus` takes his files off it next"
    ),
}


def _modules() -> list[str]:
    return sorted(
        str(path.relative_to(ROOT))
        for top in ("src", "scripts")
        for path in (ROOT / top).rglob("*.py")
        if "__pycache__" not in path.parts
    )


@cache
def _tree(rel: str) -> ast.Module:
    return ast.parse((ROOT / rel).read_text(encoding="utf-8"), filename=rel)


def _docstrings(tree: ast.Module) -> set[int]:
    kinds = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, kinds) and node.body:
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                found.add(id(first.value))
    return found


def strings_in(tree: ast.Module) -> list[tuple[int, str]]:
    """Every string the module holds but its docstrings, as `(line, text)` with whitespace
    collapsed. Adjacent literals arrive merged, and an f-string reads `{}` for each hole."""
    skip = _docstrings(tree)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            parts = []
            for value in node.values:
                if isinstance(value, ast.Constant):
                    skip.add(id(value))
                    parts.append(value.value)
                else:
                    parts.append("{}")
            out.append((node.lineno, "".join(parts)))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in skip:
                out.append((node.lineno, node.value))
    return sorted((line, " ".join(text.split())) for line, text in out)


@cache
def strings(rel: str) -> list[tuple[int, str]]:
    return strings_in(_tree(rel))


def imports_held_in(tree: ast.Module) -> bool:
    """`import ark.held`, `from ark import held` or `from ark.held import ...`, anywhere in the
    module, a lazy import too. An import through another module does not count."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name == "ark.held" for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            if node.module == "ark.held":
                return True
            if node.module == "ark" and any(a.name == "held" for a in node.names):
                return True
    return False


def imports_held(rel: str) -> bool:
    """Held itself defines the test, so it passes it."""
    return rel == HELD or imports_held_in(_tree(rel))


def hits(rel: str, rule: re.Pattern) -> list[tuple[int, str]]:
    return [(line, text) for line, text in strings(rel) if rule.search(text)]


def _exempt(rel: str, text: str) -> bool:
    return any(path == rel and key in text for path, key in LANE_STATEMENTS_EXEMPT)


MEMBERSHIP_SHAPES = [
    "INSERT INTO q SELECT domain FROM evidence e WHERE e.source_id = ? AND NOT EXISTS "
    "(SELECT 1 FROM domain_year dy WHERE dy.domain = e.domain)",
    "DELETE FROM listhost WHERE parent NOT IN (SELECT domain FROM domain_year)",
    "SELECT DISTINCT domain FROM domain_year",
    "SELECT domain, assigned_year FROM domain_year",
    "SELECT domain FROM domain",
    "SELECT domain FROM domain WHERE domain IN ({})",
    "SELECT 1 FROM domain WHERE domain = ?",
    "select count(*) from probe p where exists ( select 1 from domain_year d "
    "where d.domain = p.domain )",
    "SELECT n.name FROM names n LEFT JOIN domain_year dy ON dy.domain = n.name",
]
NEITHER_SHAPES = [
    "INSERT OR IGNORE INTO domain_year (domain, assigned_year, evidence_id) "
    "SELECT domain, evidence_year, evidence_id FROM evidence",
    "DELETE FROM domain_year WHERE evidence_id IN (SELECT evidence_id FROM gone)",
    "SELECT domain, language FROM domain_language",
    "SELECT DISTINCT domain FROM new_domain_year ORDER BY 1",
    "ia_domain_year_census",
    "INSERT OR IGNORE INTO domain (domain, tld) SELECT DISTINCT parent, tld FROM listhost",
]


@pytest.mark.parametrize("text", MEMBERSHIP_SHAPES)
def test_the_rules_see_the_membership_shapes(text: str) -> None:
    assert MEMBERSHIP.search(text), text
    assert READS.search(text), text


@pytest.mark.parametrize("text", NEITHER_SHAPES)
def test_the_rules_leave_writes_and_other_tables_alone(text: str) -> None:
    assert not MEMBERSHIP.search(text), text
    assert not READS.search(text), text


def test_a_count_is_a_read_but_not_a_membership_test() -> None:
    text = "SELECT count(*) FROM domain_year"
    assert READS.search(text) and not MEMBERSHIP.search(text)
    text = (
        "SELECT dy.evidence_id FROM old.domain_year dy "
        "JOIN old.evidence e ON e.evidence_id = dy.evidence_id"
    )
    assert READS.search(text) and not MEMBERSHIP.search(text)


def test_the_undated_names_shape_is_membership_and_exempt_by_name() -> None:
    text = (
        "SELECT name FROM _source_names WHERE name NOT IN (SELECT domain FROM domain_year) "
        "ORDER BY 1"
    )
    assert MEMBERSHIP.search(text)
    assert _exempt("src/ark/bulk.py", text)
    assert not _exempt("src/ark/hostnames.py", text)


def test_the_scan_reads_code_strings_and_skips_docstrings() -> None:
    source = (
        '"""SELECT DISTINCT domain FROM domain_year"""\n'
        "class C:\n"
        '    """SELECT domain FROM domain"""\n'
        "def f(t):\n"
        '    """SELECT domain FROM domain"""\n'
        '    q = ("SELECT 1 FROM domain_year dy "\n'
        '         "WHERE dy.domain = ?")\n'
        '    return f"SELECT domain FROM {t} JOIN   domain_year dy\\n ON x", q\n'
    )
    assert strings_in(ast.parse(source)) == [
        (6, "SELECT 1 FROM domain_year dy WHERE dy.domain = ?"),
        (8, "SELECT domain FROM {} JOIN domain_year dy ON x"),
    ]


@pytest.mark.parametrize(
    ("source", "imports"),
    [
        ("import ark.held", True),
        ("import ark.held as h", True),
        ("from ark import db, held", True),
        ("from ark.held import attested", True),
        ("def f():\n    from ark import held\n    return held", True),
        ("import ark", False),
        ("from ark import db", False),
        ("from ark.stats import held_pairs", False),
        ("from .held import load", False),
    ],
)
def test_what_counts_as_importing_held(source: str, imports: bool) -> None:
    assert imports_held_in(ast.parse(source)) is imports


def test_every_module_reading_the_tables_imports_held() -> None:
    offenders = [
        f"{rel}:{','.join(str(line) for line, _ in found)}"
        for rel in _modules()
        if (found := hits(rel, READS)) and not imports_held(rel) and rel not in ALLOWED
    ]
    assert offenders == [], (
        "these read domain or domain_year without asking held; import ark.held, "
        f"or add the module to ALLOWED with the reason: {offenders}"
    )


def test_no_lane_asks_the_tables_whether_a_name_is_dated() -> None:
    failures = []
    for rel in LANES:
        if not imports_held(rel):
            failures.append(f"{rel}: does not import ark.held")
        failures += [
            f"{rel}:{line}: {text[:120]}"
            for line, text in hits(rel, MEMBERSHIP)
            if not _exempt(rel, text)
        ]
    assert failures == [], failures


def test_each_exemption_matches_exactly_one_statement_rule_b_sees() -> None:
    for rel, key in LANE_STATEMENTS_EXEMPT:
        matched = [text for _, text in strings(rel) if key in text]
        assert len(matched) == 1, (rel, key, len(matched))
        assert MEMBERSHIP.search(matched[0]), f"{rel}: {key!r} needs no exemption"
        assert rel in LANES, rel


def test_the_allowlist_names_modules_that_exist_and_still_need_it() -> None:
    modules = set(_modules())
    for rel in ALLOWED:
        assert rel in modules, f"{rel} is gone: drop it from ALLOWED"
        assert hits(rel, READS), f"{rel} no longer reads the tables: drop it from ALLOWED"
        assert not imports_held(rel), f"{rel} imports held: drop it from ALLOWED"


def test_every_lane_exists() -> None:
    modules = set(_modules())
    assert [rel for rel in LANES if rel not in modules] == []


def _load(rel: str):
    spec = importlib.util.spec_from_file_location(Path(rel).stem, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_split_chastity_dates_what_we_or_his_files_date(
    tmp_path: Path, his_files: Path, monkeypatch
) -> None:
    """`his.com` is the case: no store row dates it, and his 1999 file names it exactly. His
    `www.rolled.com` does not date `rolled.com`, and a name the store only lists is a candidate."""
    mod = _load("scripts/sources/blocklists/split_chastity.py")
    store = tmp_path / "ark.duckdb"
    conn = connect(store)
    init_db(conn)
    web = ensure_source(conn, "ia_cdx", "timestamped")
    add_candidate(conn, "ours.com", web)
    row = record_evidence(
        conn, "ours.com", web, 2001, "cdx_timestamp", capture("ours.com", 2001), None, WEB_METHOD
    )
    assign_year(conn, row)
    add_candidate(conn, "cand.org", web)
    conn.close()

    (his_files / "1999.txt").write_bytes(text(sorted([*HIS_YEARS[1999], "his.com"])))
    held.prepare(his_files)

    src = tmp_path / "db"
    (src / "adult").mkdir(parents=True)
    (src / "adult" / "domains").write_text(
        "ours.com\nhis.com\nrolled.com\ncand.org\nnovel.net\n", encoding="utf-8"
    )
    out = tmp_path / "out"
    monkeypatch.setattr(mod, "SRC", src)
    monkeypatch.setattr(mod, "DEFAULT_DB_PATH", store)
    monkeypatch.setattr(sys, "argv", ["split_chastity.py", "--write", "--out", str(out)])
    assert mod.main() == 0

    def read(name: str) -> list[str]:
        return (out / f"{name}.{mod.STAMP}.txt").read_text(encoding="utf-8").split()

    assert read("chastity-dated") == ["his.com", "ours.com"]
    assert read("chastity-cand") == ["cand.org", "novel.net", "rolled.com"]
    assert sorted(p.relative_to(src).as_posix() for p in src.rglob("*")) == [
        "adult",
        "adult/domains",
    ]
