# Internet Digital Ark: round [ROUND]

Additions to the 1996-2001 annual lists, measured against `[BASELINE]`. Every figure is generated from
the evidence store, so no table here can disagree with the files shipped beside it.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | [BASELINEPAIRS] |
| 2. Equivalent-English total | [EEBASELINE] |
| 3. Increment | **[TOTAL]** records |
| 4. Equivalent-English increment | **[EE]** |
| 5. Equivalent-English growth rate | **[EEGROWTH]** |

Lines 1 and 2 are your `[BASELINE]` totals, unchanged, since this increment is not yet merged. The
increment covers [UNIQUE] distinct domains, of which **[NEWDOMAINS] appear in none of the six baseline
files in any year**.

[PER_YEAR_TABLE]

[CUMULATIVE]

## 2. Counting unit, normalisation and what gets dropped

**The counting unit is the (registrable domain, year) pair**, deduplicated on the lowercased line
within each year, which is your own unit. Every name from every source passes through one function
before reaching the database, so the dedup key is identical across sources.

**Normalisation, in order:** percent-decode, trim, lowercase; strip scheme, `//`, path, query,
fragment, userinfo and port; strip stray leading and trailing `.` and `,` but never a hyphen, which
would alter the name; then reduce to the registrable domain with a **pinned Public Suffix List** plus
historical ccTLDs, so `ci.anchorage.ak.us` becomes `anchorage.ak.us` while `k12.ak.us` is refused as a
public suffix in its own right. **Validity:** a line is dropped if it is empty, an IPv4 literal, a
reverse-DNS zone, syntactically invalid, carries no known public suffix, is a bare public suffix, or
has an invalid character in the registered label. **Salvage** is the same operation applied to a dirty
line, so a URL or mail address is reduced rather than discarded.

| across [INGESTRUNS] ingest runs | records | | |
|---|--:|---|--:|
| raw lines read | [RAWLINES] | **salvaged** by normalisation | **[CORRECTED]** |
| staged records | [STAGEDRECORDS] | **rejected** as invalid | **[REJECTED]** |
| outside 1996-2001, never eligible | [OUTOFWINDOW] | | |

Reject reasons over the 1,299,177 dropped lines retained in the shipped audit CSVs: **IP address
95.41%**, no known public suffix 2.92%, invalid hostname syntax 0.95%, bare public suffix 0.63%,
invalid character in the registered label 0.09%. The IP share is expected: link graphs and server logs
name hosts by address, and an address is not a domain under your counting unit.

## 3. What dates each year, and the standard applied to each category

[ROUTES_TABLE]

**Both routes are self-dating and take no corroboration split**, being records of the thing itself
rather than a description of it. The registry route is deliberately under-claimed: **a creation date
writes its own year and no other**, per your rule 6, so a domain created in 1997 and live in 2001 earns
1997 here and must earn the other four from a capture.

**The standard, by category.** Master-eligible classes are `[MASTERTYPES]`, each a machine-written
record asserting a state at an instant the artifact itself stamps. Anything a human typed is
candidate-only until another source dates that domain first, and `link_target` never dates a year at
all. A master-eligible class also needs a written human decision before it can assign a year, so
nothing enters the annual files on an agent's judgement.

**Structurally enforced.** `domain_year.evidence_id` is `NOT NULL` with a foreign key into
`evidence`, so no code path can write a year without naming the observation behind it, and twelve
invariants check that before every commit and again inside the archive. Tested by accident this round:
the candidate pool accumulated 575,417 strings under namespaces that never allowed arbitrary
registration and **not one reached an annual file**.

## 4. Source contributions

[EE_SOURCE_TABLE]

Every row is master-eligible. Separately, **[CANDIDATES] domains carry no year-specific evidence** and
ship as `candidates.txt`, kept out of the annual files as you asked.

[ADMITTED_THIS_ROUND]

## 5. Archive execution

[CDX_TABLE]

[CDX_FAILURES]

## 6. Discovery method, and what this round learned

Collectors hold absolute epoch deadlines and outlive any session; the agent hunts and prices sources
and never writes a year itself. The gains came less from new hosts than from four measurements that
changed which sources are worth opening. `experience-summary.md` carries the full working.

- **Aim at 2001, not 1996.** The store holds **6,708,320 domains at 2000 missing 2001**, against
  103,953 for the 1996-to-1997 gap. `P(store lacks 2001 | domain held)` is 0.611 `.com`, 0.653 `.net`,
  0.568 `.org`, 0.309 `.uk`, so **one already-held `.com` name in a 2001-dated artifact is worth 0.386
  equivalent-English and about 2,600 such names clear 1,000**: 32x below the curated-directory floor,
  which was measured on artifacts dated in years already covered.
- **Novelty is a cost; the screen is held AND missing this year.** So **crawling kills discovery but
  not completeness**: a 2000-dated blacklist paid 18 equivalent-English because its names already
  carried 2000, while the 2001 edition of the same list paid **10,736**, being 84.8% known but only
  57.9% held at 2001.
- **Compute headroom from the adjacent year only.** A gap between a domain's last held year and the
  target is evidence of death, not of missing data: of 9,680 `.us` names missing 2001, **6,948 were
  last seen in July 1997**. "Held any year, missing Y" is contaminated; "held Y-1, missing Y" is not.
- **Density and authority are two independent screens.** One parliamentary corpus yielded 5 URLs in
  3.26M words; grey literature passes that screen at **221x the rate** and then fails the second at
  93.0% already held, because programme reports print the URLs of institutions we already hold.

**The method that generalised** was asking what *kind* of artifact an organisation of that era
produced, then what else sat in the same directory: that found the `.ie` register, the InterNIC 1997
zone files, the JISC UK per-year index and a US Domain delegation list. **Negative results are
first-class.** [DATASETS_SEARCHED] Every rejected source is in `sources.md` with its evidence type,
location, timestamp, extraction method and the measurement that closed it.

## 7. Limitations, and whether further expansion is worthwhile

**Both routes err toward under-claiming.** A capture proves presence and never absence, so a year
with no capture is unevidenced rather than empty, and a creation date attests one year only. Neither
can invent a year; the mistake they can make is omission. **Three limits no amount of work fixes.** A
material share of archive requests fail at transport level rather than with a status code, which is
throttling seen from the other side of the socket. The corroboration split asks whether a domain is
dated somewhere, never whether a mention was genuine, so invented-but-plausible prose is the one shape
it does not stop, which is why both routes here are self-dating. And host survival correlates with
refusal: the mirrors that still run do so because an institution kept paying, and those operators are
the population now adding blanket `Disallow` rules.

**Worth expanding, in order.** Bulk dated corpora first, at two orders of magnitude more net-new pairs
per megabyte than prose. Registry datasets publishing creation dates second, the route that reaches
2001 where archives are thin. Re-auditing material already on disk third. **Not worth expanding**, each
closed with numbers this round: academic repositories and DOI datasets, national web-archive indexes,
preserved CD-ROM media, trade directories of internet businesses, and prose corpora of any kind.

## 8. The merge, the overlap and the reconciliation

[MERGE_RECONCILIATION]

## 9. Reproduction, and the four requested artifacts

`README.md` in the archive gives the order. `masters/` and `additions/` hold the merged annual lists
and this round's net-new records, `candidates.txt` the undated names, `provenance/*.parquet` every
(domain, year) joined to the evidence row justifying it. [REPRODUCTION_RESULT]

| | asked for | where it is |
|---|---|---|
| **D1** | runnable code, dependencies, instructions | `source/source.tar.gz` at the commit in `MANIFEST.txt`, with `pyproject.toml` and `uv.lock`; its `README.md` names what every command should print |
| **D2** | experience summary | `experience-summary.md`, distilled from `sources.md`, which carries every rejection with the measurement that closed it |
| **D3** | merge and dedup code, overlap, reconciliation | section 8, `source/scripts/merge_against_baseline.py`, output in `audit/` |
| **D4** | runnable metric code and its explanation | `equivalent_english_domain_calculator/`, your own program vendored unmodified, explained in `metric-explained.md` |

`verify.sh` checks all four inside a fresh extraction, so none can ship unmet.
