# His own words, transcribed

`project-brief.md` is the CURRENT task brief, pandoc's conversion of his `.docx`, never
retyped and never hand-edited. The header carries the sha256 of the source file.

One file on purpose (Ivo, 2026-09-18): the current state of the task, no changelog and no
amendments. Git holds every earlier state.

Refresh after each package:

    uv run python scripts/round/extract_ding_docs.py --package <dir> \
        --archive '<archive> (<delivery date>)' --stamp <date>
