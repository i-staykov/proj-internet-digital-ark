A work run: take the queue's top item to a merged pull request, with nobody involved.

1. First, your open pull requests: `gh pr list --search "head:agent-" --json number,headRefName`.
   Inside :36 to :04 UTC, each whose CI is green: `gh pr merge M --squash --delete-branch`, then
   `work_queue.py done <id>` and `git worktree remove ~/ark-agent/<id>`; a red one is your item.
2. `python3 scripts/agents/work_queue.py top` is your item (the runner counted the attempt).
   Its resume note, if any, says where the last run stopped: continue there, on its branch.
   Else `git worktree add ~/ark-agent/<id> -b agent-<id> origin/live`; work only in that worktree.
   Every git state change names it: `git -C ~/ark-agent/<id> commit|rebase|push ...`.
3. An `issue` item: `gh issue view N` is the whole specification; deliver its Accept, no more.
   An `alert` item: the issue's diagnosis is the evidence; fix the cause, never the symptom.
   An `improvement` item: its evidence names the measurement; one variable, with its laws row.
   Tests that guard what you shipped go in the same PR; the hook gate must pass on commit.
4. Commit only while `bash scripts/harness/sync_lock.sh holder` prints nothing. Before pushing,
   read your own `git -C ~/ark-agent/<id> diff origin/live` whole, first-hand, and cut what the
   issue did not ask for. Then spawn one skeptic subagent on the diff and the issue's Accept,
   and fix what it refutes. Record its verdict in one paragraph.
5. `git -C ~/ark-agent/<id> push -u origin agent-<id>`; `gh pr create --base live` with the body:
   `Closes #N` when the item names an issue, the `+added / -deleted` counts from
   `git -C ~/ark-agent/<id> diff --stat origin/live`, the skeptic's paragraph, nothing else.
   `work_queue.py note <id> "PR #M open"`.
6. When your turns or time run out first, leave one resume note on the item
   (`work_queue.py note <id> "<what is done, what is next, the branch>"`) and stop cleanly; the
   next run resumes your session once, then starts fresh from the note.
7. End with one line: the item, what landed (a PR number, a merge, a note) and what is next.

A merge conflict with live: `git -C ~/ark-agent/<id> rebase origin/live`, never force anything.
A rule change or a new evidence class is not yours: a `needs-owner` issue, then `park`.
