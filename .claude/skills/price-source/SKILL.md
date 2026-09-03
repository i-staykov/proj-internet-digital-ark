---
name: price-source
description: Price a dated corpus against the live store before proposing, ingesting or requesting approval for it. Use whenever a source needs a number.
---

# Price a source

The method is measured and lives in `docs/laws.md`; the long form is `docs/discovery.md`. This is
the running order, and it deliberately restates neither.

1. `docs/laws.md` first. The two screens (density and authority), the held-and-missing-this-year
   screen and the adjacent-year rule decide whether the bytes are worth fetching at all.
2. Check the family is not closed: `grep -n '<term>' docs/sources-closed.md`, then
   `grep -n '<term>' docs/sources.md`. Both are grep-only, never read whole.
3. Turn the source into items (`item`, `year|date`, `text`) and measure:
   `just price --items <items.jsonl> --label '<source>'`. It writes nothing.
4. Quote net-new post-split EE, never gross: they differ by more than 10x. Sample distinct
   domains, not `domain_year` rows.
5. Log the result in `docs/sources.md` whatever the answer, with the link and the sentence saying
   what dates one item. Under 5,000 EE gets one line.

More than two files to read, or any survey: hand it to the `pricer` subagent.

Before trusting the figure, `docs/traps.md`: an already-ingested journal shows zero net-new by
construction, a partitioned corpus is measured per partition, and a subagent's number is verified
like any other.
