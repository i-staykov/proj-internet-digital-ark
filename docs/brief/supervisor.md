# The research on one page

## The question

The Internet Digital Ark competition asks for the web's hostnames of 1996 to 2013, 1996 to
2001 first, each with item-level evidence for its year. A hostname-year the reviewer's files lack
scores its top-level domain's English share, in equivalent-English (EE); a round ships at 1% of
their EE in 1996 to 2001, candidates counted, or 2002 to 2013 ([the metric](metric-explained.md)).

## The method

Every source is priced against the reviewer's files before collection; a measured negative with
its reason is a result ([the laws](../lore/laws.md)). The main source is the Internet Archive's
capture index (CDX), whose 1996 to 2001 hosts are 85% in the reviewer's files, capping those
years at about 0.55M EE (#588). Eight other sources scouted since 2026-11-07 closed as measured
negatives, none above 162 EE ([register](../registers/sources-closed.md)).

## The architecture

The Archive throttles CDX per address, so throughput grows only with addresses (#585): the bank
VM's, GitHub's hosted runners', and a self-hosted runner's on a free cloud VM (being joined). The
VM lends runners slices of its ranked queue and banks their returns. An agent on the VM tunes
collectors and scouts sources inside rails; a laptop session reviews by pull request; the owner
alone ships rounds.

A defect, fixed in #602: collectors ranked work by EE a second, charging an index page its
streaming time but a question at least 10 s, so questions (one per domain, 2.82 EE a start)
outranked every page (10.9 EE a request on runners), and runners' slices took every page above
them. From 06:00 UTC on 2026-11-09 to the fix the VM asked no page. A start now costs the
seconds its limiter holds one, and slices leave each collector three fourths of its pages above the
questions.

## The numbers

EE a day in 2026 from the VM's address unless named; 11-09 to 10:05 UTC, GitHub's runners from
03:44; the cloud VM 0 so far.

| Day | 1996-2001 | 2002-2013 |
|---|---:|---:|
| 11-03 | 3,339 | 842,754 |
| 11-04 | 926 | 420,661 |
| 11-05 | 3,430 | 927,169 |
| 11-06 | 3,150 | 268,753 |
| 11-07 | 732 | 353,317 |
| 11-08 | 343 | 527,793 |
| 11-09 | 169 | 53,770 |
| 11-09, runners | 77 | 5,636 |

1996 to 2001 yields hundreds to a few thousand direct EE a day against a gate of 0.74M (1% of the
reviewer's 74.25M), above the Archive's ceiling, with 12.4k direct and 257k candidate EE banked;
2002 to 2013 has 3.95M banked, past its 3.15M gate. A day's EE prices each output file alone, an
upper bound before deduplication across files; banked is the export's of 2026-11-09 23:25 UTC.
