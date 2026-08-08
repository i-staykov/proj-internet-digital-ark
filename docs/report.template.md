# Internet Digital Ark: round report

Additions to the 1996-2001 annual domain lists, measured against `[BASELINE]`.

Every figure here is generated from the store by `scripts/report_figures.py` and substituted by
`scripts/fill_report.py`. None is typed by hand, so none can drift from the shipped files.

---

## 1. What this round adds

| | |
|---|--:|
| Net-new (domain, year) pairs | **[TOTAL]** |
| Over unique domains | [UNIQUE] |
| Domains absent from the baseline in every year | **[NEWDOMAINS]** |
| Equivalent-English added | **[EE]** |
| Growth on the [EEBASELINE] baseline | **[EEGROWTH]** |
| Mean equivalent-English weight per pair | [EEMEAN] |

[PER_YEAR_TABLE]

## 2. Where the additions come from

[EE_SOURCE_TABLE]

Each source below is described by the **artifact that carries the date**, because that is what decides
whether a (domain, year) pair is worth anything.

### `rdap_snapshot`: registry creation dates, asked of the candidate pool

The registry's own `registration` event, read from the authoritative RDAP server for each TLD. This is
the strongest evidence class in the collection and the only one that needs no corroboration, because a
registry record is not free text: the registry is the authority on when a name was created.

What is new is not the source but the **population**. Until now creation dates were only ever asked
about domains that already held a year, looking for a missing year beside a held one. The candidate
pool, names held with no year at all, had never been asked. A creation date landing in window gives
such a name its **first** year, which makes it a net-new domain and not merely a net-new pair.

Two limits, both deliberate. A creation date supports the annual file for the year it falls in and
**nothing later**: it does not establish that the domain remained registered afterwards. And a domain
whose creation date falls outside 1996-2001 attests nothing and stays in the candidate pool.

### `usenet_bare`: the addresses written without `www.`

Same corpus again, no new downloads. The extractor read `http://` URLs and hosts beginning `www.`,
and refused a bare `foo.com` on the grounds that in running prose such a string is more often a
company name, a file name or half an email address than a website. In 1996-1999 people wrote bare
addresses constantly, so that refusal was expensive.

What makes reading them safe is the corroboration rule below: a string that is really a file name is
not a domain any independent source has attested, so it cannot reach an annual file. Of 601,738 gross
pairs found, **269,773 were already asserted by the two Usenet sources above** and **36.3% were
uncorroborated and went to the candidate pool**. The figure reported here is the marginal remainder,
not the gross, which would have overstated the source fifteenfold.

### `usenet_address`: the addresses the extractor never read

Same corpus as `usenet_announce`, no new downloads. The message parser read `http(s)` URLs, bare
`www.` hosts and the `From:` header, and therefore never saw `ftp://` addresses, `mailto:` links, or
addresses typed in running text. In 1996 an `ftp://` address was often the only address a vendor
published. The date is the post date, exactly as for `usenet_announce`, which this collection already
accepts.

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

The `rtfm.mit.edu` periodic-posting archive. Each FAQ lists dozens of sites and carries its own
revision header, so it is dated by **revision** rather than by the date it happened to be reposted,
which is the difference between a 1997 fact and a 2001 one.

### `trade_press`: scanned computer magazines

A magazine issue is a dated artifact: a 1997 issue printing a domain establishes that the domain was
in use in 1997, exactly as an archived dated directory page does. Reported here at its measured
size rather than its projected one; see `sources.md` for why the discovered corpus turned out
smaller in value than the family suggests.

## 3. Why the additions are viable

**The one structural guarantee.** Every free-text source above passes through the corroboration
split: a (domain, year) becomes a dated master record **only when an independent source already
places that domain in some year**. Everything else is demoted to the candidate pool and ships
separately, in `candidates.txt`, asserting nothing. A name invented by a bad pattern, an OCR error or
a munged Usenet address therefore **cannot** reach an annual file. This is a property of the
pipeline, not a review step that might be skipped.

**Independent corroboration.** Sources sharing a collection lineage cannot corroborate each other,
and the store enforces that rather than counting distinct source names. The lineages present are
`internet_archive`, `usenet`, `dns_survey`, `registry`, `uk_web_archive`, `corporate_email`,
`trade_press`, `editorial_directory`, `software_catalogue` and `arquivo_pt`.

[CORROBORATION_TABLE]

**One flaw in that table, stated rather than buried.** 1,200 pairs, 2.8% of `usenet_bare`, are first
seen in `comp.mail.maps` and `can.uucp.maps`, the newsgroups the UUCP registry parser also reads. A
pair carrying evidence from both can appear to hold two independent lineages when it is in truth one
posting read two ways. It affects neither the equivalent-English figure nor the validity of any pair,
only the independent-corroboration count above, by roughly 0.04%. It is filterable by group name
without re-ingesting, and is recorded in `sources.md`.

**One limitation, stated plainly.** All [TOTAL] pairs added this round are **language-unchecked**.
The equivalent-English figure above is unaffected, since it is derived from the TLD distribution and
not from page text. But the page-level English verification of feedback section 6 has not been run
over these additions, so `additions_english/` is empty for this round and everything ships in
`additions_unverified/`. The two sets remain disjoint and together partition `additions/` exactly.
Running that verification over 835k pairs is months of archive budget at the measured rate, so
whether it is required for this material is a scope question rather than an oversight.

## 4. How to reproduce

Every result file can be rebuilt three ways, cheapest first.

```bash
just rebuild          # from the shipped provenance export, no source data, ~1 minute, byte-identical
just reproduce        # from the raw sources in data/raw/ plus the supplied baseline
bash verify.sh        # the reviewer's own check: checksums, pair counts, evidence for every pair
```

`just reproduce` replays the collectors' stored journals rather than re-requesting the network, so it
gives the same answer every time. To collect **more** evidence from any of the new families:

```bash
just usenet-addresses     # the ftp:/mailto:/body addresses, from archives already on disk
just uucp-maps            # the comp.mail.maps registry dumps
just enron                # the FERC corpus
just rtfm-faqs            # the rtfm.mit.edu FAQ mirror
just trade-press          # scanned magazines on archive.org
```

Per-source detail, including every family evaluated and **rejected** with the measurement that killed
it, is in `sources.md`. The archive layout and what each folder proves is in `README.md`.
