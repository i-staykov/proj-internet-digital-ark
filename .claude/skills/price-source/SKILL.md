---
name: price-source
description: Price a dated corpus against the live store before proposing, ingesting or requesting approval for it. Use whenever a source needs a number.
---

# Price a source

The method is measured and lives in `docs/lore/laws.md`; price net-new post-split EE, never gross; a lever under 300 EE per client-hour closes. This is
the running order, and it restates neither.

1. `docs/lore/laws.md` first. The two screens (density and authority), the held-and-missing-this-year
   screen and the adjacent-year rule decide whether the bytes are worth fetching at all.
2. Check the family is not closed: `just find <term>` searches both register pages.
3. Turn the source into items (`{host, year, text}`, or `{url, timestamp, status}`, the only shape
   2002 to 2013 prices from) and measure both tracks, writing nothing: `just price --items
   <items.jsonl>`, then the same with `--track candidate --extended`.
4. Quote both `parts`, each beside its `gate_ee`, the candidate `ee` beside
   `counts.in_his_2002_2013` of its `netnew_pairs`, and the `snapshot_marker`. A 1996 to 2001
   candidate counts as a direct addition, so candidates alone close no source. Sample distinct
   domains, not `domain_year` rows.
5. Log the result as the source's one row whatever the answer (`docs/ops/runbook.md`, step 4).

More than two files to read, or any survey: hand it to the `pricer` subagent.

Before trusting the figure, `docs/lore/laws.md`, Pricing: an already-ingested journal shows zero
net-new by construction, a partitioned corpus is measured per partition, and a subagent's number is
verified like any other.
