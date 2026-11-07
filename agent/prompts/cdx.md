A cdx run: the lanes' productivity, 1996 to 2001 first, from one row and at most one lever,
with nobody involved.

1. The row: the last line of `data/logs/productivity.tsv`, written daily by
   `scripts/agents/lane_yield.py` (per question kind and window: requests, answered, paused
   seconds, EE priced as banked, EE per client-second, the 7-day band). A file or script that
   does not exist yet is a finding, not an error: end on it.
2. The objective, in order: 1996 to 2001 EE per client-second, then 2002 to 2013, then requests
   per EE. Every lane inside its band needs nothing: end on the row.
3. The levers are the `levers` list of the policy file `lane_yield.py` names, each with its
   last measurement and date; pull none not listed, none when the list is absent. One lever a
   day, the one whose measurement says it moves the lane under its band.
4. The pull: `git worktree add ~/ark-agent/cdx-<date> -b agent-cdx-<date> origin/live`; work
   only there, every git state change naming it (`git -C ~/ark-agent/cdx-<date> ...`). The PR
   changes the one lever's value, its measurement and date, and bumps that policy's `version`;
   no code change beside it. Commit only while `bash scripts/harness/sync_lock.sh holder`
   prints nothing; push `agent-cdx-<date>`; `gh pr create --base live` with the row's line, the
   `+added / -deleted` counts and one skeptic subagent's paragraph on the pull, nothing else.
   The next work run merges it.
5. The day after a pull, its laws row: the first row after the merge against the one before,
   as one line under Channel in `docs/lore/laws.md`, by the same route as a pull.
6. Anything outside the list (a new evidence class, a new address for a CDX client, a
   custodian's terms) is a `needs-owner` issue.
7. End with one line: the row's date, the lane under its band or none, and the lever pulled
   (its PR), the laws row, the issue, or the finding.
