A triage run: read the VM, act on what a script cannot, and change nothing else.

Read, each through one subagent that returns the conclusion: the last 24 rows of
data/logs/ticks.tsv; `gh issue list -R i-staykov/ark-fleet --label vm-alert --state open`;
`just check unattended`; `journalctl --user -u 'ark-*' --since -2h -n 200`; the last 30 lines
of each data/logs/lane*.log. A file or recipe that does not exist yet is a finding, not an error.

Then end in exactly one of:
- nothing, when every read is green;
- BANK RED: `just red-clear` once the cause is fixed, and one comment on its vm-alert issue
  (`gh issue comment -R i-staykov/ark-fleet`) with the reason; a red clears only through that
  recipe;
- a reader stopped: `python3 scripts/agents/triage.py restart <reader> [--item ID]`;
- the lanes: `python3 scripts/agents/triage.py walk`, and no other way;
- a cause a fix in code needs: `work_queue.py add alert|improvement "<title>" --evidence "<what
  you read>" --priority N`, then `work_queue.py note <id> "<where to start>"`;
- anything else: one `vm-alert` issue (`gh issue create|reopen -R i-staykov/ark-fleet`, never
  duplicate) with the diagnosis.

A refusal (exit 3) from triage.py is the answer: queue the work item it names, do not retry.
Never touch the sync lock or the tick and agent units, never commit or push.

End with exactly one line: `OK`, or the outcome and the issue or item it went to.
