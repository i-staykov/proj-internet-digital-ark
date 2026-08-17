# legacy: superseded, kept on purpose

Nothing in here runs, and nothing in here is maintained. It is kept because the
**negative results and the retired designs are worth more than the code**: they are
what stops the next person rebuilding a tool whose answer is already known, or
re-proposing a source a measurement already closed.

Three rules, so this folder cannot rot into a second source of truth:

1. **Not linted, not tested, not imported.** `pyproject.toml` excludes `legacy` from
   ruff and `testpaths = ["tests"]` keeps pytest out. Several files here import
   modules that also moved, so they are preserved rather than runnable, and that is
   the intended state.
2. **Not shipped.** `.gitattributes` marks this tree `export-ignore`, so
   `git archive` leaves it out of the delivery snapshot. The reviewer gets the
   working pipeline, not its history.
3. **Read-only.** If something here becomes useful again, move it back out and
   bring it up to the current standard. Do not edit it in place.

| subtree | what is in it |
|---|---|
| `src/` | two retired engines |
| `tests/` | their tests, plus the three retired integrity invariants |
| `scripts/` | spent one-off probes, completed migrations, superseded supervisors |
| `docs/` | retired design documents, and the index of retired data directories |
| `notes/` | past-round session logs and outside-agent handbacks (**git-ignored**) |

## Why each piece is here

### `src/language.py` and `tests/test_language.py`

The page-level English verification engine. The reviewer's phase-3 feedback required
an addition to be shown to have been an English-language website in that year, judged
from archived body text, and phase 4 shipped the additions split into English-verified
and unverified sets. **He retired that standard in August 2026** in favour of the
equivalent-English metric, which weights each record by the English share of its TLD
and needs no page fetch at all. See `docs/brief_amendments.md`.

Three ideas in it are worth more than the engine and are transferable to any collector
that asks a service a question:

- **Unsettled is a first-class outcome.** A verdict, a documented rejection and "the
  question did not land" are three different things. Collapsing the third into the
  second excludes a possibly-good record on the strength of a transport error, which
  this project did once before in the RDAP engine at a cost of 12,888 domains.
- **A domain is never excluded on the strength of a question that was not asked.** An
  empty filtered CDX result means "nothing matching that filter", not "nothing at
  all", so a second unfiltered probe runs before an absence is recorded.
- **`ENGINE_VERSION`, and why a verdict records the version that produced it.** Two
  rounds of verdicts had to be discarded because the exporter excluded any pair that
  had a verdict row at all, so a defect became permanent the moment it produced
  output. A pair should leave the work queue only when asking again could not change
  the answer.

The `domain_language` table is **deliberately still in `src/ark/db.py`**, with its
migration. Existing stores hold those rows, every provenance export shipped to the
reviewer contains them, and `ark rebuild` loads them. Dropping the table would make
an already-delivered archive unrebuildable.

### `src/verify.py` and `tests/test_verify.py`

The original CDX verifier: six sequential queries per domain, driven off the SQLite
work queue. Replaced by `src/ark/cdx.py`, which answers all six years in **one
collapsed query per domain**. That is the single most important throughput lesson in
the project: the archive limits what it will serve one client, so the lever is
**requests per verdict**, not requests in flight.

### `tests/test_checks_english.py`

The three integrity invariants that policed the English partition, removed from
`src/ark/checks.py` when the standard was retired. The gate is nine invariants now.

### `scripts/`

| file | why it is here, and what the answer was |
|---|---|
| `supervise_lang.sh`, `watchdog_lang.sh` | The retired standard's supervisor pair. Their design lesson survives in `supervise_cdx_pool.sh`: **a watchdog must check progress, not presence.** A batch hung on a socket leaves the supervisor alive and the journal frozen, which a PID check reports as healthy. The successor folds both into one process, so a watchdog cannot restart a supervisor with retuned settings it does not know about |
| `finalise_delivery.sh` | Pre-deadline orchestration built around the retired partition. Its **ordering** is the part to reuse: stop the collectors, wait for the `.part` renames, ingest everything, export, run the gate, fill the report, package, then verify the archive from outside the repository |
| `maintain.sh` | The first ingest loop, superseded by `scripts/maintain.sh` (which was `maintain_phase3.sh` until the name was freed). Its one lesson is now in the successor's comments: counting distinct domains over net-new pairs reported **1,161,961 domains against a true 463,566**, because a baseline domain gaining a year it lacked is a new pair on an old domain |
| `supervise_engines.sh` | Kept rather than deleted, and the reason is a gap: it is the only unattended **idle-detecting re-dispatcher for RDAP**. `rdap-batch` runs one batch and `rdap-pool` a bounded sweep, so neither restarts on idle. If phase 5 runs RDAP unattended, start from this |
| `fetch_usenet_groups.py` | Selected Usenet groups by name components under a size cap. Its problem is gone: the catalogue is 19,233 groups and 19,231 are downloaded. Keep for the trap it documents, which generalises to any token filter: **match name components, not substrings**, because `talk.bizarre` contains "biz" and is not a commerce group |
| `probe_usenet_groups.py`, `screen_usenet_archives.py`, `gate_usenet_groups.py` | Three ways of deciding which archives to fetch, all answered by fetching them all. The findings that outlived them: yield is **bimodal rather than smoothly decaying**; **4,023,027 of 5,283,482** probed messages were out of window, so three quarters of the bytes bought nothing; and the date gate "barely fires, and that is the finding rather than a defect" |
| `measure_usenet_decay.py` | Read the marginal-yield curve directly. Answer: `a * g^0.909`, so saturation had barely started at 28 groups. Distinct from `measure_usenet_yield.py`, which is live and justfile-wired |
| `measure_capture_rate.py` | Settled whether 1996 and 1997 deserved any archive budget. **1996 5.4%, 1997 12.6%, 9.1% overall** have an in-year capture despite no `cdx_timestamp` in the store. Now recorded in `docs/sources.md`. Imports `ark.language`, so it no longer resolves |
| `measure_nypw_yield.py` | The project's most-cited methodological save: the NYPW index was estimated at **27,276 net-new domains and measured at 53**, the error being registered domains compared against raw hostname lines. Read this before trusting any yield estimate |
| `probe_webrings.py` | Web rings, rejected. Two traps recorded in `docs/sources.md`: `matchType=prefix` on `www.webring.org/*` returns zero because the member lists are query strings off the site root |
| `journal_from_wwwvl.py` | Converted 2,709 out-of-band WWW Virtual Library captures into a standard journal, once. **It is the sole producer of two journals that `just journals` still ingests**, so if `data/raw/expand/wwwvl/` is ever lost, this is what regenerates it rather than re-fetching 2,709 snapshots |
| `restrict_whois_creation_to_creation_year.py` | A completed one-time migration enforcing brief III.6, now enforced at ingest instead. Kept out of `scripts/` deliberately: a stray `--apply` would delete current evidence |
| `feed_usenet_bulk.sh`, `ingest_usenet_batched.sh` | Drip-fed a 12,000-archive corpus through split-and-ingest. Both spent. The argument they record is still true: one pass runs for hours and holds the DuckDB write lock at the end, so a bulk corpus has to be fed in batches |

### Two scripts that were deleted rather than archived

`maintain_loop.sh` was twelve lines wrapping a script that is itself archived, with
zero references anywhere in the tree. `refresh_report_figures.py` rewrote one sentence
in `README.md` from the store and **could no longer run at all**: its only regex anchor
had been edited out of the README, so every invocation hit its own `raise SystemExit`.
Its own docstring settled it: "a rewriter that cannot find its anchor is worse than no
rewriter". Note what went with it, though: keeping README figures in step with the
store is now discipline plus `ark stats`, with no automation behind it.
