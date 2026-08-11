# Open approvals: which source classes may date a year

**What this file is.** The pipeline can measure a source without help. It cannot decide whether that
source's records belong in the annual files, because that is a judgement about what counts as proof.
The thing being distrusted in an unattended run is exactly **the agent's reasoning about its own
finds**, so an argument written by the agent is the least trustworthy artifact here. This file is where
a human classifies a source class, and `src/ark/approvals.py` **enforces** the answer rather than
trusting anyone to remember it.

**How the gate behaves.** `ark ingest` refuses, before it even opens the database, any source whose
evidence type is master-eligible and whose class is not approved below. Candidate-only evidence passes
without a lookup: it can never date a year, the reviewer asked for the pool to be as large as
practicable, and gating it would stall collection for no gain. **An unapproved source is not
quarantined inside the store; it was never written to it.** The journal waits on disk and nothing is
lost.

**How to decide one, in about two minutes.** Each request below carries a link to the source, a
**seeded-random** sample of real records with a live link each, and the measured figures. Open two or
three of the sample links. If the page shows that domain with that date, the class is sound. **Do not
read the agent's argument as evidence**; it is there to be checked, not believed.

**Set exactly one `Decision:` line per request:**

| value | meaning |
|---|---|
| `pending` | nobody has looked. Ingest refuses. |
| `master` | approved: its rows may date a year and enter the annual files. |
| `candidate-only` | collect it, but its rows may never date a year. |
| `rejected` | do not ingest at all, and do not re-request without new external evidence. |

`rejected` binds: the gate refuses it and the request generator will not re-open it, because an agent
that forgets a rejection re-proposes it a week later.

---

## Approved before this mechanism existed

These were classified by the reviewer merging and crediting the round that contained them, or by Ivo by
name and date. They are recorded here so the gate has an answer for them, **not** re-argued: the
authority is the merge or the named decision, and it is cited per entry.

### afnic_fr / whois_creation

- ingest specs: `afnic_fr`
- authority: phase 2; the registry documents that crDate resets on re-registration, quoted in sources.md

Decision: master

### arquivo_ia / cdx_timestamp

- ingest specs: `arquivo_ia`
- authority: phase 1, merged and credited 2026-07-27

Decision: master

### arquivo_roteiro / cdx_timestamp

- ingest specs: `arquivo_roteiro`
- authority: phase 1, merged and credited 2026-07-27

Decision: master

### attrition_defacement / artifact_listing

- ingest specs: `attrition_dated`
- authority: phase 5, classified by Ivo 2026-08-10 after the licence question was resolved

Decision: master

### early_web_cdx / cdx_timestamp

- ingest specs: `early_web`
- authority: phase 1, merged and credited by the reviewer 2026-07-27

Decision: master

### enron_email / dated_directory

- ingest specs: `enron_dated`
- authority: phase 4, merged and credited 2026-08-10, and takes the corroboration split

Decision: master

### ia_cdx_bulk / cdx_timestamp

- ingest specs: `cdx_snapshot`
- authority: phase 1 onward, the reviewer's own named route (SPEC VI)

Decision: master

### internet_scout / dated_directory

- ingest specs: `internet_scout`
- authority: phase 1, merged and credited 2026-07-27

Decision: master

### isc_survey / artifact_listing

- ingest specs: `isc_survey`
- authority: reviewer confirmed in writing 2026-07-24 that a dated DNS survey may enter the annual files directly

Decision: master

### maillist_archive / dated_directory

- ingest specs: `maillist_dated`
- authority: phase 4, merged and credited 2026-08-10, and takes the corroboration split

Decision: master

### ncsa_whats_new / dated_directory

- ingest specs: `ncsa_whats_new`
- authority: phase 1, merged and credited 2026-07-27

Decision: master

### nypw_firstcdx / cdx_timestamp

- ingest specs: `nypw_firstcdx`
- authority: parser retained and wired, but the source was REJECTED on measurement: 53 net-new domains over 6.28M lines

Decision: rejected

### odp / artifact_listing

- ingest specs: `odp`
- authority: phase 1, merged and credited 2026-07-27

Decision: master

### page_directory / dated_directory

- ingest specs: `expansion_directory`
- authority: phase 1; the curated-catalogue assertion is made per seed and on the record (SPEC IV.i)

Decision: master

### rdap_snapshot / whois_creation

- ingest specs: `rdap_snapshot`
- authority: phase 4, merged and credited 2026-08-10; SPEC III.6 allows a creation date for the year it falls in

Decision: master

### rtfm_faq / dated_directory

- ingest specs: `rtfm_dated`
- authority: phase 4, merged and credited 2026-08-10, and takes the corroboration split

Decision: master

### trade_press / dated_directory

- ingest specs: `tradepress_dated`
- authority: phase 4, merged and credited 2026-08-10, and takes the corroboration split

Decision: master

### tucows_catalogue / dated_directory

- ingest specs: `tucows_dated`
- authority: phase 4, merged and credited 2026-08-10, and takes the corroboration split

Decision: master


### ukwa_link_source / link_source

- ingest specs: `ukwa_link_source`
- authority: reviewer confirmed in writing 2026-07-24: host/link graph rows may serve as direct annual evidence where the year is explicit

Decision: master

### usenet_address / dated_directory

- ingest specs: `usenet_addr_dated`
- authority: phase 4, merged and credited 2026-08-10, and takes the corroboration split

Decision: master

### usenet_announce / dated_directory

- ingest specs: `usenet_dated`
- authority: phase 4, merged and credited 2026-08-10, and takes the corroboration split

Decision: master

### usenet_bare / dated_directory

- ingest specs: `usenet_bare_dated`
- authority: phase 4, merged and credited 2026-08-10, and takes the corroboration split

Decision: master

### uucp_map_creation / whois_creation

- ingest specs: `uucp_creation`
- authority: phase 4, merged and credited 2026-08-10

Decision: master

### uucp_map_registry / artifact_listing

- ingest specs: `uucp_listing`
- authority: phase 4, merged and credited 2026-08-10

Decision: master

---

## Decided, with the request that was reviewed

### udrp_proceedings / artifact_listing

- ingest spec: `udrp_proceedings`
- source: https://www.icann.org/udrp/proceedings-list.htm
- journal: `data/raw/udrp/udrp_proceedings.jsonl.gz`
- agent's dating claim: a proceeding exists only because the domain was registered and a complaint was filed against it, and the commencement date is printed in the record
- nothing in the closed register resembles this by name.

**Check these before reading anything else.** Seeded-random sample, seed `20260811`, so it is reproducible and was not chosen by the agent:

| record | domain | year claimed | open this |
|---|---|--:|---|
| `NAF FA0094335` | `statefarmdirect.com` | 2000 | https://www.icann.org/udrp/proceedings-list.htm |
| `WIPO D2000-0599` | `teliasystems.com` | 2000 | https://www.wipo.int/amc/en/domains/decisions/html/2000/d2000-0599.html |
| `WIPO D2001-0044` | `christiesimages.net` | 2001 | https://www.wipo.int/amc/en/domains/decisions/html/2001/d2001-0044.html |
| `WIPO D2000-0862` | `mcgraw-hill.org` | 2000 | https://www.wipo.int/amc/en/domains/decisions/html/2000/d2000-0862.html |
| `WIPO D2000-1713` | `tatawestside.com` | 2000 | https://www.wipo.int/amc/en/domains/decisions/html/2000/d2000-1713.html |
| `WIPO D2000-1497` | `ge-points.com` | 2000 | https://www.wipo.int/amc/en/domains/decisions/html/2000/d2000-1497.html |

**Measured against the live store**, by program, not by the agent:

| | |
|---|--:|
| records in the journal | 8,972 |
| distinct (domain, year) | 8,923 |
| over distinct domains | 8,892 |
| already held by the store | 8,923 |
| absent from the store | 0.0% |

**What was at stake when the decision was taken**, measured 2026-08-11 before the ingest:

| decision | net-new pairs | equivalent-English |
|---|--:|--:|
| `master` (self-dating, no split) | **7,714** | **4,708.9** |
| `master` (taking the corroboration split) | 1,471 | 914.1 |
| `candidate-only` | 0 | 0.0, and the names still grow the pool |

Mean equivalent-English weight of the net-new part: 0.6214. Contributed **7,837 pairs and 4,763.1808
equivalent-English** on ingest, the difference being pairs the store acquired between the measurement and
the ingest.

The request block above was generated **after** the ingest, so its own counterfactual read zero: nothing
was net-new any more. That is why `request_approval.py` now refuses to build a request for a class the
store already holds evidence for.

**Reasons a reader should refuse**, listed by the agent against its own request:

- the sample links do not show that domain with that date;
- the year is inferred from something other than the record itself;
- the hostname comes out of prose rather than a structured field, in which case `candidate-only` or a split-taking spec is right, not `master`;
- the closed family named above is the same population under another name.

**Decided by Ivo, 2026-08-11**, in these words: "Treated as master artifact-listing sounds fine to me,
just make sure to document and reason about the decision and ingest carefully as you described." The
reasoning, the argument against it and the three mitigations are in
[ADR-002](ADRs.md). The counterfactual above reads zero because the source was already
ingested by the time this request was generated; at the time of the decision it was **7,714 net-new
pairs and 4,708.9 equivalent-English** under the `master` reading against 1,471 and 914.1 under the
split.

Decision: master

---

## Pending requests

Nothing pending.
