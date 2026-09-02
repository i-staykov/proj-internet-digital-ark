"""What filled an agent's context, measured from the session transcript.

Two sessions ever compacted, 78 times, 60 of them by hand. The transcript is the only record
of what the model was actually shown, so this reads it instead of adding a log: which tool
results were largest, how many bytes each tool returned in total, how much the assistant
wrote, how often it wrote a wall of text, and how many times the conversation was compacted.

Transcripts are JSONL under `~/.claude/projects/<cwd slug>/*.jsonl`, the slug being the
repository path with `/` replaced by `-`. A record carries `uuid`, `type` and
`message.content`, a list of blocks; `tool_use` blocks name the tool and carry an `id`,
`tool_result` blocks point back with `tool_use_id`. Resumed sessions copy earlier records
into the new file, so records are deduplicated by `uuid` (58,348 duplicates across 724
files when this was written). A compaction is a `system` record with `subtype`
`compact_boundary`.

The schema is not a contract and this is a diagnostic, never a gate: it exits 0 whatever it
finds and prints nothing from any record but a tool name and a byte count.

    uv run python scripts/agents/context_report.py            # newest transcript
    uv run python scripts/agents/context_report.py PATH       # one transcript
    uv run python scripts/agents/context_report.py --all      # every transcript, one summary
"""

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# Keyed on the working directory, which is how the harness names the folder.
TRANSCRIPT_DIR = Path.home() / ".claude" / "projects" / str(Path.cwd()).replace("/", "-")
TOP_N = 10
TOP_TOOLS = 12
LONG_TEXT_CHARS = 1500


@dataclass
class Report:
    files: int = 0
    records: int = 0
    duplicates: int = 0
    tool_names: dict[str, str] = field(default_factory=dict)
    # (bytes, tool_use_id) so the largest can be named after every tool_use has been seen.
    results: list[tuple[int, str]] = field(default_factory=list)
    result_bytes_by_tool: Counter = field(default_factory=Counter)
    assistant_text_bytes: int = 0
    long_text_blocks: int = 0
    compacts: Counter = field(default_factory=Counter)

    def tool_of(self, tool_use_id: str) -> str:
        return self.tool_names.get(tool_use_id, "unknown")


def block_bytes(content: object) -> int:
    """UTF-8 bytes of a tool_result's content, which is a string or a list of blocks."""
    if isinstance(content, str):
        return len(content.encode("utf-8"))
    if isinstance(content, list):
        total = 0
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                total += len(part["text"].encode("utf-8"))
            else:
                total += len(json.dumps(part, ensure_ascii=False).encode("utf-8"))
        return total
    return 0


def scan(path: Path, report: Report, seen: set[str]) -> None:
    """Fold one transcript into the report, skipping records whose uuid was already seen."""
    report.files += 1
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict):
                continue
            uuid = rec.get("uuid")
            if uuid is not None:
                if uuid in seen:
                    report.duplicates += 1
                    continue
                seen.add(uuid)
            report.records += 1
            kind = rec.get("type")
            if kind == "system":
                if rec.get("subtype") == "compact_boundary":
                    trigger = (rec.get("compactMetadata") or {}).get("trigger", "unknown")
                    report.compacts[trigger] += 1
                continue
            content = (rec.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "tool_use" and kind == "assistant":
                    report.tool_names[str(block.get("id"))] = str(block.get("name"))
                elif btype == "tool_result":
                    size = block_bytes(block.get("content"))
                    report.results.append((size, str(block.get("tool_use_id"))))
                elif btype == "text" and kind == "assistant":
                    text = block.get("text") or ""
                    report.assistant_text_bytes += len(text.encode("utf-8"))
                    if len(text) > LONG_TEXT_CHARS:
                        report.long_text_blocks += 1


def finish(report: Report) -> None:
    """Attribute result bytes to tools once every tool_use in scope has been read."""
    report.result_bytes_by_tool.clear()
    for size, tool_use_id in report.results:
        report.result_bytes_by_tool[report.tool_of(tool_use_id)] += size


def render(report: Report, label: str) -> list[str]:
    total_results = sum(report.result_bytes_by_tool.values())
    lines = [
        f"{label}: {report.files} file(s), {report.records:,} records, "
        f"{report.duplicates:,} duplicate uuids skipped",
        "",
        f"largest tool_result blocks ({len(report.results):,} in total, {total_results:,} bytes)",
    ]
    for size, tool_use_id in sorted(report.results, reverse=True)[:TOP_N]:
        lines.append(f"  {size:>11,}  {report.tool_of(tool_use_id)}")
    lines += ["", "tool_result bytes by tool"]
    ranked = report.result_bytes_by_tool.most_common()
    for tool, size in ranked[:TOP_TOOLS]:
        lines.append(f"  {size:>11,}  {tool}")
    if len(ranked) > TOP_TOOLS:
        rest = ranked[TOP_TOOLS:]
        lines.append(f"  {sum(s for _, s in rest):>11,}  other ({len(rest)} tools)")
    manual = report.compacts.get("manual", 0)
    auto = report.compacts.get("auto", 0)
    lines += [
        "",
        f"assistant text: {report.assistant_text_bytes:,} bytes, "
        f"{report.long_text_blocks} block(s) over {LONG_TEXT_CHARS:,} chars",
        f"compact events: {sum(report.compacts.values())} ({manual} manual, {auto} auto)",
    ]
    return lines


def newest_transcript(directory: Path) -> Path | None:
    files = sorted(directory.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def report_for(paths: list[Path]) -> Report:
    report = Report()
    seen: set[str] = set()
    for path in paths:
        scan(path, report, seen)
    finish(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("path", nargs="?", type=Path, help="one transcript (default: newest)")
    parser.add_argument("--all", action="store_true", help="aggregate over every transcript")
    parser.add_argument("--dir", type=Path, default=TRANSCRIPT_DIR, help="transcript directory")
    args = parser.parse_args(argv)

    if args.all:
        paths = sorted(args.dir.glob("*.jsonl"))
        if not paths:
            print(f"no transcripts under {args.dir}")
            return 0
        label = f"all transcripts under {args.dir.name}"
    else:
        path = args.path or newest_transcript(args.dir)
        if path is None or not path.is_file():
            print(f"no transcript found ({path or args.dir})")
            return 0
        paths = [path]
        label = path.name
    print("\n".join(render(report_for(paths), label)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
