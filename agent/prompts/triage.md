A triage run: read the VM, act on what a script cannot, and change nothing else.

Read, each by a subagent: the last 24 rows of data/logs/ticks.tsv;
each open alert's number, title, newest text (comment or body) and last `triage: green`
(`gh issue list -R i-staykov/ark-fleet -l vm-alert --json number,title,body,comments`);
`just check unattended`; `journalctl --user -u 'ark-*' --since -2h -n 200`; the last 30 lines
of data/logs/lane*.log. A missing file is a finding. Never commit or push.

One act per cause, none if taken or queued:
- BANK RED: `just red-clear` once the cause is fixed;
- a reader stopped: `python3 scripts/agents/triage.py restart <reader> [--item ID]`;
- the lanes: `python3 scripts/agents/triage.py walk`;
- a fix in code: `work_queue.py add alert|improvement "<title>" --evidence "<what you read>"
  --priority N`, then `work_queue.py note <id> "<where to start>"`;
- else one `vm-alert` issue opening `triage:` (`gh issue create|reopen -R i-staykov/ark-fleet`).
A triage.py refusal (exit 3) is final: queue the item it names.

Every open alert, by `gh issue comment|close N -R i-staykov/ark-fleet`: green now, close it
with `triage: green, <evidence>`, unless `parked:` or closed by a triage within 24 h;
else, if its newest text lacks `triage:`, one comment `triage: <cause>; <evidence>; <act>`.

End with one line: `OK` if all is green and no alert open, else each act and where it went.
