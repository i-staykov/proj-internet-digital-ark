# Email draft for the phase-5 submission

Send to: [redacted]
CC: [redacted]
Subject: Re: Trial Project

Attach: `report.docx`
Link: upload `internet-digital-ark-1996-2001.tar.gz` to transfernow and paste the URL where marked.

---

Dear Professor Ding,

This round passes the 5% threshold you set.

1. Total number of original domains from 1996 to 2001: 15,428,507
2. Equivalent-English total: 8,346,839.3737
3. Increment: 2,836,693 records
4. Equivalent-English increment: 1,695,551.8368
5. Equivalent-English growth rate: 20.313700%

Lines 1 and 2 are your `merged260815` totals, unchanged, since this increment is not yet merged.

Cumulative across my four rounds, which you asked me to track: 5,364,432 records and 3,147,327.5923
equivalent-English, which is 37.7068% of the 8,346,839.3737 the corpus holds today. My first round
predates the equivalent-English metric, so its 1,429,524 records are your own confirmed figure and the
weight beside it is measured over the two releases either side with the unchanged model.

The increment covers 2,665,102 distinct domains, and 1,789,260 of them appear in none of your six
annual files in any year, so most of it is genuinely new names rather than new years on names already
held.

The round came from a change of strategy rather than more querying, and I think the finding is the
useful part. When `merged260815` arrived carrying another contributor's UMN DRUM delivery, the shape
of it was informative: one bulk dated corpus was worth roughly twenty times my entire previous round
of per-domain archive querying. My collection had been optimised against request throughput against a
single archive, and a bulk dated corpus does not have that constraint at all. So I re-aimed the search
at that shape and found two more:

- The Internet Archive's own capture census, published in a 2017 Dartmouth/NBER research release. It
  states how many captures the Wayback Machine holds for each host in each calendar year, which is the
  same fact a CDX query returns, in bulk instead of one host at a time. 227,273 net-new pairs. Where my
  own CDX engine had separately queried the live archive, the two agree on 138,760 pairs.
- A published compilation of registry creation dates over 171 million domains. Used strictly as you
  specified: a creation date in 1998 writes 1998 and no other year, and later years still have to be
  earned from a capture or a survey. 2,165,523 net-new pairs. Before admitting it I ran a falsification
  check, since a TLD cannot predate its own delegation: across the six TLDs delegated in 2001 the file
  has 21,698 in-window rows and zero dated before 2001.

Two further gains came from material already on my own disk. A parser had been reading 6.76% of a UK
Web Archive file since July because it assumed the file was sorted by year and it is fifteen
concatenated shards; fixing that recovered 92,646 pairs. And the January 1997 Internet Domain Survey,
recorded as unrecoverable because its host is dead, turned out to be intact in the Wayback Machine
under a successor hostname.

The archive holds the annual files, the candidate pool kept separate from them, the evidence behind
every single assignment as Parquet, the raw journals, and the code at the commit that produced it. I
extracted a fresh copy and ran its own documented reproduction before sending: the rebuild returns
every per-year count exactly and all nine integrity invariants pass. The report covers the CDX
execution notes, the per-source contribution statistics and the discovery system itself.

[PASTE TRANSFERNOW LINK HERE]

Best regards,
Ivaylo
