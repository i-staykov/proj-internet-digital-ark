"""The last gate before tracked bytes become world-readable.

`origin` is public and every branch but `main` may now be pushed, so a secret, a machine
address or a local path in a tracked file is published the moment the push lands. One scan
covers all three, `tests/test_repo_hygiene.py` calls it, and the pre-commit hook and CI run
it as `uv run python -m ark.hygiene`.

The rules are deliberately narrow: each one matches a shape that has no legitimate reason to
sit in this repository. A hit is read in context, and then either it is a real leak, which is
fixed and never committed, or it is a fixture or a public host, which goes on the allowlist
below with a comment saying why.
"""

import ipaddress
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# A four-octet run that is not part of a longer dotted number, so a version string
# like 1.2.3.4.5 does not read as an address.
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")

# RFC 5737 reserves these three ranges for documentation and examples. A fixture that has
# to look like a host uses one, which is exactly what they are for, so the host-login rule
# skips them instead of growing an allowlist entry per fixture.
DOCUMENTATION_RANGES = ("192.0.2.", "198.51.100.", "203.0.113.")

# Globally routable addresses already in the tree, each read in context: a host a source
# note says a name resolves to, a root server or public resolver, or a test fixture. A new
# one fails until somebody reads it and adds it here, which is the point of the rule.
KNOWN_ADDRESSES = frozenset(
    {
        # fixture rows in tests/test_isc_hostnames.py and tests/test_ripe_nserver_hostnames.py
        "1.0.0.2",
        "1.125.2.7",
        "1.125.2.8",
        "1.3.3.1",
        "1.3.3.2",
        "1.3.3.3",
        "128.214.4.29",
        "1.2.3.4",
        "8.8.8.8",
        "66.199.183.26",
        "78.47.242.83",
        "130.217.250.15",
        "192.149.252.21",
        "193.166.0.0",
        "193.166.255.255",
        "198.41.0.4",
        "204.96.208.1",
        "207.36.205.194",
    }
)

# (rule name, pattern, whether the match may be printed). CI logs on a public repository
# are public too, so only what has to be read to be acted on is echoed: the address, which
# somebody has to see to decide whether it belongs on the allowlist, and the private key
# banner, which is not itself secret. A credential or a local path is named by file and
# line and nothing else.
_RULES: tuple[tuple[str, re.Pattern[str], bool], ...] = (
    ("github token", re.compile(r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"), False),
    ("anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), False),
    ("aws key", re.compile(r"AKIA[0-9A-Z]{16}"), False),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), True),
    ("slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), False),
    ("credential", re.compile(r"(?i)(?:token|password)\s*=\s*\S{16,}"), False),
    # A home directory names the machine's user. The lookbehind keeps a URL path such as
    # site.com/home/whats-new/ out of it; the same segment standing alone is still a hit.
    ("home path", re.compile(r"(?<![A-Za-z0-9._-])/(?:Users|home)/[A-Za-z0-9._-]+/"), False),
    ("ssh target", re.compile(r"\bssh\s+[A-Za-z0-9._-]+@[A-Za-z0-9.-]+"), False),
    # A login against a bare address, in ANY range. The address check below fires only on
    # globally routable addresses, and the collector host sits in private space, so a
    # shell default of that shape passed every guard and reached published history in
    # seven files (docs/security.md, 2026-09-03). The rule it broke is about that host, so
    # the class of the address is irrelevant and the shape is what must be refused.
    # No literal example here: this file is scanned too.
    ("host login", re.compile(r"[A-Za-z0-9._-]+@(?:[0-9]{1,3}\.){3}[0-9]{1,3}"), False),
)

# Every pattern above is written so that its own source line does not match it, which is
# why the separators sit outside the character classes. Keep that true when editing one.


@dataclass(frozen=True)
class Finding:
    """One rule matching once in one file."""

    path: Path
    line: int
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.detail}"


def text_of(path: Path) -> str | None:
    """The file's text, or None for a binary (git's own test: a NUL in the first 8000 bytes)."""
    data = path.read_bytes()
    if b"\0" in data[:8000]:
        return None
    return data.decode("utf-8", errors="replace")


def scan(paths: Iterable[Path]) -> list[Finding]:
    """Every rule hit in these files, binaries skipped, in file then line order."""
    findings: list[Finding] = []
    for path in paths:
        text = text_of(Path(path))
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for rule, pattern, may_print in _RULES:
                for match in pattern.finditer(line):
                    hit = match.group(0)
                    if rule == "host login" and any(r in hit for r in DOCUMENTATION_RANGES):
                        continue
                    detail = hit[:120] if may_print else f"{len(hit)} chars, not printed"
                    findings.append(Finding(Path(path), number, rule, detail))
            for hit in dict.fromkeys(IPV4.findall(line)):
                try:
                    addr = ipaddress.IPv4Address(hit)
                except ValueError:  # 300.1.2.3 is not an address
                    continue
                if addr.is_global and hit not in KNOWN_ADDRESSES:
                    findings.append(Finding(Path(path), number, "address", hit))
    return findings


def tracked_files(root: Path) -> list[Path]:
    """Tracked files worth scanning: frozen submissions keep whatever their round shipped."""
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    ).stdout
    rels = [p for p in out.decode("utf-8").split("\0") if p and (root / p).is_file()]
    return [root / rel for rel in rels if not rel.startswith("submissions/")]


def main() -> int:
    """Scan the tracked tree, print one line per finding, non-zero exit on any."""
    root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], check=True, capture_output=True, text=True
        ).stdout.strip()
    )
    files = tracked_files(root)
    findings = scan(files)
    for finding in findings:
        print(f"{finding.path.relative_to(root)}:{finding.line}: {finding.rule}: {finding.detail}")
    if findings:
        print(
            f"\n{len(findings)} finding(s). Read each in context: a real leak is fixed and never "
            "committed, and an address that is a fixture or a public host joins KNOWN_ADDRESSES "
            "in src/ark/hygiene.py with a comment saying why."
        )
        return 1
    print(f"security-scan: clean over {len(files)} tracked files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
