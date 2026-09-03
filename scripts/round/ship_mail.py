"""The submission mail draft: the filled figures, the open questions, the cumulative record.

Three parts and no fourth. The FIGURES are not computed here: `fill_report.py` fills
`private/email-draft.md` from the store, and this appends to that body rather than keeping a
second copy of a number that would then drift from the report. The REMINDERS come from
`docs/questions.md`, because a question he never answered is only asked again if a program puts
it in front of whoever sends the mail; the row's `remind-on` decides when, and a remind-on that
names an event rather than a date is due at the next mail, since a ship IS that event. The
CUMULATIVE record is read from the `awarded p_i` and `S_i quoted` columns of `docs/rounds.md`
by column name, so the numbers are the ones he quoted and not ours.

Without `--write` the whole draft goes to stdout and nothing is written, which is what a ship
rehearsal runs: `just ship draft`.

    uv run python scripts/round/ship_mail.py --write --archive output/<stage>
"""

import argparse
import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

QUESTIONS = Path("docs/questions.md")
ROUNDS = Path("docs/rounds.md")
BODY = Path("private/email-draft.md")
OUT_DIR = Path("private/emails/drafts")

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def rows(text: str, first_column: str) -> list[dict[str, str]]:
    """Every data row of the first table whose leftmost column has that name.

    Keyed by lowercased column name rather than by position: the pages gain columns, and a
    reader counting cells reads the wrong one the day somebody inserts a column.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("|") or cells(line)[:1] != [first_column]:
            continue
        columns = [c.lower() for c in cells(line)]
        out = []
        for row in lines[i + 2 :]:
            if not row.startswith("|"):
                break
            values = cells(row)
            out.append({c: (values[j] if j < len(values) else "") for j, c in enumerate(columns)})
        return out
    return []


def number(text: str) -> Decimal | None:
    """The cell as a number, or None for `n/a`, `not quoted` and other prose."""
    try:
        return Decimal(text.replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        return None


def is_due(remind: str, today: date) -> bool:
    """A dated remind-on is due when the date has passed; an event-named one is due now."""
    match = ISO_DATE.search(remind)
    if match:
        return date.fromisoformat(match.group()) <= today
    return True


def reminders(text: str, today: date) -> list[str]:
    """One line per question still open and due, in the order the page lists them."""
    out = []
    for row in rows(text, "asked-on"):
        if not row.get("status", "").lower().startswith("open"):
            continue
        if not is_due(row.get("remind-on", ""), today):
            continue
        asked = row.get("asked-on", "")
        mark = " [DRAFT: approve the wording or delete the row]" if asked == "draft" else ""
        out.append(f"- (asked {asked}, remind: {row.get('remind-on', '')}){mark} {row['question']}")
    return out


def cumulative(text: str) -> list[str]:
    """His accepted record: the percentages he awarded, and the scores he has quoted."""
    table = rows(text, "round")
    awarded = [(r["round"], number(r.get("awarded p_i", ""))) for r in table]
    awarded = [(label, value) for label, value in awarded if value is not None]
    quoted = [(r["round"], number(r.get("s_i quoted", ""))) for r in table]
    quoted = [(label, value) for label, value in quoted if value is not None]
    if not awarded:
        return ["_No scored round in docs/rounds.md._"]
    total = sum(value for _, value in awarded)
    labels = ", ".join(label for label, _ in awarded)
    out = [
        f"- Awarded across {len(awarded)} scored rounds ({labels}): {total}% in total.",
    ]
    if any(label == "1" for label, _ in awarded):
        out.append(
            "  Round 1's figure is a percentage of RECORDS, not of equivalent-English, so the "
            "total is a sum of his awards and not one ratio."
        )
    if quoted:
        scores = " + ".join(str(value) for _, value in quoted)
        rounds = ", ".join(label for label, _ in quoted)
        out.append(
            f"- Ranking scores he has quoted (rounds {rounds}): "
            f"{scores} = {sum(value for _, value in quoted)}."
        )
    return out


def archive_lines(archive: str | None) -> list[str]:
    """What was built, and its checksum when one sits beside it."""
    if not archive:
        return ["- Archive: not built in this run."]
    path = Path(archive)
    out = [f"- Archive: `{path}`"]
    digest = path.with_suffix(path.suffix + ".sha256")
    if digest.is_file():
        out.append(f"- sha256: `{digest.read_text(encoding='utf-8').split()[0]}`")
    return out


def compose(body: str, due: list[str], cumulative_lines: list[str], archive: str | None) -> str:
    parts = [f"# Submission mail draft, {datetime.now(UTC):%Y-%m-%dT%H:%MZ}", ""]
    parts += [body.strip() if body.strip() else "_No filled body: run fill_report.py first._", ""]
    parts += ["---", "", "## The delivery", "", *archive_lines(archive), ""]
    parts += ["## Cumulative record, from docs/rounds.md", "", *cumulative_lines, ""]
    parts += ["## Open questions due for a reminder, from docs/questions.md", ""]
    parts += due if due else ["- None open and due."]
    parts += ["", "Send: paste the body, attach the report .docx, upload the archive."]
    return "\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="save it; without this it is printed")
    parser.add_argument("--archive", default=None, help="the built delivery this mail sends")
    parser.add_argument("--questions", type=Path, default=QUESTIONS)
    parser.add_argument("--rounds", type=Path, default=ROUNDS)
    parser.add_argument("--body", type=Path, default=BODY)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--today", default=None, help="YYYY-MM-DD, for testing a remind date")
    args = parser.parse_args(argv)

    today = date.fromisoformat(args.today) if args.today else datetime.now(UTC).date()
    body = args.body.read_text(encoding="utf-8") if args.body.is_file() else ""
    due = reminders(_read(args.questions), today)
    draft = compose(body, due, cumulative(_read(args.rounds)), args.archive)

    if not args.write:
        print(draft, end="")
        print(f"[rehearsal] nothing written; {len(due)} question(s) due for a reminder")
        return 0
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}.md"
    out.write_text(draft, encoding="utf-8")
    print(f"{out}: written, {len(due)} question(s) due for a reminder")
    return 0


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


if __name__ == "__main__":
    raise SystemExit(main())
