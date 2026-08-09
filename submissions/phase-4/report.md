# Internet Digital Ark: round report

Additions to the 1996-2001 annual domain lists, measured against `merged260802`.

**Every figure in the tables** is generated from the store by `scripts/report_figures.py` and
substituted by `scripts/fill_report.py`, so a table here cannot drift from the shipped files. The
handful of one-off measurements quoted in the prose of sections 2 and 3 are not regenerated per round;
each describes a specific run and is recorded with that run in `sources.md`.

---

## 1. What this round adds

| | |
|---|--:|
| Net-new (domain, year) pairs | **945,312** |
| Over unique domains | 683,868 |
| Domains absent from the baseline in every year | **75,883** |
| Equivalent-English added | **602,465.6** |
| Growth on the 5,622,984.6 baseline | **10.7143%** |
| Mean equivalent-English weight per pair | 0.6373 |

| Year | merged260802, this counting unit | Additions | Capture-backed |
|---|--:|--:|--:|
| 1996 | 623,012 | 25,301 | 72 (0.3%) |
| 1997 | 1,281,371 | 59,156 | 1,499 (2.5%) |
| 1998 | 970,963 | 176,953 | 17,982 (10.2%) |
| 1999 | 1,537,182 | 260,439 | 26,730 (10.3%) |
| 2000 | 1,555,211 | 251,325 | 50,827 (20.2%) |
| 2001 | 2,817,881 | 172,138 | 38,383 (22.3%) |
| **Total** | **8,785,620** | **945,312** | **135,493 (14.3%)** |

## 2. Where the additions come from

| Source | What carries the date | Evidence type | Admissible | Net-new pairs | Equivalent-English |
|---|---|---|---|--:|--:|
| `usenet_announce` | post date of the announcement | `dated_directory` | master | 585,175 | 348,669.9 |
| `ia_cdx_bulk` | Wayback capture timestamp | `cdx_timestamp` | master | 116,463 | 96,301.6 |
| `usenet_address` | post date of the message carrying the address | `dated_directory` | master | 107,304 | 64,960.8 |
| `rdap_snapshot` | the registry's own `registration` event date | `whois_creation` | master | 48,394 | 29,023.4 |
| `usenet_bare` | post date of the message carrying the address | `dated_directory` | master | 42,139 | 28,460.3 |
| `uucp_map_registry` | posting date of the registry's generated dump | `artifact_listing` | master | 23,678 | 19,806.2 |
| `rtfm_faq` | the FAQ's revision header | `dated_directory` | master | 5,166 | 4,084.2 |
| `uucp_map_creation` | the registrar's own `approved:` date | `whois_creation` | master | 4,793 | 4,009.3 |
| `enron_email` | the message `Date:` header | `dated_directory` | master | 5,134 | 3,241.9 |
| `trade_press` | the issue cover date | `dated_directory` | master | 3,740 | 2,401.9 |
| `maillist_archive` | the message `Date:` header | `dated_directory` | master | 1,458 | 833.2 |
| `isc_survey` | survey run date | `artifact_listing` | master | 1,857 | 665.2 |
| `page_directory` | capture timestamp of the archived catalogue page | `dated_directory` | master | 11 | 7.7 |
| **Total** | | | | **945,312** | **602,465.6** |

**All 13 are master sources, so all 945,312 pairs are admitted to the annual files.** None of them is candidate-only. Names may pass through the candidate pool on the way in, and this round many did, but a pair is only counted once a master source dates it.

**What "admissible" means here.** A source may back an entry in an annual file only if the evidence it
produces is one of the master types: `artifact_listing`, `cdx_timestamp`, `dated_directory`, `link_source`, `whois_creation`. Anything else, in practice a bare outbound link,
is `link_target` and can never assign a year; it goes to the candidate pool and ships separately in
`candidates.txt`. Two of the integrity invariants enforce this on every build: `no_candidate_leakage`
finds any annual assignment backed by candidate-only evidence, and `every_pair_has_master_evidence`
finds any assigned pair lacking a master-eligible row for that exact year. Both currently report zero.

The four master types in this round divide into two kinds, and the difference is worth one paragraph
because it is the difference in how much each pair rests on.

**Self-dating artifacts, where the record itself is the authority.** `whois_creation` is the
registry's own registration event. `cdx_timestamp` is a capture the Internet Archive actually holds.
`artifact_listing` is a dated registry or survey file that enumerates names. For these the date is a
property of an authoritative record, so nothing further is needed and nothing further is done.

**Addresses printed inside a dated artifact**, which is `dated_directory`: a magazine page, a Usenet
post, a FAQ, an email. The artifact's date is sound, but a human typed the address, so these take one
extra filter described below.

Each source is named below by the **artifact that carries the date**, because that is what decides
what a (domain, year) pair rests on.

### `rdap_snapshot`: registry creation dates, asked of the candidate pool

The registry's own `registration` event, read from the authoritative RDAP server for each TLD rather
than through a redirector. It is one of the self-dating types above: the registry is the authority on
when a name was created, so the record stands on its own.

What is new is not the source but the **population it was asked about**. Earlier rounds pointed
creation-date lookups at domains that already held a year, hunting a missing year beside a held one.
This round pointed them at the candidate pool instead, the names held with no year at all. A creation
date landing in window gives such a name its **first** year, which makes it a net-new domain and not
merely a net-new pair, and that is why this round's net-new domain count rose so much faster than its
pair count.

Two limits, both deliberate. A creation date supports the annual file for the year it falls in and
**nothing later**: it does not establish that the domain remained registered afterwards. And a domain
whose creation date falls outside 1996-2001 attests nothing and stays in the candidate pool.

### `usenet_bare`: the addresses written without `www.`

Same corpus again, no new downloads. The extractor read `http://` URLs and hosts beginning `www.`,
and refused a bare `foo.com` on the grounds that in running prose such a string is more often a
company name, a file name or half an email address than a website. Bare addresses are common in
the corpus, so that refusal was expensive.

What makes reading them safe is the corroboration rule below: a string that is really a file name is
not a domain any independent source has attested, so it cannot reach an annual file. That rule does
most of the work here. The pass found 601,738 candidate pairs in the corpus; 269,773 of them were
already asserted by the two Usenet sources above, and 36.3% were uncorroborated and went to the
candidate pool. **The table above reports only what survived both filters**, which is the figure this
source is worth. Quoting the 601,738 would have overstated it by more than an order of magnitude.

### `usenet_address`: the addresses the extractor never read

Same corpus as `usenet_announce`, no new downloads. The message parser read `http(s)` URLs, bare
`www.` hosts and the `From:` header, and therefore never saw `ftp://` addresses, `mailto:` links, or
addresses typed in running text. In 1996 a vendor often published an `ftp://` address where a later
one would publish a web address. The date is the post date, exactly as for `usenet_announce`, which
this collection already accepts.

### `uucp_map_registry` and `uucp_map_creation`: the UUCP maps

The strongest provenance added this round. `comp.mail.maps` carried the Canadian registry's own
machine-generated dumps, each declaring itself *"Automatically generated from a .CA domain
registration form"* and regenerated from the live registration database at posting time. Entries
carry the registrar's own `approved:` date. This is a registry record of the same class as the AFNIC
`.fr` file already in the collection, not a typed URL, which is why it is split into a listing date
and a creation date rather than treated as free text. Hand-maintained map files in the same group are
**not** treated this way: they are demoted to candidate-only.

### `enron_email`: the FERC-released corporate mail corpus

517,401 business messages released by the Federal Energy Regulatory Commission, 480,891 of them in
window, each carrying a `Date:` header. Its value is less its size than its **independence**:
corporate email owes nothing to any web crawl, to Usenet, or to any registry, so a pair it confirms
alongside those is genuine cross-source corroboration rather than one lineage agreeing with itself.

### `rtfm_faq`: the Usenet FAQ mirror

The `rtfm.mit.edu` periodic-posting archive. Each FAQ lists the sites its subject covers and carries
its own revision header, so it is dated by **revision** rather than by the date it happened to be reposted,
which is the difference between a 1997 fact and a 2001 one.

### `trade_press`: scanned computer magazines

A magazine issue is a dated artifact: a 1997 issue printing a domain establishes that the domain was
in use in 1997, exactly as an archived dated directory page does. Reported here at its measured
size rather than its projected one; see `sources.md` for why the discovered corpus turned out
smaller in value than the family suggests.

## 3. The extra filter on typed addresses

The `dated_directory` sources are the ones where a human typed the address, so they carry the risk
that the string is not a real domain at all: an OCR error from a scanned page, a transcription typo,
a Usenet address deliberately munged against harvesters, or a file name that merely looks like a host.

Every one of them therefore passes a corroboration split before it may assign a year. The test is
exact and mechanical: **the domain must already appear in the annual files from a different source.**
That other source establishes the name is real; the dated artifact then supplies only the year. A
string appearing nowhere else is not asserted at all. It is demoted to the candidate pool, ships
separately in `candidates.txt`, and claims nothing.

The consequence is the guarantee worth having: **an invented name cannot reach an annual file**,
because a name nobody else ever saw has no other source to corroborate it. This is a property of the
pipeline rather than a review step that could be skipped, and it costs real volume: `usenet_bare`
found 601,738 candidate pairs in the Usenet corpus and the table above reports only the fraction that
survived, because 36.3% were uncorroborated and went to the pool and most of the rest were already
held.

Beyond that, 78,308 of this round's pairs are confirmed by two or more independent collection lineages rather than one, and every asserted pair in the collection carries 1.7435 distinct sources on average. One qualification on that count, since it is the kind of number that flatters itself:
50,250 of the `usenet_bare` rows come from `can.uucp.maps` and `comp.mail.maps`, the two newsgroups
the UUCP registry parser also reads. Where a pair holds evidence from both, that is one posting read
two ways rather than two independent lineages. It moves no annual file and no equivalent-English
figure, only the corroboration count.

## 4. How to reproduce

Two ways to rebuild the result files, cheapest first, and one way to check what shipped without
rebuilding anything.

```bash
bash verify.sh        # check only: checksums, pair counts, and evidence for every shipped pair
just rebuild          # rebuild from the shipped provenance export, no source data, ~1 min, byte-identical
just reproduce        # rebuild from the raw sources in data/raw/ plus the supplied baseline
```

`just reproduce` replays the collectors' stored journals rather than re-requesting the network, so it
gives the same answer every time. To collect **more** evidence from any of the new families:

```bash
just rdap-pool            # registry creation dates for the candidate pool
just usenet-bare          # bare addresses, from archives already on disk, no network
just usenet-addresses     # the ftp:/mailto:/body addresses, likewise offline
just uucp-maps            # the comp.mail.maps registry dumps
just maillists            # the python.org and gnome.org list archives
just enron                # the FERC corpus
just rtfm-faqs            # the rtfm.mit.edu FAQ mirror
just trade-press          # scanned magazines on archive.org
```

Per-source detail, including every family evaluated and **rejected** with the measurement that killed
it, is in `sources.md`. The archive layout and what each folder proves is in `README.md`.
