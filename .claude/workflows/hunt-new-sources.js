export const meta = {
  name: 'hunt-new-sources',
  description: 'Five independent lenses propose named historical-domain sources; a sceptic per lens kills the ones already closed or no longer retrievable',
  phases: [
    { title: 'Find', detail: 'one agent per discovery lens, each blind to the others' },
    { title: 'Refute', detail: 'per lens: collide against the closed register and probe live retrievability' },
  ],
}

// Repo root. Defaults to the working directory; set ARK_REPO when the checkout is elsewhere.
const REPO = globalThis.process?.env?.ARK_REPO ?? '.'

const BRIEF = `
You are hunting NEW sources of historical domain names for the Internet Digital Ark project.
Repository: ${REPO}. Work READ-ONLY: do not create, edit or delete any file in that repository,
and do not write scripts into scripts/. Use WebSearch and WebFetch freely.

WHAT COUNTS. The project reconstructs which domains existed in each year 1996-2001. A source is
only useful if it can attach a domain to a SPECIFIC YEAR in that window, per-item. A capture in
1998 evidences 1998 and nothing else. Sources with no per-item year are still worth naming, but
they are candidate-only: they grow a pool that a CDX engine then dates.

THE METRIC. Each (domain, year) record scores the English page-language share of its right-most
TLD: .uk 0.9813, .com 0.6321, .net 0.4530, .de 0.1324, .br 0.0934. A large non-English source is
a SMALL source. Say so when a candidate is mostly non-English.

READ THESE FIRST, in the repository:
- docs/sources.md    every source already developed, plus roughly 60 families already REJECTED,
                     each with the measurement that closed it. This is long: grep it, do not read
                     it whole. Anything you propose that is already in here is worthless.
- docs/discovery.md  the acceptance bar: how a source is priced before a collector is written.
- docs/ding/project-brief.md  the reviewer's own brief, sections V, VI and IX.

WHAT THE REVIEWER ASKED FOR ON 2026-08-17, verbatim:
"Please continue expanding the historical domain list and exploring additional ready-made
historical datasets, bulk dated corpora, national web-archive link graphs, academic repositories,
registry datasets, and other innovative automated discovery methods. Please also continue
reviewing whether previously successful methods can produce further additions."

WHAT ALREADY WORKED, so you know the shape worth finding: a 2017 Dartmouth/NBER release of the
Internet Archive's own capture census (227,273 net-new pairs); a bulk compilation of registry
creation dates over 171M domains (2,165,523 pairs); the UK Web Archive host link graph; the ISC
Internet Domain Survey. One bulk dated corpus was worth about twenty times a whole round of
per-domain archive querying.

WHAT DOES NOT WORK, measured, so do not propose it: fetching archived pages one at a time to
harvest their outbound links. Measured as a matched A/B over 240 pages, it harvested 391 domains
and yielded 5 net-new, because 386 were already held and already dated.

TARGETING FACT, new this round. The reviewer ships a per-year merge audit. Our 2001 coverage is
982,881 accepted records against another contributor's 267, because registry creation dates reach
a year the web archives cover thinly. Our 1998-2000 is being outproduced roughly three to one.
So a source that reaches 1996, 1997 or 2001 is worth more than one that reaches 1999.
`

const CANDIDATES = {
  type: 'object',
  required: ['candidates'],
  properties: {
    candidates: {
      type: 'array',
      maxItems: 4,
      items: {
        type: 'object',
        required: ['name', 'url', 'what_it_is', 'what_dates_an_item', 'evidence_type', 'size_estimate', 'english_share_note', 'already_in_register'],
        properties: {
          name: { type: 'string', description: 'short snake_case identifier, e.g. arquivo_cdxj' },
          url: { type: 'string', description: 'a URL a human can open right now' },
          what_it_is: { type: 'string' },
          what_dates_an_item: { type: 'string', description: 'the exact field or fact that attaches ONE domain to ONE year, or "nothing, candidate-only"' },
          evidence_type: { type: 'string', enum: ['cdx_timestamp', 'artifact_listing', 'link_source', 'dated_directory', 'whois_creation', 'link_target', 'none'] },
          size_estimate: { type: 'string', description: 'order of magnitude of in-window domains, and how you got that number' },
          english_share_note: { type: 'string', description: 'which TLDs dominate and what that does to the metric' },
          already_in_register: { type: 'string', description: 'what you found when you grepped docs/sources.md for it, by name AND by population' },
          years_reached: { type: 'string', description: 'which of 1996-2001 it can actually date' },
        },
      },
    },
  },
}

const VERDICTS = {
  type: 'object',
  required: ['verdicts'],
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        required: ['name', 'survives', 'reason', 'retrievable_in_2026', 'closest_closed_family'],
        properties: {
          name: { type: 'string' },
          survives: { type: 'boolean' },
          reason: { type: 'string', description: 'why it dies, or what specifically you could not refute' },
          retrievable_in_2026: { type: 'string', description: 'what the URL actually returned when you fetched it, with the status' },
          closest_closed_family: { type: 'string', description: 'the nearest entry in the rejected register and why it is or is not the same population' },
          corrected_size: { type: 'string', description: 'your own estimate if the finder overstated it' },
        },
      },
    },
  },
}

const LENSES = [
  {
    key: 'national-archives',
    prompt: `LENS: national and regional web archives other than the Internet Archive. Their bulk CDX/CDXJ
indexes, annual crawl indexes, host and link graphs, and any published dataset derived from them.
The UK Web Archive host link graph and Arquivo.pt are already developed here; find the OTHERS.
Think about which countries ran national deposit crawls that reach back to the 1990s, and which of
them publish an index rather than only a viewer. Prefer archives whose crawl is English-dominant
or whose link graph reaches English sites.`,
  },
  {
    key: 'academic-repositories',
    prompt: `LENS: academic and institutional data repositories, DOI registries, replication packages and
paper supplements. The reviewer's own worked example is the University of Minnesota DRUM dataset
"Link Lists for Websites Tracking the Development of the Early Web from 1996 to 2000"
(DOI 10.13020/D62684), which another contributor mined for millions of records. The point is the
PATTERN, not that dataset. Search repository search APIs, dataset registries, and the citation
graph around early-web research: papers from 1997-2003 that studied the web at scale almost all
deposited their crawl seeds or link graphs somewhere.`,
  },
  {
    key: 'registry-and-dns',
    prompt: `LENS: registry and DNS-infrastructure datasets. Historical zone file snapshots, ccTLD registry
publications and open data, bulk WHOIS or RDAP compilations, passive DNS archives with history,
DNS survey series, and any registry that publishes its own historical registration record.
This is the route that gave us 2001 almost exclusively, so it is the highest-value lens for the
years the web archives cover thinly. Note carefully which registries publish creation dates as
open data rather than behind a rate-limited query interface.`,
  },
  {
    key: 'crawl-collections',
    prompt: `LENS: large historical web collections, crawl indexes and seed packages. TREC WT2g/WT10g,
Stanford WebBase, ArchiveTeam collections, GeoCities SEEDS and LISTS, Early Web Datasets,
Common Crawl's predecessors, university crawls of the late 1990s, and any preserved URL list,
crawl frontier or seed package from that era. Say clearly for each whether it carries a per-item
date or whether it is candidate-only material for the CDX engine to date.`,
  },
  {
    key: 'residual-in-what-worked',
    prompt: `LENS: residual opportunity inside sources this project has ALREADY used. The reviewer asks
directly whether previously successful methods can produce further additions, and the two largest
gains last round were both of this kind: a parser that had been reading 6.76% of a file we already
held, and a survey filed as unrecoverable that was intact under a successor hostname.
Read docs/sources.md for what each developed source says REMAINS unexhausted, and read the
rejected register for entries closed because something could not be REACHED rather than because it
was measured and found poor. A closure about one copy of an artifact is not a closure about the
artifact. Propose specific unexhausted material, naming the file or date range, not general ideas.`,
  },
]

phase('Find')

const results = await pipeline(
  LENSES,
  (lens) => agent(
    `${BRIEF}\n\n${lens.prompt}\n\nReturn at most 4 candidates, best first. A candidate you cannot
    name and link is not a candidate. If a lens is genuinely dry after real searching, return an
    empty list and say so rather than padding it.`,
    { label: `find:${lens.key}`, phase: 'Find', schema: CANDIDATES },
  ),
  (found, lens) => {
    const list = (found && found.candidates) || []
    if (!list.length) return { lens: lens.key, candidates: [], verdicts: [] }
    return agent(
      `${BRIEF}\n\nYou are the SCEPTIC for the "${lens.key}" lens. Another agent proposed these:\n\n` +
      JSON.stringify(list, null, 2) +
      `\n\nYour job is to REFUTE each one. Default to survives=false when you are unsure. Three tests,
      all of which must be done rather than reasoned about:
      1. Grep docs/sources.md for the source BY NAME and BY POPULATION. A source already closed under
         another name is dead. Roughly 60 families are in the rejected register.
      2. Actually WebFetch the URL. A dataset that 404s, requires an institutional login, or has been
         taken down is dead however good it sounds. Report what you actually got back.
      3. Check the dating claim. If "what dates an item" is really an aggregate snapshot date, or a
         year inferred from something other than the record itself, it cannot be master evidence and
         is at best candidate-only. Say which.
      Also correct any size estimate you think is inflated, and say how you checked.`,
      { label: `refute:${lens.key}`, phase: 'Refute', schema: VERDICTS },
    ).then((v) => ({ lens: lens.key, candidates: list, verdicts: (v && v.verdicts) || [] }))
  },
)

const clean = results.filter(Boolean)
const survivors = []
const killed = []
for (const r of clean) {
  const byName = new Map(r.candidates.map((c) => [c.name, c]))
  for (const v of r.verdicts) {
    const c = byName.get(v.name) || { name: v.name }
    const row = { lens: r.lens, ...c, verdict: v }
    if (v.survives) survivors.push(row)
    else killed.push(row)
  }
}

log(`${survivors.length} survived, ${killed.length} refuted, across ${clean.length} lenses`)

return { survivors, killed }
