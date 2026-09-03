"""Read one verdict mail and write its round's row in docs/rounds.md.

His verdicts follow one template: five labelled figures, sometimes numbered, sometimes
with a sixth candidate-pool line, and sometimes a `Score calculation:` line. Only the
figures are read here. **S and t are never parsed, always computed**, from the awarded
percentage and the two stamps, through `ark.figures`, because the score the report
shipped in round 7 was 226.43 against his 6.302372 and the difference was a clock rule
nobody had written down. Where he does quote S, his figure is compared against ours at
two places and a disagreement is printed rather than written: the mail is the record of
what he scored, this page is the record of what the rule gives, and when they part it is
the rule that is wrong.

    uv run python scripts/round/rounds.py --mail private/mail/verdict7.txt \\
        --round 7 --received "2026-09-02 05:50"

`--released` defaults to the stamp the round already carries in `ark.baseline`, and to
the current baseline's release for a round that has none yet. The benchmark marker is
read from the backticks in his mail and marked `not received` when no extracted tree of
that name is under the feedback root, which is the state three of his markers are in:
he scored against an interim merge he never sent.

Only the target row is rewritten. Every other line of the page, and every column this
script does not compute, is left exactly as it is.
"""

import argparse
import re
from decimal import Decimal
from pathlib import Path

from ark.baseline import CURRENT_BASELINE_RELEASED, SUBMITTED_ROUNDS
from ark.figures import elapsed_days, score, t_days

PAGE = Path("docs/rounds.md")
FEEDBACK = Path("feedback")

# A cell of a new row that nothing here can fill.
BLANK = "pending"
NOT_RECEIVED = "not received"

# His five figures, by the letters of their label. First match wins, so the compound
# labels come before the words they contain: "Equivalent-English increment" must not be
# read as "Increment", and the candidate-pool line must not be read as line 5.
FIGURES = (
    ("candidate_growth", "candidate"),
    ("increment_ee", "equivalentenglishincrement"),
    ("growth", "equivalentenglishgrowthrate"),
    ("total_ee", "equivalentenglishtotal"),
    ("increment_records", "increment"),
    ("total_records", "total"),
)

NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
MARKER = re.compile(r"`(merged\d{6}(?:-\d+)?)`")
LETTERS = re.compile(r"[^a-z]")
# The trailing `= 6.302372` of his score line, which is read only to be compared.
QUOTED_SCORE = re.compile(r"=\s*(\d+(?:\.\d+)?)\s*$")

TWO_PLACES = Decimal("0.01")


def number(text: str) -> Decimal:
    """The first figure in a value, thousands separators and trailing units dropped."""
    m = NUMBER.search(text)
    if not m:
        raise ValueError(f"no figure in {text!r}")
    return Decimal(m.group(0).replace(",", ""))


def parse_mail(text: str) -> dict:
    """His figures, the benchmark marker, and the score he quotes if he quotes one."""
    found: dict = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        label, _, value = line.partition(":")
        key = LETTERS.sub("", label.lower())
        if "score" in key:
            m = QUOTED_SCORE.search(value.strip())
            if m:
                found["quoted_score"] = Decimal(m.group(1))
            continue
        for name, needle in FIGURES:
            if needle in key and name not in found:
                found[name] = number(value)
                break
    m = MARKER.search(text)
    if m:
        found["marker"] = m.group(1)
    missing = [n for n, _ in FIGURES[1:] if n not in found]
    if missing:
        raise SystemExit(f"mail is missing {', '.join(missing)}")
    return found


def released_for(label: str) -> str:
    """The release his score divides by: the round's own stamp, or today's baseline."""
    for row in SUBMITTED_ROUNDS:
        if row[0] == label:
            return row[6]
    return CURRENT_BASELINE_RELEASED


def marker_received(feedback: Path, marker: str) -> bool:
    """Whether an extracted tree of that release is under the feedback root."""
    if not feedback.is_dir():
        return False
    return any(p.is_dir() for p in feedback.rglob(marker))


def cells_of(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def find_table(lines: list[str]) -> tuple[int, int, list[str]]:
    """(header index, index after the last data row, the column names)."""
    for i, line in enumerate(lines):
        if line.startswith("|") and cells_of(line)[:1] == ["round"]:
            columns = cells_of(line)
            end = i + 2
            while end < len(lines) and lines[end].startswith("|"):
                end += 1
            return i, end, columns
    raise SystemExit("no table with a `round` column in the page")


def sort_key(label: str) -> tuple[int, str]:
    """Rows are in round order, and a label that is not a number sorts last."""
    return (int(label), "") if label.isdigit() else (1 << 30, label)


def row_line(columns: list[str], old: list[str] | None, values: dict[str, str]) -> str:
    """One table line: computed cells, then the old ones, then blanks."""
    cells = []
    for i, column in enumerate(columns):
        key = column.lower()
        if values.get(key) is not None:
            cells.append(values[key])
        elif old is not None:
            cells.append(old[i])
        else:
            cells.append(BLANK)
    return "| " + " | ".join(cells) + " |"


def update_page(text: str, label: str, values: dict[str, str]) -> str:
    """Rewrite one round's row, leaving every other line byte for byte."""
    lines = text.split("\n")
    head, end, columns = find_table(lines)
    at, old = None, None
    for i in range(head + 2, end):
        row = cells_of(lines[i])
        if row[0] == label:
            at, old = i, row
        elif at is None and sort_key(row[0]) > sort_key(label):
            at = i
    line = row_line(columns, old, values)
    if old is not None:
        lines[at] = line
    else:
        lines.insert(end if at is None else at, line)
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--mail", type=Path, required=True, help="his verdict mail, as text")
    ap.add_argument("--round", required=True, help="the round label, as the page writes it")
    ap.add_argument("--received", required=True, help="'YYYY-MM-DD HH:MM' in his clock")
    ap.add_argument("--released", help="the benchmark release stamp, same format")
    ap.add_argument("--page", type=Path, default=PAGE)
    ap.add_argument("--feedback", type=Path, default=FEEDBACK)
    ap.add_argument("--sent-records", help="records sent, which the mail does not carry")
    ap.add_argument("--sent-ee", help="equivalent-English sent")
    ap.add_argument("--sent-pct", help="percentage claimed when sending")
    ap.add_argument("--note", help="the note cell")
    args = ap.parse_args()

    mail = parse_mail(args.mail.read_text(encoding="utf-8", errors="replace"))
    p = mail["growth"]
    released = args.released or released_for(args.round)
    t = t_days(released, args.received)
    s = score(p, t)

    print(f"his database: {mail['total_records']:,} records, {mail['total_ee']:,} EE")
    print(f"round {args.round}: credited {mail['increment_records']:,} records, {p}%")
    print(f"  {released} -> {args.received} is {elapsed_days(released, args.received):.2f} days")
    print(f"  t = {t}, S = {s}")
    if "candidate_growth" in mail:
        print(f"  candidate-pool growth rate {mail['candidate_growth']}%, not part of S")

    quoted = mail.get("quoted_score")
    if quoted is not None and quoted.quantize(TWO_PLACES) != s.quantize(TWO_PLACES):
        print(f"  WARNING: he quotes S = {quoted}, the rule gives {s}: the clocks disagree")

    against = mail.get("marker")
    if against and not marker_received(args.feedback, against):
        print(f"  {against}: {NOT_RECEIVED} under {args.feedback}/")
        against = f"{against} ({NOT_RECEIVED})"

    values = {
        "round": args.round,
        "sent records": args.sent_records,
        "sent ee": args.sent_ee,
        "sent %": args.sent_pct,
        "credited records": f"{mail['increment_records']:,}",
        "credited ee": f"{mail['increment_ee']:,}",
        "awarded p_i": f"{p:,}",
        "against": against,
        "released": released,
        "received": args.received,
        "days": f"{elapsed_days(released, args.received):.2f}",
        "t_i": str(t),
        "s_i computed": f"{s}",
        "s_i quoted": str(quoted) if quoted is not None else "not quoted",
        "note": args.note,
    }
    text = args.page.read_text(encoding="utf-8")
    new = update_page(text, args.round, values)
    if new == text:
        print(f"{args.page} unchanged")
        return
    args.page.write_text(new, encoding="utf-8")
    print(f"wrote {args.page}")


if __name__ == "__main__":
    main()
