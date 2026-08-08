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

Five source families are new this round. Each is described by the **artifact that carries the date**,
because that is what decides whether a (domain, year) pair is worth anything.

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
