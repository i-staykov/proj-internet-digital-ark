# Traps

**Mistakes this project has already paid for, one paragraph each.** Read before trusting a
number, running a collector, or sending a first request to a host. Cut from `CLAUDE.md` on
2026-09-02 and from `.github/copilot-instructions.md` on 2026-09-03, which is now a pointer;
the measured laws of pricing are in [laws.md](laws.md), the rules in [rules.md](rules.md).

## Numbers and negatives

**Prove a negative against a known positive.** Nothing-found and pointed-wrong look identical.

**Verify every number, including a subagent's.** Several were fabricated or out by 1000x.

**An already-ingested journal shows 0 net-new by construction.** Measure against a pre-ingest
snapshot.

**Measure a rate over a trailing window, not a lifetime, and never across a backfill.** A
lifetime average hides the hour that stopped paying, and a backfill inside the window inflates
every rate computed over it.

**Check the dates before counting the contents.** Real hostname counts on files dated 1990 to
1992 have wasted days: nothing outside 1996-2001 can evidence a year, however many names it holds.

**A partitioned corpus must be measured per partition, never reasoned about.** `nypw_timemaps`
was closed at 14.2 EE on its 1996 folder, reopened on 1999 and 2000 for **+87,905 EE**, and one
run then argued from a plausible mechanism that the 2001 folder was the real seam. `ark ingest`
reports `year_rows` per file: the 2001 part wrote **6**, against 94,695 for one 2000 part. The
ledger is free, needs no store lock, and settles any claim about what a partition paid. Read it
before acting on a partition recommendation, including your own.

**A collapse after a change is not evidence the change caused it.** Three queue orderings were
compared inside the Verisign clamp below and all read as catastrophic, which produced a
confident and wrong law about ranking. Get a per-minute series out of the journals before
attributing a rate change to anything.

**A corroboration split is only as independent as its partner source.** When the partner is a
class this project has already swept at scale, the split validates nothing and the failure is
invisible in the headline: the same Usenet bytes and the same parse priced 22,838 EE against the
current baseline and 252 EE against `merged260810`, a 91x spread. Price a source against a
reviewer cut from BEFORE our own collector last ran in that channel.

**A figure that does not come from the shipped files is not the round's figure.** The
scoreboard and the export each computed net-new from the store, and only the export applied the
shipping filter, so on 2026-09-03 the brief quoted 17,638 pairs against 16,772 in the files: 866
pairs and 479.4256 EE under `.arpa` or dated before their TLD existed, which no round could be
credited for. `ark.delegation.shipping_filter` is the one predicate; every count that claims to
be what ships takes it, and a new counter that does not is wrong by construction.

**A hostname-grain figure is not a figure until the `www.` alias share is measured.** Two lane-A
corpora came back from the E9.5 batch as five-figure finds and both were the same illusion:
`ukwa` 20,916.90 EE of which 99.5% was `www.<a name already held that year>`, and
`nypw_firstcdx` 7,074.09 EE of which 100.0% was, leaving 107.94 and 2.84 EE. Neither was
ingested. The seam is real code: `NOT_WWW_OF_PARENT` refuses `www.<parent registrable>` and
nothing refuses `www.<held hostname>`, so a crawler's default alias of a name we already date
counts as a new record. `just price-hosts` prints the share, `round_figures.py` prints it for the
round, and a hostname number quoted without it is not comparable to one quoted with it.

**A skeptic that re-runs the same code confirms the defect.** The first Usenet body-URL figure was
reproduced to the digit by a verifier that re-priced the same shards, and it was wrong: the post
boundary `^From (\d+|\S+@\S+)` cannot match the negative signed ids Google Groups exports use, so
**50.019% of posts were never recognised** and every unrecognised post's header block was appended
to the previous post's body. 14.02% of extracted hosts then came from header lines, `Organization:`
alone 12.65%, which is the news-relay class the write-up promised to exclude, and the post totals
were understated 2x. **A verifier has to read the extractor against the raw bytes.** The same round
found two more of the same shape: two corpora of one class priced separately and **added**, double
counting 12,387 shared keys, and a fiction screen made of a word list when the surviving fakes are
**typos of real hosts** (`mmembers.aol.com`, `home.mci20000.com`), which no list catches and only a
hand-judged sample rates.

**Extracting hosts from a Usenet or mail document with a bare dotted-token regex prices the
transport, not the web.** `rtfm` measured 20,049.42 EE that way and 3,719.91 EE when only
explicit `http://`, `https://` and `ftp://` URLs in the body counted, an 81.45% error. The header
block was the smaller half of it: `Path`, `Xref`, `NNTP-Posting-Host`, `Message-ID` and `From`
hosts are news relays and mailboxes, 12% of the error, while un-vouched dotted tokens in the body
were 69%. Extract from a URL scheme, never from the shape of a token.

## Collectors and queues

**A running collector is not a working one.** Presence, progress and yield are three questions,
and a supervisor's guess at why a batch stopped is not evidence for any of them. `just cycle`
checks yield.

**Watch a collector's hit rate, not its query rate.** The pool population went barren
overnight: 1,114 of 1,200 queries returned no capture, ~0.03 year-records per query, while the
gap queue on the other machine returned 1,647 years per 1,200. Same code, same hour, 45x apart.
`just engines` prints both; a queue whose head has already been asked is a queue that has
quietly expired.

**Rank a queue by TLD weight alone and 2013 gTLDs lead it.** Volume floor first.

**CDX tier costs, remeasured 2026-09-01 over 1,179 journals, because the old figures were from
the scan-first era and are 16x wrong.** Seconds per query by tier: `by_host` hit 2.78 to 4.93,
`scan` 3.65 to 7.58 (so **1.26x a host query, not 33 s**), `by_root` 11.84 to 46.00. The cost
outlier is `by_root` at 32.9% of collector seconds for 15.3% of years, and the two zero-yield
classes burn 31.9% of the clock. Recovering this needs no requests: journal filename stamp gives
the start, file mtime the end, per-tier record counts the design matrix.

**Verisign RDAP is a QUOTA, not a rate.** It served 64,568 queries at a flat 65 q/s for
seventeen minutes, then clamped to about 1 q/s for at least twenty-five minutes across three
restarts. Restarting does not clear it; only resting might. Budget a night's Verisign work as
one block of ~65,000 queries.

**Look for the existing tool before writing one.** A worse reimplementation of
`build_promotion_journals.py` overstated a source 20x.

## Extraction and content

**Any name-shape filter over-catches.** `bl.uk` is the British Library, `x.com` is real.

**Watch for anti-spam address munging when extracting from anything people typed.** Usenet and
mailing-list posters wrote `user@nospam.bigfoot.com` and `user@bigfoot.com.invalid` to defeat
harvesters, and an extractor turns those into `nospam.bigfoot.com` and `bigfoot.com.invalid`.
Measured 2026-08-31: `nospambigfoot.com`, `nospam.ac.uk`, `deletethis.com` and
`btnospaminternet.com` all carry dated years, and `prior_task` holds MORE such names than our
own sources do, so it is not unique to us. **The standard does not change**: a munged-looking
name that genuinely earns multi-source corroboration could be a real registration and stays.
Just do not let one extractor's artifact corroborate another's, which is the circularity trap
above.

**A dated mail or Usenet corpus contains the era's worms as message content.** That is corpus
fidelity, not compromise (Defender flagged Klez.H inside a newsgroup zip, 2026-09-01, verified
inert in `private/security/`). Parse archives in-stream, never extract attachments, delete probe
bytes after measurement, and match an AV alert's hashes against the file before acting on it.

**A size floor is not a content check.** A replay URL built as `{stamp}id_{host}`, missing the
slash in `id_/`, made web.archive.org answer seven different objects with the same 154,263-byte
interstitial, and a floor set at half the expected bytes passed all seven. Assert on what the
artifact must CONTAIN, and read identical sizes across different objects as a failed fetch.

## Hosts, terms and refusals

**archive.org's `services/search/v1/scrape` LIES under load. Use `advancedsearch.php` for any
zero.** Caught twice on 2026-08-19: it returned the same 6 items for five different collections,
and an identical bogus `total=28330` for five different queries, producing six false zeros in
one batch. It also rejects `count<100`. A false zero is how a real source gets buried.

**Clear a whole FTP host with ONE request: pull its own `ls-lR.gz` or `locatedb.gz` and grep
offline.** Proven twice on 2026-08-19: `ftp.gwdg.de`'s 926 MB locatedb indexed an 8.8 GB tree,
and a 9.8 MB `ls-lR` gave 1.46M lines. Politer and more complete than crawling, and it turns a
zero into a proved zero.

**On a port-43 whois source, read PAST the record.** The terms of use follow the data, so a
reader that stops at the last field reports "no licence" on a source that explicitly prohibits
bulk access. `.nz` cost 7,586 EE that way; `.uk` says the same thing.

**A landing page's robots.txt does not govern the host its downloads sit on.** `www.fac.gov` is
`Disallow:` and permits everything; every Federal Audit Clearinghouse data file it links is on
`app.fac.gov`, which is `Disallow: /`. Read the robots.txt of the host in the download URL.

**A 403 wall is not always a refusal. Test it before recording one.** `.info` RDAP returned 403
on record 199 and on all 394 after it, unbroken, with `awselb/2.0`, 118 bytes and no
`Retry-After`. After ~12 minutes idle the SAME User-Agent got a genuine 404: it throttles above
~3 q/s and answers again after a rest. Honour it by slowing down, not by filing the host as
refusing us.

**Read the WHOLE robots.txt, not its head, and act on it before any other request.** A by-name
group can sit anywhere in the file and a permissive `User-agent: *` block at the top does not
override it. `tomocha.net` disallows ClaudeBot at line 51 of 61; reading ten lines cost a breach
and 1,623 EE. Refusing us by name: `cryptome.org`, `tbtf.com`, `www.openpgp.net`,
`ftp.nluug.nl`, `tomocha.net`, `mirror.aarnet.edu.au`, `ftp.aarnet.edu.au`, `www.potaroo.net`,
`ftp.sunet.se`, `ftp.surfnet.nl`, `www.math.upenn.edu`, `ftp.cc.uoc.gr`, `ftp.acc.umu.se`,
`www.floodgap.com`, `gopher.floodgap.com`, `leb.net`, `app.fac.gov` (upenn, uoc and umu name
Claude-User, Claude-Code, Claude-SearchBot, Claude-Web and ClaudeBot together; umu.se puts them
at lines 115-119 of a 6,238 B file whose FIRST group is a permissive `User-agent: *`; both
floodgap hosts are `Disallow: /` for ClaudeBot and www.floodgap.com also names `anthropic-ai`,
which closes the obvious host for any gopher or retro-internet lens before it is proposed).

**Host survival and robots refusal are correlated, so this will keep happening.** The old
mirrors that survive did so because a commercial or university operation kept paying, and mirror
operators are exactly the population now adding blanket or Claude-named `Disallow: /`. Five of
seven live large mirrors in one sweep refused; the two that allowed crawling carried only current
distro trees.

## Briefing agents

**Grep `sources.md` before briefing an agent, not after.** A lens described as untried when it
is closed three times over wastes the run and teaches the agent to distrust the brief.

**Grep does not reach the highest authority.** The reviewer's own words arrive in
`feedback-phase-*/` and `private/personal-context.md`, both git-ignored, so a repository-wide
search misses them; only the transcriptions in [ding/](ding/) are tracked.

## The round figures mixed two windows the moment a round opened mid-flight

Measured 2026-09-04. `round_figures.py` filters the registrable half by
`domain_year.verified_at >= round_since`, and takes the hostname half by reading the exported
`*_hostnames.txt` files, which carry no timestamps and hold everything net-new against the
baseline. While a round opens only when a new benchmark arrives those two agree, because the
baseline moves at the same instant. Round 9 opened at 15:00Z on 2026-09-04 **before** his feedback
on round 8, so for one afternoon the printed increment was 6,223 registrable records (round 9
alone) beside 8,620,331 hostname records (round 8 and 9 together), which reads as a collapse in the
registrable lane and an explosion in the other. Neither is true.

Both numbers are correct for what they measure and the label above them is wrong. Round 9's own
hostname contribution has to be queried from the store (`evidence.ingested_at >= round_since`,
through the export's own two predicates) and came to **886,216 records and 552,782.0436 EE**, while
the cumulative position against `merged260904` is **8,626,554 records and 4,815,266.2861 EE**.

**The rule: a figure is only comparable to another figure over the same window, and an exported
file has no window.** Quote the cumulative for a submission, because that is what he merges, and
query the store for what a session added. Fixing `hostname_increment()` to take a window means
giving it the store rather than the files, which is a change to make deliberately and not at the
end of a session.

## A collector's work is invisible until a loop reads it, and a converter counts as a collector

Five instances, four of them found on 2026-09-04 and three of them created that same day.

| when | what wrote | what nobody read |
|---|---|---|
| July | the VPS's CDX journals | 5,793 year-records sat remote for a day and a half |
| August | the RDAP sweep | 67 journals, ~12,000 EE, stranded on disk |
| 2026-09-04 | the suffix sweep, hostname half | writing since round 7, ingested only by hand |
| 2026-09-04 | the suffix sweep, registrable half | `cdx_suffix_convert.py` last run five weeks earlier |
| 2026-09-04 | the three body-URL lanes | usenet, maillist and Enron, all built that day, none in the loop |

**The shape is always the same and never announces itself.** Nothing fails, nothing warns, and
every measurement taken afterwards is correct about a store that is missing the work. The two
halves of the suffix sweep are the sharpest case: the same journal file, read by one loop line and
not by the other, for five weeks.

**And a converter is a collector for this purpose.** `cdx_suffix_convert.py` produced nothing new
from the archive, only a reshaping of bytes already held, and its absence from the loop cost
exactly as much as a collector's would.

The rule: **a lane is not finished when its ingest works, it is finished when a loop calls it.**
Add the `maintain.sh` line in the same commit that adds the ingest. Three of the five instances
above were written on the day the pattern was named, by someone who had just named it, which is
why this is a trap and not a reminder.

`just residual` is the check that finds them, but only for families with a documented ingest glob;
the fifth instance was invisible to it, because a brand-new lane has no glob to be too narrow.

## A malware alert on the fleet host, and why the corpus lane will keep causing them

2026-09-06. Microsoft Defender for Cloud raised `VirTool:JS/Obfuscator.HH` (category Tool) against
`/tmp/arkrun/zips/misc.writing.screenplays.moderated.mbox.zip` on the fleet host, SHA256
`8fba8919b55465cd9049db974dd2dc29d64ea01f65daa55a89736e3fd66592eb`.

**It was a Usenet newsgroup archive an agent downloaded, and the finding was correct.** Historical
mail and Usenet corpora carry the era's obfuscated-script spam as message content. The scanner was
right; the file really did contain what it said.

**Impact was nil, and both halves were checked rather than assumed.** It was never executed: a
Linux host, inert text inside an archive. And it could never ship: the extractor reduces every post
to `{item, year, text}` where `text` is a bare list of hostnames, so no message body leaves the
machine. The shipped `journals/usenet_*_items/` files were inspected directly to confirm it.

**The defect was the path, not the download.** `/tmp` is on the root disk, and the root disk is
exactly what agentless scanning images. Corpus bytes now go to `$ARK_PROBE_DIR` under
`/run/ark-probe`: tmpfs, so they live in RAM and never enter the disk image, mounted
`noexec,nosuid,nodev`, and the harness fails loudly if that path is not tmpfs rather than falling
back to disk.

**Two lessons that generalise past this incident.**

An instruction is not a control. The brief had told researchers to delete their downloads since the
lane was built; five directories were still there eleven days later.

**And a glob is not a control either.** The first fix swept `/tmp/ark_probe*`, `/tmp/ark_run_*` and
`/tmp/dnsbridge_run`. The offending file was in `/tmp/arkrun`, which matches none of them, and the
host also held `arkA_516190.py`, `ark_arm1b_512945.py` and `ark_full_513306.py`. Agents name their
own scratch, so enumerate a location you own instead of guessing the names they will pick.

**Triage next time, in this order.** Read the alert's File and Malware panes for the exact path and
detection name before touching the host. A corpus path plus a `JS/Obfuscator`, `HTML/` or era-worm
family is this class and is expected. Anything under `/home`, `/usr`, `/etc`, or a detection naming
a miner, backdoor or credential stealer, is not: check `auth.log` for non-publickey logins, `ss
-tulpn` for unexpected listeners, crontabs, and recently modified units, which on 2026-09-06 all
came back clean and took about ten minutes.

Two unrelated defects surfaced on the way: `clamav-freshclam` had been disabled since 2026-07-28,
because `NotifyClamd` pointed at a config for a clamd that is not installed and `Checks 0` is
rejected as "must be a positive integer". Signatures were six weeks stale. Both fixed, service
enabled, updating hourly.

## The store admits one process at a time, and a READER blocks the writer

DuckDB will not mix a read-only and a read-write connection to the same file across processes, so
`connect_read_only_patiently` is not the harmless choice it reads as. On 2026-09-07 a pricing probe
holding a read-only handle stalled both `ark ingest-hostnames` and the repair scripts, and the error
names the probe's own PID while suggesting read-only mode, which points the reader at the wrong fix:

    IO Error: Could not set lock on file "data/ark.duckdb": Conflicting lock is held in
    .../python3.12 (PID 4700) ... you would be able to open this database in read-only mode

So before anything that writes, stop the loops that ingest. The order that works is: stop
`pull_suffix_loop.sh` and `maintain.sh`, run the write, run `ark export` then `ark check`, then
restart the loops. `ark check` is a reader and conflicts with an ingest exactly the same way, which
is why the gate cannot be run while a collection loop is folding.

A long read against the live store is also worth avoiding for its own sake: it holds the lock for
its whole duration, and the collectors are what earn.

## A green test run through a pipe is not a green test run

`uv run pytest -q | tail -4` reports `tail`'s exit status, so a failing suite prints a plausible
summary and returns zero. On 2026-09-07 that hid `test_every_script_has_a_caller` for four commit
attempts, and the pre-commit hook, which redirects instead of piping, was the thing that caught it.
The hook's own comment warns about this, and rule 2 already says the gate never goes through a pipe.
Redirect to a file and read the file:

    uv run pytest -q > /tmp/pt.log 2>&1; echo "exit=$?"; tail -3 /tmp/pt.log

**What it was catching is worth knowing too**: every `scripts/*.py` must be named by the justfile,
the README, a docs page, another tracked file or the fleet list. A new script needs a caller or a
sentence about it in the page where a reader would look for it.

## Unledgered bytes are not lost records, and the raw tree will say they are

An audit of `data/raw` against `ingested_file` reports **129 GB unledgered** and that number means
nothing. Most of the tree is raw containers, Usenet zips and survey tarballs, which are read to
produce derived journals that are ledgered under their own names; the container never enters the
ledger and never should. Measured 2026-09-07: 129,101,381,838 unledgered bytes across all families,
of which the journal-shaped population (`*.jsonl.gz`, what the ingest commands actually consume
one-for-one) is **599,459,118**, a factor of 215 smaller.

So audit at the grain the ingest works at, and then price rather than count, because even a genuinely
unledgered journal is usually a superseded intermediate: the banked `usenet_addr` and `usenet_bare`
files are `*_candidates_cmp*` consolidations, and the older per-run journals beside them hold the
same pairs under different filenames.

This is the same shape as the stale-held-set trap in `laws.md`: a completeness audit that counts
files, bytes or rows will find a large number, and the only figure worth reporting is the anti-join
against the store, priced in EE.


## Sweep ORDER confounds any correlation between a parent's rank and its yield

Measured 2026-09-08, twice, on the same store. Joining the 41,122-parent ranking of 2026-09-07 to
the hostname-year rows every swept parent actually banked gives Spearman rho **+0.746** over 198
parents: the top 100 ranked parents paid a median of 3 rows each while ranks 5,000 to 20,000 paid a
median of 6,442, which reads as a ranker that is exactly inverted. It is not. The head of a ranking
is swept FIRST, so by the time a log records it again the parent is exhausted, its journal is
`already ingested, skipping`, and its rows are already held. The correlation measures sweep history,
not ranking quality.

Restricting to the 54 parents swept FRESH from the ranking that replaced it, none of them touched
before, gives rho **-0.655**: the ranking works. The same data, the opposite conclusion, decided
entirely by whether the sample was contaminated by earlier sweeps.

Two things to carry from it. Price a ranker only on parents it has never been used on, which in
practice means the window right after a re-rank. And read the DECAY while you are there: those 54
parents ran 8 to 17 MB of compressed rows at the head and 0.2 to 2 MB by rank 50, so a re-ranked
queue's dense head is about twenty parents deep and an hour of two clients walks it out.

## Equivalent-English per byte is not a constant, and a rich sample overstates the next hour

Three times on 2026-09-08, on three different lanes, a conversion measured on the best part of a
corpus was used to plan the rest of it, and each time the realised figure came in several times
lower:

| lane | measured on | realised | factor |
|---|---|---|---|
| domain-wide sweep | 565 EE/MB on the freshly ranked head | 53 EE/MB over the next 2.5 h | 10.7x |
| Usenet `alt` body URLs | 722 EE/GB on three mid-size groups | 134 EE/GB over the first 24 GB | 5.4x |
| domain-wide sweep, 2026-09-04 | 193,000 EE/client-hour on a dense head | 210 EE/hour two nights on | 919x |

The mechanism is the same in all three: a queue, a plan or a sample is ordered best-first, whether
deliberately or by the population's own skew, so whatever is measured early is drawn from the top of
the distribution. The rest of the corpus is the tail by construction.

Two rules follow. **Quote a conversion with the window it was measured over**, never as a property
of the lane. And **project the next hour from a measurement taken AFTER the head**, which in
practice means the second window rather than the first. The peak still matters, but as evidence
about the ordering: a rate that falls tenfold is the queue reporting that its head is walked, and
the answer to it is a re-rank, not a longer run.

## A restarted collector recycles its output names, and the ledger is what catches it

`sweep_alt_hierarchy.sh` numbered its output shards by batch, `batch1_shard_000` and so on, and the
batch counter starts at 1 every time the script runs. Stopped and restarted on 2026-09-08, its first
batch overwrote the first run's six `batch1_shard_*` files on disk.

**Nothing banked was lost, and the reason is worth knowing.** `ark ingest` keys the ledger on
`(source_name, file_name)` and stores the sha256, and a ledgered name whose bytes differ raises
`ledgered with different content (sha256 mismatch)` instead of logging "already ingested, skipping".
So the recycled name would have failed the next ingest loudly rather than dropping 15,183 hostname
rows quietly. Auditing the 42 ledgered shards against disk found exactly 6 changed and 36 the same,
which is how the blast radius was established before anything was touched.

Two rules. **A long-running collector's output name must carry a run id, not a counter that resets**,
and the fix here is a `date -u +%Y%m%dT%H%M%SZ` prefix. And when a name may have been recycled,
**audit the ledger's sha256 against the bytes on disk before ingesting or deleting anything**: the
answer is a list of files, not a guess. The cost of the incident was the six shards' first-run bytes,
which are regenerable because the plan and done-file record exactly which groups produced them.

## A proxy set overstates its admissible subset, and the factor reached 18.6x

The pattern already recorded above is about SAMPLES of a corpus. This is its sibling: a set that
stands in for the one you are allowed to claim.

`jeb_bush_anchored.jsonl.gz` is built as `anchored_all`, the union of hosts found in email addresses
and hosts found in explicit `http`, `https`, `ftp` or `www.` URLs. Priced at hostname grain on
2026-09-09 the union gave **5,999.2714 EE over 8,000 net-new host-years**. Re-parsing the artifact
and pricing the `url_body` lane alone, which is the only lane whose observation shows the host
serving web content, gave **322.4322 EE over 479**. The union overstates the admissible figure by
**18.6x**.

Nothing about the union was wrong as a measurement. It was wrong as a claim, because this project's
own rule says a `Received`, `Message-ID`, `From` or `List-*` host is a mail relay or a mailbox and
never a host that served a page. A mailbox host at hostname grain is worth nothing, and 94.6% of
that union's value was mailbox hosts.

**So price the lane you may ship, never the lane that is easy to read.** When a journal on disk is a
union, find out what it unions before quoting it: the register row for this lane had said "over all
472,949 anchored lines, then over the URL-vouched subset alone", which was the warning, and the
figure that survived into the register was the union's.


## A date range an API accepts and ignores hands back the wrong DECADE, at HTTP 200

Measured 2026-09-09 on `lists.apache.org`, and the shape generalises to any archive API that
parses one date form and shrugs at the rest.

The working form is `d=YYYY-MM`. Three others look fine and are not:

| request | what comes back |
|---|---|
| `mbox.lua?...&d=1999` | 200, a 13-message stub, not the year |
| `mbox.lua?...&d=1999-01-01~1999-12-31` | 200, the same 13-message stub |
| `stats.lua?list=*&domain=*&d=2001-12-01~2001-12-10` | 200, 15,001 messages whose epochs are in **2026-08** |

The third is the dangerous one. It is not a stub and not an error: it is a large, well-formed
response about the most recent mail in the archive, returned to a query that named ten days in
2001. An extractor pointed at it would have found real hostnames, dated them 2001 from the
`d=` parameter it asked for, and been wrong about every one.

**So verify a range filter against the DATA, not against the status code.** One line does it: read
the epoch or `Date:` of the first three records and print them as dates. The `searchParams` block
this API echoes back repeated the range faithfully, so even the server's own echo of the query is
not evidence that the query was applied.

## A wildcard listing that caps SILENTLY makes the busy half of a window look like the quiet half

Same host, same day. `stats.lua?list=*&domain=*&d=<month>` is the cheap way to enumerate an
archive: 72 requests covered 1996-2001 instead of one per candidate list-month. Its counts by
month:

| month | messages | lists |
|---|--:|--:|
| 2000-05 | 11,650 | 53 |
| 2000-06 | 13,707 | 52 |
| 2000-07 | **15,001** | 51 |
| 2000-12 | **15,001** | 72 |
| 2001-12 | **15,001** | 108 |

Every month from 2000-07 on returns exactly 15,001. That is a cap, not a plateau, and two things
follow: a busy list's message count is a floor rather than a count, and a QUIET list in a busy
month can be missing from the response altogether. Reading 2000-07 as "51 lists" would have
planned a smaller harvest than the archive holds, and nothing in the response says so.

**The fix was already in the same API and cost one request per list rather than per list-month.**
`active_months` returns a count for every month of one list's whole history, so it is exact and
the cap cannot reach it. A repeated round number at the top of a distribution is the tell: check
whether the largest value appears more than once before treating any of them as measurements.

## An ingest that finds no files reports success

`ark ingest-ietf-header-hostnames data/raw/ietf_header_items/` would have banked nothing and
said so only as a zero. `ingest_usenet_item_dir` globbed `*.jsonl.gz`, which is what the Usenet
and Apache pools write, and `collect_ietf_mail_archive.py` appends plain `.jsonl` shards. No
file matched, no exception was raised, and the command printed `files_seen: 0` beside a row of
other zeros. Every count an ingest prints is a count of what it DID, so nothing in the output
distinguishes "the corpus added nothing" from "the corpus was never opened". Read `files_seen`
before reading anything else, and pin the writer's suffix and the reader's glob to each other in
a test, because they live in different directories and move independently.

## Idempotence keyed on a file name freezes a file that grows

The same ingest marked a shard done by `(source, parent_dir/name)`. The pools write a shard once,
so that key was exactly right for them. This collector appends every month of a list to that
list's ONE shard, so the first reading would have marked `snmpv2.jsonl` done at whatever it held
that minute and every month swept afterwards would have been skipped for ever, silently, with the
shard sitting on disk holding the rows. The digest was already being computed and stored; it just
was not being compared. It is compared now, and a changed digest re-reads the file, where the
rows already banked land on `INSERT OR IGNORE`. Ask of any idempotence key whether the thing it
names can change after it is first seen.
