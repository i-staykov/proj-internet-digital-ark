# State, 2026-08-24 01:15Z

## Position
**386,428.95 EE, 2.891919% growth. Gate 668,118.44 (5% of `merged260821`, fixed). 57.8% of it.**
Gap **281,689 EE**. Engines delivered ~3,900 EE/hour overnight, so the gap is ~72 hours of querying.

## Delivery: built and verified, NOT sendable (below the gate)
`submissions/phase-6/`, built 2026-08-24T00:45:07Z at commit `de44f5ce`, baseline `merged260821`.
**1,941,273,504 bytes, 276 files**, sha256 `70299a90...85da7`. **All nine checks pass**, D1-D4 included.
D3 reconciles 22/22 with overlap zero. `ARK_SLIM=1` omits the 3.4 GB of raw journals; tier 2 unaffected.

## Running
2 RDAP workers, 1 CDX supervisor + worker, `maintain.sh`. Hourly cron `cccba25e` fires the hunt cycle.

## Spend limit is exhausted
10 of 11 agents in the last hunt failed on it. **No further subagents or workflows will run**, so hunting
is single-threaded until the limit resets.

## Closed on measurement, never retry
Dartmouth reopened **0** (payload already banked) | ODP alt host **0** | Zenodo banner ads **433** |
AFNIC back editions **782** | promotion re-run **163** | FAC Single Audits **2,407** |
SEC EDGAR extended **5,884** | USPTO unretrievable | Companies House out of window.

**Screening test earned tonight: a current-state snapshot cannot evidence a past year.** AFNIC and
Companies House both died on it. Apply before downloading.

**UKWA host linkage (~1.1M EE if it opens) is still shut.** Our copy is exactly 2147483648 bytes, a 2 GiB
replay cap. Capture `20200106181208id_` refuses ranged requests while a CDX control returns 200; the
origin serves a 159-byte stub. Re-probe, do not re-reason.

## Best unbuilt source
**SEC EDGAR extended, 5,884 EE.** Dated by EDGAR's own `Date Filed` over 222,232 in-window filings of
8-K, DEF 14A and 10-KSB, taking printed URLs and e-mail domains. Collector is straightforward.

## Needs Ivo
`internic_zone` and `ukwa_geoindex`: one word each, ~13,000 EE claimed, both stale-downward so re-price
before quoting. Neither changes the arithmetic.

## Open
Archive is 1.94 GB against a ~1 GB target. `provenance/` is 1.6 GB and 86% of it is the reviewer's own
baseline evidence. Dropping it alone left 11,316,960 `domain_year` rows pointing at missing evidence and
failed `ark check` inside the archive, so the slice must be cut on both sides or not at all.
