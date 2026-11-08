A triage run: read the VM, act on what a script cannot, and change nothing else.

Read, each by a subagent: the last 24 rows of data/logs/ticks.tsv; each open alert's number,
title, newest text (comment or body) and last `triage: green`
(`gh issue list -l vm-alert --json number,title,body,comments`); `just check unattended`;
`journalctl --user -u 'ark-*' --since -2h -n 200`; data/logs/lane*.log's last 30 lines. A
missing file is a finding.

One act per cause, none if taken or queued:
- BANK RED, its cause fixed: `just red-clear`;
- a reader stopped: `python3 scripts/agents/triage.py restart <reader> [--item ID]`;
- the lanes: `python3 scripts/agents/triage.py walk`;
- a code fix: `work_queue.py add alert|improvement "<title>" --evidence "<what you read>"
  --priority N`, then `work_queue.py note <id> "<where to start>"`;
- else one `vm-alert` issue `triage: <cause>` (create or reopen, never a duplicate).
A triage.py refusal (exit 3) is final: queue the item it names.

An open alert titled `vm-alert:` or `triage:` and green now gets one comment `triage: green,
<evidence>` and closes, unless a triage closed it in 24 h; any other whose newest text lacks
`triage:` gets one comment `triage: <cause>; <evidence>; <act>`. Every `gh issue` takes
`-R i-staykov/ark-fleet`, its text `--body-file`. Never commit or push.

End on one line: `OK` if all is green and no alert open, else each act and where it went.
