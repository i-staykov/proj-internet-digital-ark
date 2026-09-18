# Architecture decision records

**Structural decisions only**: the evidence taxonomy, the store's shape, how the machines are
allocated, or a write path every route depends on. Each record is the decision in force and where
it is enforced; git is the history. A superseded record keeps its heading and names its successor,
because frozen submissions and code comments cite these numbers.

---

## ADR-001. The store's single write lock, and the seed that holds it for half an hour

2026-08-11. **When jobs contend for the store's single write lock, priority follows expected
net-new equivalent-English**: banking a collector's finished journal first, then pricing and
measurement, then seeding, which yields and may be interrupted. Enforced by asymmetric patience
rather than by prose: `ark ingest` waits 2400s (`INGEST_LOCK_PATIENCE_S`, `src/ark/cli.py`),
`ark seed` waits 20s and says it is yielding, and `maintain.sh` calls `ark ingest` once per SOURCE,
never once per file.

The cause and the fix are in `db.add_candidates`' docstring: `executemany` is not a batch, and a
set-based insert from an Arrow table measured 267x faster on the same input. **Do not "optimise"
`_CLASSIFY_SQL`**: its correlated `EXISTS` is 0.33 s per 3,000 names and a hand-written semi-join
measured 1.30 s, four times slower, because DuckDB already plans it as a hash semi-join. Watch the
ordering: it makes seeding always yield, which is wrong the moment a seed feeds a route that pays.

## ADR-002. UDRP dispute proceedings are master `artifact_listing`, not a split source

2026-08-11, **dead under Section XIII**: a dispute docket is a textual and registry record, not
exact-host year-specific web evidence, so it dates no annual year and scores as a candidate. The
measurement stands as a candidate figure: 5,306 in-window proceedings, 8,800 (domain, year) pairs
over 8,769 domains, 87.7% absent from the store, and ICANN calls its own table incomplete so that
is a floor. Lineage `dispute_docket`, its own family.

**Carry forward, because it is general.** The pricer's typo bound measures contamination on every
source except a typosquat source, where a name one edit from a famous one is the signal: do not
reject a docket-shaped source on a high edit-distance score.

## ADR-003. A source class may not date a year until a human classifies it

2026-08-11. **A master-eligible class may not be ingested until a human writes a `Decision:` line**
for it in [approved-sources-list.md](../registers/approved-sources-list.md); `pending`, `rejected`
and absent all refuse, and the refusal happens before the store is opened. `src/ark/approvals.py`
is the enforcement, `ingest_files` the choke point, `tests/test_approvals.py` the only place the
gate is genuinely exercised. Four decisions: `pending` refuses, `master` admits, `candidate-only`
admits while forbidding the source to date a year, `rejected` refuses and stops the request
generator re-opening it. **A material change to the extraction re-opens the class**, because the
class is the granularity and a loose extraction behind a self-dating source turns noise into master
claims.

Candidate-only evidence is deliberately ungated, so **collection never waits on a human and
promotion always does**. The quarantine is the journal on disk, outside the store: an unapproved
source cannot contaminate anything, having never been written.

## ADR-004. A declarative *probe*, and bespoke *collectors*: the line is master evidence

2026-08-11. **Two paths, split on whether the output can date a year.** `scripts/pricing/probe_source.py`
turns a TOML description into a priceable journal with no Python written; it has no `SOURCES` entry,
so `ark ingest` has no spec to run and it literally cannot admit master evidence. Bespoke collectors
stay bespoke and remain the only route into an annual file.

**A declarative path to master evidence is refused because the value of a parser is in its refusals,
and refusals do not generalise**: a configuration language expressive enough to state them is a
programming language with worse tooling. The probe refuses to guess a column and reports what it
threw away by reason, since a fetcher that silently drops rows makes a low yield read as a bad
source rather than a bad extraction. Validated against a known answer, `probes/udrp_selftest.toml`,
seven lines reproducing a 186-line collector's 8,923 records exactly.

## ADR-005. One surface asks the human for something, and it is enforced rather than agreed

2026-08-11. **[key-decisions.md](key-decisions.md) is the only surface that asks Ivo for a
decision**, a `pending` class is mirrored into it by both `request_approval.py` and
`check_approvals`, and a test over the two live documents fails when one is not named there
(`src/ark/key_decisions.py`). **It is never generated**, because a human overrules things by
editing it. Hypotheses are the agent's to settle, which is safe only because ADR-003's gate is
downstream.

## ADR-006. Edge-year gaps are a third population, and the bracketing rule was never measured

2026-08-18, C-24. **Nothing moves.** `sandwich_gap_domains` is unchanged, so 1996 and 2001 can
never be bracketed gap targets, and `build_query_queue.py --population edge` exists for whenever
the pool runs thin. Ranked on EE per query: bracketed gap 1.249, edge 0.2645, candidate pool ~0.18,
so the merged queue gives 9,999 of its best 10,000 rows to bracketed gaps. `EDGE_RATE` in
`src/ark/gaps.py` carries the pilot rates and `tests/test_edge_gaps.py` pins them; 1996 is `0.000`
on 0 of 186 domains that held both 1997 and 2000, kept as a constant so one number revives it.

**The reusable part is the method, not the population.** Freeze the denominator before measuring
against it: recomputing the edge set live biased the rate down by its own success, since every
domain where 2001 was found was banked and left the set it had just satisfied, giving 24.2% for the
same 200 answers a fixed snapshot scored 59.7%. And prefer a small sample of the real population to
a large sample of a proxy: the conditional measured off 725 journals overstated it by 1.6x.

## ADR-007. `www.<a name already held that year>` is not a hostname record

2026-09-03, **superseded by ADR-008 the next day**. The alias-share measurement it was decided on
is live and lives in [laws.md](laws.md) with fresher figures.

## ADR-008. `www.<a name already held that year>` ships, and ADR-007 is superseded

2026-09-04, Ivo. **They ship.** `NOT_WWW_ALIAS` is out of the export query and the hostname
evidence manifest, and kept unapplied because `round_figures.py` and the hostname pricer import it
to report the alias share. Settled by counting his merges rather than reasoning about him: he keeps
all 1,313,547 `www.` names of the 2026-09-02 submission, 1,106,188 of them beside the bare name in
the same year file, and credited the round 7.562846%; his section XI then wrote it down. Reporting
a share and excluding on it are two different acts, and a contested rule put at the export rather
than the ingest made the reversal one line and destroyed nothing.

## ADR-009. `www.<parent registrable>` is its own hostname record

2026-09-04, Ivo, superseding the second half of C-55. `NOT_WWW_OF_PARENT` leaves all three ingest
paths. **A record is created only where an evidence value names that exact host**, so a capture of
`foo.com` never becomes a record for `www.foo.com`: the invariant is
`a_www_record_has_its_own_evidence`, which admits the shape without asserting it. The backfill from
evidence was 6,915,924 rows and no new bytes. The first half of C-55 stands, so the DNS lanes date
the parent only.

## ADR-010. The `www.` inference runs in neither direction

2026-09-06, his ruling. `a_bare_record_is_not_inferred_from_www` refuses a registrable domain-year
whose every evidence row names `www.<domain>` and nothing else, and the CDX path excludes
`www.<parent>` from its parent-year insert at the source. **Deleting the rows was not the fix**: a
cleanup left zero and the fold wrote 22,920 more overnight. `nothing_earned_is_left_unassigned`
exempts evidence naming a subdomain, on his ground that such evidence attests THAT HOST, so the two
invariants cannot pull against each other.

The limit, stated because it is large: registrable-grain evidence stores a bare timestamp and no
host, so **7,578,321 domain-years cannot be attributed to any host at all**. The set stops growing
from the `fl=timestamp,original` fix of 2026-09-05.

## ADR-011. A sweep admits 2xx and 3xx captures, not 200 alone

2026-09-07. `cdx_suffix_sweep.py` sends `filter=statuscode:[23][0-9][0-9]`, because a 3xx is a host
that resolved, accepted the connection and answered. The regex form is what the CDX API supports; a
multi-clause negated filter returns HTTP 400. Dropping the filter entirely is another 3.3% and
admits 4xx and 5xx, where the SERVER answered rather than the host served, so the line stays where
the evidence is unambiguous. No class or journal change, so nothing banked is affected.

## ADR-012. The hostname wall admits an observation of the host IN USE, not only one of it serving

2026-09-09, C-83. **Overridden by Section XIII for what ships**: a `Received: ... by <host>` clause
is a mail header, which XIII puts on the candidate side, so it dates no annual year. The wall's
wording is still the live one in `hostname_observed_serving_web`: the observation must show the
host in use, which admits that one field, written by the receiving MTA about itself in a
transaction it completed, and takes no corroboration split for the same reason.

Excluded by name, all three deliberately: the `from` HELO clause, because the sender chose it and
it is forgeable; the parenthesised reverse-DNS, because it was outside the approval; the
`Message-ID` host, because the client stamps it from a configured nodename. DNS lanes still write
no hostname year, on his ISC ruling of 2026-09-06: a DNS answer proves a name resolves, a `by`
clause proves a service at that exact name accepted a message. He measured the ISC class at 2.67%
exact-host CDX corroboration, against 22.1% for one Apache list-month's `by` hosts and 84.2% for
the `www.` shape, and that ordering is what the wall encodes.
