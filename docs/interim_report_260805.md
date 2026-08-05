% Internet Digital Ark: interim report
% Ivaylo Staykov
% 6 August 2026

## Additions since the 2 August submission

Measured against the collection on 06 August 2026 at 00:27 CEST.

| | |
|---|---|
| New (domain, year) records admitted | **110,978** |
| Distinct domains | 90,017 |
| **Equivalent-English added** | **75,067.3794** |
| Mean weight per record | **0.6764** |
| Growth on the 5,622,984.6434 baseline | **1.3350%** |
| Held as candidates, not admitted | 119,055 |

Last round's 151,949 records averaged 0.6042 equivalent-English. These average **0.6764**,
so each record is worth **11.9% more** under the metric.

## Where they came from

| Source | Records | Equivalent-English | Mean weight |
|---|---|---|---|
| `usenet_announce` | 80,714 | 52,270.6337 | 0.6476 |
| `ia_cdx_bulk` | 30,264 | 22,796.7457 | 0.7533 |

**Dated Usenet postings, 80,714 records.** A newly opened source family, and the larger of the two.
Group archives from the Internet Archive's Usenet collection, 4,175 of them processed so far. Selection was widened from announcement groups to ordinary discussion groups, which yield as well because people quote addresses in conversation.

**Archive capture verification, 30,264 records.** The method reported on 2 August, continued, with
its query queue now ordered by expected equivalent-English per query rather than by which year was
thinnest. Measured hit rate 96.0% to 97.5%.

## By year

| Year | New records | Equivalent-English | EE baseline | EE growth |
|---|---|---|---|---|
| 1996 | 1,358 | 870.2 | 436,608.6 | 0.1993% |
| 1997 | 3,831 | 2,442.6 | 785,802.1 | 0.3108% |
| 1998 | 19,761 | 12,593.9 | 698,408.2 | 1.8032% |
| 1999 | 25,751 | 16,970.9 | 1,081,431.8 | 1.5693% |
| 2000 | 32,981 | 22,434.9 | 932,153.5 | 2.4068% |
| 2001 | 27,296 | 19,754.9 | 1,688,580.5 | 1.1699% |

**No year meets the completeness standard.** 1996 grew 0.1993% and 1997 grew 0.3108%, both above the 0.1% threshold, which must be satisfied together with the 10,000-record condition before any year may be described as approaching completeness.

1996 and 1997 are sparse for reasons of method rather than saturation. The bracketed-gap search can only
target 1997 to 2000, because both flanking years must themselves lie inside the window, so 1996 gains
only incidentally: 31 of its 1,358 records came from capture verification. And dated Usenet
mentions of web addresses are intrinsically scarcer in the first two years, because the habit of quoting
a URL grew with the web itself.

## Evidence

Every record ties one domain to one specific year through a dated artifact: an archive capture
timestamp, or a message's own posting date. No inference across years is made. A name attested only by a
Usenet mention does not enter an annual file; it waits in the candidate pool until an independent source
or a capture corroborates it. 119,055 domains are currently held that way: found, dated by a posting, but not yet independently corroborated.

Per-record provenance is retained throughout, and can be supplied as annual `.txt` files with a
provenance table on request.

## Next

The capture-verification engine is currently adding 529 records and 370 equivalent-English per hour, measured over the last 12 hours. Running to 9 August, that projects to roughly **45,256 further records and 31,613 equivalent-English** from this method alone.

Then: verify the 119,055 uncorroborated candidates; work the Usenet groups not yet downloaded, of which roughly 15,000 remain; and open the archived portal
directory trees, where each capture is a dated artifact. That last is the method most likely to move
1996 and 1997, since a page captured in 1996 dates its entries directly rather than depending on
flanking years or posting volume.
