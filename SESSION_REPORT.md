# Session report: 1 August 2026, 02:00 to 11:00 CEST

For Ivo. Everything here was measured against `data/ark.duckdb`, and the scripts that produce each
figure are committed so the numbers can be re-derived rather than believed. Branch `phase-3`,
nothing pushed.

---

## 1. Where the project stands

| | at 02:00 | at 11:00 | change |
|---|--:|--:|--:|
| net-new (domain, year) pairs vs merged260730 | 32,698 | **PLACEHOLDER_PAIRS** | **PLACEHOLDER_DELTA** |
| candidate pool | 5,583 | PLACEHOLDER_CAND | |
| English-verified pairs | 0 | PLACEHOLDER_ENGLISH | |
| tests | 204 | PLACEHOLDER_TESTS | |

Per year:

    PLACEHOLDER_YEAR_TABLE

All nine integrity checks pass. `ruff check`, `ruff format --check` and `pytest` all clean.

---

## 2. What was blocking us, and what was built

Feedback v3 section 6 changed the rules: a domain now enters an annual file **only** if it belongs
to an English-language website, or one where English is more than 50% of reliably classified body
text, judged at website level from **archived page body text** rather than from the domain spelling
or its TLD. That is an admission criterion, not a filter, so before this session the next submission
had zero admissible additions no matter how many pairs the engines collected.

Ding also writes that his own language table is "a provisional aggregate estimate ... using a
TLD-stratified Common Crawl 2024-10 page-language prior and is not a per-domain historical-language
verification", and that future reports "must replace the provisional estimate with archived-content
evidence". So this is the one piece of infrastructure he has asked for in writing.

### The English-website verification engine

`src/ark/language.py`, four CLI commands, 29 unit tests, committed as `f4260d9`.

    uv run ark lang-targets            # the (domain, year) work list
    uv run ark lang <targets> -n 400   # classify from archived body text
    uv run ark ingest-lang <journal>   # fold verdicts into domain_language
    uv run ark lang-report             # netnew_english/ + the section 6.1 table

**The design decision that matters: language is not evidence.** Every existing `evidence_type`
answers "did this domain exist in this year". A language verdict answers "what was this website in
this year", which is orthogonal, and a domain can be perfectly evidenced and still inadmissible.
Adding an eighth evidence type would have put a non-existence claim inside a taxonomy that
`MASTER_TYPES`, the schema CHECK and four integrity checks all read as proof of existence. Verdicts
go in a new `domain_language` table instead, keyed on the same (domain, year) pair as everything
else.

**Every verdict stores the exact snapshot URLs it read.** That column is the whole difference
between this and a TLD prior: a reviewer can refetch what we classified and recompute the answer.

Verified live: `bbc.co.uk` 1999 returns `english` at share 1.0 from three distinct sampled pages;
`lemonde.fr` 1999 returns `other`, share 0.0, top other language `fr`.

---

## 3. The measurement that changed the plan

**Only two thirds of our additions can be classified at all**, and that is a ceiling no amount of
crawling moves. Per net-new pair, does any `cdx_timestamp` evidence exist for that exact
(domain, year)? If yes the archive holds an in-year capture and there is body text to read.

    year     pairs   capture-backed    share
    1996     4,994               20     0.4%
    1997     3,534                1     0.0%
    1998     6,029            5,216    86.5%
    1999       696               41     5.9%
    2000     9,702            9,075    93.5%
    2001     7,743            7,472    96.5%
    TOTAL   32,698           21,825    66.7%

**The plan's priority order was exactly backwards.** It said classify 1996 and 1997 first, because
feedback section 5 puts them closest to the completeness threshold. Correct about completeness,
wrong about this engine: those two years are 0.4% and 0.0% capture-backed. The first calibration run
spent its whole budget on 1996 and returned 74 answers, **every one `undetermined` with zero
captures found**, exactly as the table predicts. The work list now orders capture-backed pairs first.

This also gives the open question for Ding a number. **10,873 of the original 32,698 additions
(33.3%) have no archived capture in their evidenced year**, because their evidence is a registry
creation date or a DNS survey line. For 1996 and 1997 that is 99.6% and 100.0%. Does such a pair
become "undetermined" and leave the annual files, even though its existence that year is well
evidenced? That decides whether the RDAP and AFNIC routes have any future value. Draft below.

---

## 4. The largest result: Usenet announcement archives

Giganews donated its Usenet archive to the Internet Archive. Announcement and commerce groups carry
a posting date beside the URLs in each message, and **the date is intrinsic to the artifact rather
than recovered from a crawl**. That is precisely the gap the measurement above exposed: a dated post
reaches the years the archive never captured.

PLACEHOLDER_USENET_TABLE

**The admission rule is the safety argument.** The post date is trustworthy; the URL beside it is
human-typed, and 35.4% of never-before-seen names are within a single edit of a name the store
already holds. The corpus visibly contains `weddinqnetwork.com` and `dmjbuisness.co.uk`. So the same
split `expand.py` applies to archived directory pages:

- a domain **another source already places in an annual file** is real and only its year is open, so
  the post dates it, as `dated_directory` with the Message-ID as the auditable evidence value;
- a name appearing **only** in Usenet is written as `link_target` and goes to the candidate pool to
  earn its own evidence.

The corroboration test is "appears in `domain_year`", not "appears in `domain`", because the latter
includes the candidate pool and a typo recorded by an earlier round would corroborate itself.

Usenet is its own provenance lineage. The corpus has no common ancestor with any web crawl, so a
pair confirmed by both Usenet and a Wayback capture is genuine cross-lineage corroboration rather
than the Internet Archive agreeing with itself.

---

## 5. Two sources rejected, and why that is worth as much

**NYPW first-capture index: estimated 27,276 net-new domains, measured 53.** The estimate compared
NYPW's *registered domains* against *raw hostname lines* from the *phase-1* baseline. Two compounding
unit errors, both inflating. Measured against the store: 2,354,914 in-window domains of which all but
**53** are already held, a 99.998% overlap, which is exactly what a sample of the Internet Archive's
own CDX should look like against a baseline already drawn from it. Two minutes of measurement
avoided a 19.35 GB download of the TimeMaps sibling.

**Australian Web Archive: 0 of 60 sampled domains had an in-window capture.** Worth keeping the
endpoint correction anyway: `webarchive.nla.gov.au/awa/cdx` still serves an anti-bot challenge but
**`web.archive.org.au/awa/cdx` answers normally**, so our `sources.md` rejection was stale. That is
exactly what feedback section 4 means by revisiting blocked sources. The pool looked strong (29,595
PANDORA domains in no annual file) and returned nothing in window.

Both are recorded in `docs/sources.md` with the reasoning, because section 4 asks for previously
unavailable sources to be revisited and that only works if the failure was written down.

---

## 6. Defects found and fixed

- **The rate governor could not see a refusal.** The first language run sent up to 4 requests per
  pair at 4 workers, and after ~400 requests `web.archive.org` began refusing TCP connections while
  ping and DNS stayed healthy. The real defect was not the pace but the blindness: a refused
  connection is status 0, which `RateGovernor` did not treat as a throttle, so the run kept dialling
  at full speed at the moment it should have stopped. Status 0 now backs the pace off, `ark lang`
  carries a circuit breaker at 25 consecutive failures, and `--min-delay` is explicit because for a
  three-requests-per-pair engine the floor bounds the load, not the worker count.
- **A Usenet date format was silently discarding 92% of the corpus.** The Giganews donation rewrote
  many `Date:` headers as a bare `YYYY/MM/DD`, which `parsedate_to_datetime` rejects: 21,346 of
  23,282 messages in one group. Before the fix the route measured 913 pairs and nothing before 2000;
  after it, 6,885 across all six years.
- **Out-of-window and unreadable dates were one counter.** They call for opposite responses, and
  `alt.www.webmaster` made the point: 170 MB, one pair, because the group is entirely 2006 to 2013.
  Group size does not predict in-window content.
- **`init_db` split the schema on semicolons inside comments**, so a semicolon in new explanatory
  text cut a `CREATE TABLE` in half. Comment lines are stripped before the split now.
- **A test caught a missing provenance lineage** on a newly added source, which would have inflated
  the independent-corroboration count. That check earned its keep.

---

## 7. What is still running

PLACEHOLDER_RUNNING

---

## 8. Draft question for Ding, to send after the exam

> The English-website standard is defined per website per year from archived body text. We have
> measured how much of our own contribution that reaches: of our current additions against
> merged260730, PLACEHOLDER_SHARE have an archived capture in the evidenced year and can therefore
> be classified from page text. The remainder are evidenced by a registry creation date or a
> national DNS survey record, and the Internet Archive simply holds no capture of those sites in
> those years. For 1996 and 1997 this affects 99.6% and 100.0% of our additions respectively.
>
> Should such a pair be recorded as "undetermined" and kept out of the annual files, even where its
> existence in that year is well evidenced by the registry? Or may an evidenced pair with no
> classifiable capture be admitted on other grounds, for example where the registry is a national
> one for an English-speaking country?
>
> The answer decides how much of the 1996 to 1999 window is reachable at all under the new rule, and
> those are the years where section 5 says completeness is closest.

---

## 9. Where to pick up

1. **Keep sweeping Usenet.** Eight groups of 302 shortlisted, and marginal yield was still high at
   the eighth. Downloads are the bottleneck, not processing. Choose groups by whether they existed
   in window rather than by size.
2. **Let the language engine finish the capture-backed list.** 21,825 pairs at the measured rate is
   roughly 58 hours of wall clock, so it wants a long unattended stretch rather than a night.
3. **CDX-verify the candidate pool.** It has grown to PLACEHOLDER_CAND, most of it from Usenet, and
   every verified candidate becomes a net-new domain rather than just a net-new year. Net-new
   *domains* is still 0, and this is the route that changes that.
4. **Send the question above** before the next submission, since it changes what is worth running.

Operational detail is in `READFIRST.md`, decisions in `docs/notes.md`, the plan in `plan.md`, and
per-source assessments including every negative in `docs/sources.md`.
