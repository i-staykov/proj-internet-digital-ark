"""Turn a reviewer-facing markdown report into the .docx he asks for.

**Two things must never reach the file that gets sent.** These drafts carry a status
block at the top, saying when the figures were measured and what to re-run before
sending, and a `## Notes for Ivo` section at the bottom holding the things deliberately
not being said: what could not be verified, which paragraph is optional, what he may
query. Both are for the sender. Copying the file by hand and trimming them by eye is
exactly the operation that eventually sends one of them, so it is done by program.

The cut is structural rather than clever: everything from the notes heading onward goes,
and so does everything between the title and the first horizontal rule. What is left is
the letter, which is the only part with a reader outside this repository.

`to_docx` is the pandoc step alone, so `orq.py` builds its document the same way without
the cut, which would drop everything between the title and the first rule and everything
from a notes heading on.

    uv run python scripts/round/build_report_docx.py private/interim-report-20260812.md
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Tolerant of the exact wording: what matters is that a notes section starts here.
NOTES = re.compile(r"^#{1,3}\s+notes\b.*$", re.I | re.M)
RULE = re.compile(r"^-{3,}\s*$", re.M)
# A reference document, because the reviewer asked for four pages and pandoc's default is
# 12pt with 10pt paragraph spacing and one-inch margins, which spends about a page and a
# half on air. It is that default with 10pt body, 5pt spacing and 0.75in margins, and
# nothing else changed. Found from this file, so a run from any directory is styled.
REFERENCE = Path(__file__).resolve().parents[2] / "docs/round/assets/report-reference.docx"


def sendable(markdown: str) -> str:
    """The letter alone: no status block, no notes to self."""
    cut = NOTES.search(markdown)
    if cut:
        markdown = markdown[: cut.start()]
        # A notes section is usually preceded by its own rule, which would otherwise
        # end the document on a stray line.
        markdown = re.sub(r"\n-{3,}\s*\n\s*$", "\n", markdown)

    lines = markdown.splitlines()
    title = lines[0] if lines and lines[0].startswith("# ") else ""
    body = "\n".join(lines[1:] if title else lines)
    first_rule = RULE.search(body)
    if first_rule:
        body = body[first_rule.end() :]
    return f"{title}\n{body}".strip() + "\n"


def to_docx(markdown: str, out: Path) -> None:
    """Write `markdown` to `out` as a .docx. Raises FileNotFoundError without pandoc and
    CalledProcessError when pandoc fails.

    Pandoc's own markdown reader, not gfm: only it sizes pipe-table columns from the
    separator row's dash counts, and the gfm reader gave every column of a six-column
    attribution table the same width, which is what made the .docx unreadable. `-smart`
    keeps `--` and `...` as typed instead of turning them into dashes.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
        handle.write(markdown)
        staged = Path(handle.name)
    command = ["pandoc", "--from=markdown-smart", "--to=docx", "--standalone"]
    if REFERENCE.exists():
        command.append(f"--reference-doc={REFERENCE}")
    command += ["-o", str(out), str(staged)]
    try:
        subprocess.run(command, check=True)
    finally:
        staged.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="the markdown draft")
    parser.add_argument("--out", type=Path, default=None, help="default: alongside, .docx")
    parser.add_argument(
        "--keep-markdown",
        action="store_true",
        help="also write the trimmed markdown, for reading what will be sent",
    )
    args = parser.parse_args()

    if not args.source.is_file():
        print(f"no such file: {args.source}", file=sys.stderr)
        return 1
    out = args.out or args.source.with_suffix(".docx")
    body = sendable(args.source.read_text(encoding="utf-8"))

    if args.keep_markdown:
        trimmed = args.source.with_name(args.source.stem + "-sendable.md")
        trimmed.write_text(body, encoding="utf-8")
        print(f"wrote {trimmed}")

    try:
        to_docx(body, out)
    except FileNotFoundError:
        print("pandoc is not installed: brew install pandoc", file=sys.stderr)
        return 1

    print(f"wrote {out} ({out.stat().st_size:,} bytes) from {args.source}")
    if NOTES.search(args.source.read_text(encoding="utf-8")):
        print("  the notes-to-self section was removed, as was the status block")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
