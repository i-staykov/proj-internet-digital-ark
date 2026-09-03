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
