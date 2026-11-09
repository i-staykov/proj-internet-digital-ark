A work run: take the queue's top item to a green pull request, with nobody involved; the triage
merges it.

1. `python3 scripts/agents/work_queue.py top` is your item (the runner counted the attempt).
   Its resume note, if any, says where the last run stopped: continue there, on its branch.
   Else `git worktree add ~/ark-agent/<id> -b agent-<id> origin/live`, or for an alert `PR #M
   red` its evidence's branch; work only in that worktree.
   Every git state change names it: `git -C ~/ark-agent/<id> commit|rebase|push ...`.
2. An `issue` item: `gh issue view N` is the whole specification; deliver its Accept, no more.
   An `alert` item: the issue's diagnosis is the evidence; fix the cause, never the symptom.
   An `improvement` item: its evidence names the measurement; one variable, with its laws row.
   Tests that guard what you shipped go in the same PR; the hook gate must pass on commit.
3. Commit only while `bash scripts/harness/sync_lock.sh holder` prints nothing. Before pushing,
   read your own `git -C ~/ark-agent/<id> diff origin/live` whole, first-hand, and cut what the
   issue did not ask for. Then spawn one skeptic subagent on the diff and the issue's Accept,
   and fix what it refutes. Record its verdict in one paragraph.
4. `git -C ~/ark-agent/<id> push -u origin agent-<id>`; `gh pr create --base live` with the body:
   `Closes #N` when the item names an issue, the `+added / -deleted` counts from
   `git -C ~/ark-agent/<id> diff --stat origin/live`, the skeptic's paragraph, nothing else.
   `work_queue.py note <id> "PR #M open"`.
5. When your turns or time run out first, leave one resume note on the item
   (`work_queue.py note <id> "<what is done, what is next, the branch>"`) and stop cleanly; the
   next run resumes your session once, then starts fresh from the note.
6. End with one line: the item, what landed (a PR number, a push, a note) and what is next.

A merge conflict with live: `git -C ~/ark-agent/<id> rebase origin/live`, never force anything.
A rule change or a new evidence class is not yours: a `needs-owner` issue, then `park`.
