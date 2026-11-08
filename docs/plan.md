# The plan
Aim: sustainable unattended collection with rising throughput, 1996 to 2001 first. The one measured
bottleneck: IA caps CDX at two clients an address, so throughput is addresses. The work, in order:
- #585 runner lanes: scheduled jobs on this repo run CDX slices, the VM banks their journals.
- #586 the VM runs the agent and new-source exploration; its lanes stay while they add to the total.
- #587 the agent tunes every 4 h, works only on breakage, merges its own PRs, scouts off-Wayback.
- #588 supervisor write-up: the question, the method, the architecture, the numbers.
- #523 triage, #506 disk floor, #511 lane floor, #515 suite, rest of #517; #576 incremental export.

Where we stand is read in the heartbeat. The agent refills an empty queue with umbrella #517's next
open issue (`scripts/agents/run_agent.sh`); a session's: one the owner names, one whose PR changes a
rail file or the umbrella leaves to a session, or one `data/logs/agent_runs.tsv` shows it stuck on.
