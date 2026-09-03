export const meta = {
  name: 'hunt-breadth',
  description: 'Six untried source SHAPES proposed and refuted in parallel, screened against the seven measured killers',
  phases: [
    { title: 'Find', detail: 'one agent per shape, each blind to the others' },
    { title: 'Refute', detail: 'per shape: collide against the closed register, screen on the seven laws, probe live' },
  ],
}

// Repo root. Defaults to the working directory; set ARK_REPO when the checkout is elsewhere.
const REPO = globalThis.process?.env?.ARK_REPO ?? '.'

const BRIEF = `
Hunting NEW sources of historical domain names for the Internet Digital Ark.
Repository: ${REPO}. READ-ONLY: create, edit and delete nothing in it. Use WebSearch and WebFetch freely.

THE JOB. Reconstruct which domains existed in each year 1996-2001. A source pays only if it attaches
ONE domain to ONE specific year in that window, per item. A 1998 capture evidences 1998 and nothing else.

THE METRIC. Each (domain, year) scores its TLD's English share: .uk 0.9813, .au 0.9904, .nz 0.9895,
.edu 0.9717, .ca 0.8365, .org 0.7101, .com 0.6321, .net 0.4530, .de 0.1324, .jp 0.0605, .cz 0.0709.
A large non-English source is a SMALL source. Say so.

THE GAP. We hold about 397,000 equivalent-English of a 668,118 gate. We need roughly 270,000 more,
which is about 430,000 net-new .com-weight (domain, year) pairs. A source worth 3,000 is a rounding
error. Say plainly when your best candidate is two orders short: that is useful, a padded number is not.

THE SEVEN KILLERS, each established here by measurement. Screen every candidate on these BEFORE
proposing it, and state which ones it survives:
 1. Derived from Internet Archive crawls. Our baseline is IA-derived, so net-new is about zero.
    The exception is a bulk PROJECTION of IA holdings, which is why the Dartmouth capture census paid.
 2. Lists names without asserting they were live. A dated artifact proves the ARTIFACT's date, not the
    names' liveness. Killed Netcraft and the JANET proxy reports. A byte-volume filter does not fix it.
 3. Trust-selected rather than sampled. Certificate bundles hold CAs, relay headers hold ISPs, papers
    cite universities, award lists hold famous sites. A selected population is small however large the file.
 4. A current-state snapshot. Cannot evidence a past year. Killed AFNIC and Companies House.
 5. Human-typed. A novel name takes the corroboration split and earns no year, so typed directories
    cannot produce master evidence for exactly the names that are new.
 6. Anonymised or hashed hostnames. Ask for the release's sanitisation paragraph before fetching a byte.
    Killed the whole 1990s proxy-trace family.
 7. Dating and URL-bearing anticorrelate. A record still carrying an in-window date is one nobody has
    edited since, and a record naming a web site is one somebody has.
Prose corpora ceiling at about 0.042 net-new pairs per item, so about 119,000 items to clear the bar,
and that ceiling is a property of SUBJECT MATTER: a million biology abstracts name no web sites at all.

READ THESE FIRST, by grep and not whole:
- docs/sources.md   every source developed plus roughly 110 families already REJECTED, each with the
                    measurement that closed it. Anything already in here is worthless. Grep by NAME and
                    by POPULATION: the same population closed under another name is still dead.
- docs/discovery.md the pricing bar and the three laws in full.
- docs/ding/project-brief.md sections V, VI and IX, the reviewer's own list of what to try.

WHAT THE SHAPE OF A WIN LOOKS LIKE, from what actually paid: a 2017 Dartmouth/NBER release of the
Internet Archive's own capture census, 227,273 net-new pairs; a bulk compilation of registry creation
dates over 171M domains, 2,165,523 pairs; the UK Web Archive host link graph; the ISC Internet Domain
Survey; the Enron mail release at 5,134 pairs, which beat every public technical mailing list per
message because a business writes to other businesses that each own a domain.

THIN YEARS ARE WORTH MORE. Our 2001 is strong and our 1996, 1997 and 1998 are thin, so a source that
reaches the early years outranks one that reaches 1999 to 2001.
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
        required: [
          'name', 'url', 'what_it_is', 'what_dates_an_item', 'evidence_type',
          'size_estimate', 'english_share_note', 'already_in_register', 'killers_survived', 'years_reached',
        ],
        properties: {
          name: { type: 'string', description: 'short snake_case identifier' },
          url: { type: 'string', description: 'a URL a human can open right now' },
          what_it_is: { type: 'string' },
          what_dates_an_item: { type: 'string', description: 'the exact field that attaches ONE domain to ONE year, or "nothing, candidate-only"' },
          evidence_type: { type: 'string', enum: ['cdx_timestamp', 'artifact_listing', 'link_source', 'dated_directory', 'whois_creation', 'link_target', 'none'] },
          size_estimate: { type: 'string', description: 'order of magnitude of in-window domains, and HOW you got that number' },
          english_share_note: { type: 'string', description: 'which TLDs dominate and what that does to the metric' },
          already_in_register: { type: 'string', description: 'what you found grepping docs/sources.md by name AND by population' },
          killers_survived: { type: 'string', description: 'which of the seven it survives, and which one is its biggest risk' },
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
        required: ['name', 'survives', 'reason', 'retrievable_in_2026', 'closest_closed_family', 'corrected_size'],
        properties: {
          name: { type: 'string' },
          survives: { type: 'boolean' },
          reason: { type: 'string', description: 'why it dies, or what specifically you could not refute' },
          retrievable_in_2026: { type: 'string', description: 'what the URL actually returned, with the HTTP status and byte count' },
          closest_closed_family: { type: 'string', description: 'nearest entry in the rejected register, and why it is or is not the same population' },
          corrected_size: { type: 'string', description: 'your own in-window net-new EE estimate, and how you got it' },
          which_killer: { type: 'string', description: 'the numbered killer it dies on, if it dies' },
        },
      },
    },
  },
}

const LENSES = [
  {
    key: 'uncrawled-subscribers',
    prompt: `SHAPE: mailing lists and online communities whose SUBSCRIBERS were an uncrawled population.
This is a reopen condition this project set for itself and never used. Its own finding, verbatim:
"If mail is ever reopened, ask whether a list's SUBSCRIBERS were an uncrawled population, never whether
its headers survived." The developer lists already mined (python.org, gnome.org, Apache) failed because
a Python developer's homepage is exactly what a web crawl held first. What is wanted is the opposite:
in-window list or group archives whose posters were ORDINARY small businesses, tradespeople, hobbyists,
clubs, churches, schools, local societies, each with its own registered domain and no reason to be
famous. Think genealogy lists, trade and industry lists, regional and municipal lists, hobby and
collector lists, professional-association lists, eGroups/OneList/Yahoo Groups, Topica, Listserv archives
at universities, and per-industry commercial lists. For each: is there a BULK route to the raw messages
with Date and From headers, and how many in-window messages does it hold? Enron yielded 0.0067
equivalent-English per in-window message; use that rate to say what a corpus is worth before proposing it.`,
  },
  {
    key: 'organisational-mail-releases',
    prompt: `SHAPE: bulk releases of an organisation's own 1996-2001 correspondence, the Enron shape at scale.
Enron paid because a business writes to other businesses that each own a domain, which is the one
population that beats killer 3. Find more of them. Routes to search: litigation discovery made public
(antitrust, tobacco, opioid, asbestos, securities), regulator investigation files, US state and federal
FOIA reading rooms, state-governor and state-agency email archives released under public-records law,
university and hospital records releases, congressional and parliamentary inquiry exhibits, bankruptcy
estate document sets, and industry document libraries. For each say: how many items fall in 1996-2001,
are they born-digital mail with real headers or scanned paper with OCR damage, is there a BULK download
or only a per-document viewer, and what does the release's own redaction policy do to e-mail addresses.
Killer 6 applies: a release that redacts addresses is worth nothing, so find the redaction paragraph.`,
  },
  {
    key: 'small-org-open-data',
    prompt: `SHAPE: government, regulator and funder open data carrying BOTH a per-row date in 1996-2001 AND
a web-address or e-mail column, for ORDINARY SMALL organisations. This project already killed the
academic version of this: US IPEDS institutional characteristics died because .edu is 95.5% saturated at
the year an institutional directory attests. So do not propose universities, and do not propose large
public companies (SEC EDGAR is measured and closed at 0.01 equivalent-English per filing). Propose the
long tail: small-business registries, trade licensing and professional boards, charity and non-profit
regulators, local-government supplier and procurement records, agricultural and food producer registers,
tourism and hospitality licensing, broadcast and telecom licensees, importer and exporter registers,
trade-mission and export-promotion directories, chamber-of-commerce data releases. High-weight
jurisdictions pay most: UK 0.9813, Australia 0.9904, New Zealand 0.9895, Canada 0.8365, Ireland, US.
Killer 4 is the one that kills most of these, so for each say whether the published file is a HISTORICAL
per-year release or a current-state snapshot with a date column, because the second cannot evidence a past year.`,
  },
  {
    key: 'high-weight-registries',
    prompt: `SHAPE: national registries for the HIGHEST-weight TLDs publishing their own historical registration
record. Weights make these worth 1.5x a .com pair: .au 0.9904, .nz 0.9895, .uk 0.9813, .ie, .za, .ca
0.8365, .sg, .in. The .au family (AUNIC, auDA, AARNet) is already closed here and .uk zone data was never
published, so grep before proposing either. What is wanted: any registry, registrar association, national
research network or national library that published a LIST of registered names with dates, or an annual
report with a machine-readable annex, or a deposited dataset, or an academic study of its own namespace
that deposited the name list. Also consider second-level registries with their own records (.ac.uk, .gov.uk,
.co.nz, .edu.au) and the national research networks that ran them. State for each whether the artifact is a
zone snapshot, a creation-date list, or an aggregate count, because aggregate counts are worthless here.`,
  },
  {
    key: 'dataset-registry-sweep',
    prompt: `SHAPE: an automated sweep of dataset registries for deposited 1996-2001 web crawls, link graphs, URL
lists and seed packages. The reviewer names this method explicitly and gives one worked example, the
University of Minnesota DRUM dataset "Link Lists for Websites Tracking the Development of the Early Web
from 1996 to 2000" (DOI 10.13020/D62684). The point is the PATTERN. Query the search APIs rather than
reading landing pages: DataCite, OpenAIRE, re3data, ICPSR, Harvard Dataverse, Dryad, figshare, Zenodo,
OSF, Mendeley Data, PANGAEA, ADS, and the national repositories of the UK, Australia and Canada. Also
walk the citation graph around early-web measurement research 1997-2003: the papers that studied the web
at scale (Broder, Kleinberg, Lawrence and Giles, Bharat, Kumar, Adamic, Huberman, the NEC and IBM
web-graph groups) mostly deposited or published their crawl seeds somewhere. Report the actual queries you
ran and the hit counts, so the sweep is reproducible, and name specific DOIs rather than repositories.`,
  },
  {
    key: 'non-capture-assertions',
    prompt: `SHAPE: wildcard. Any machine-generated 1996-2001 artifact that ASSERTS a domain was registered or
resolving, and is NOT a web capture index, NOT a DNS zone file, and NOT a registry creation-date snapshot.
All three of those are developed or closed here. Killer 2 is the whole game in this lens: the artifact must
assert existence, not merely mention a name. Things that assert: a delegation record, a resolution result, a
successful transfer, a payment, a certificate issued to a host, a registered trade mark citing a domain, a
peering or routing record naming a domain, a mail-exchanger table, an FTP mirror manifest listing its
upstream by name, a software licence server host list, a newsgroup control message, a DNS blocklist or
whitelist with dated entries, a name-server configuration published as documentation. For each, say what
makes it an assertion rather than a mention, and how many in-window items exist. Reject your own ideas that
reduce to a mention: this project has closed relay headers, cited references, printed directories, quoted
whois, trade press and award lists, all on killer 2 or killer 3.`,
  },
]

phase('Find')

const results = await pipeline(
  LENSES,
  (lens) => agent(
    `${BRIEF}\n\n${lens.prompt}\n\nReturn at most 4 candidates, best first. A candidate you cannot name
    and link is not a candidate. If the shape is genuinely dry after real searching, return an empty list
    and say so: an honest empty lens is worth more than a padded one. Never state a number you did not
    derive, and say how you derived each one.`,
    { label: `find:${lens.key}`, phase: 'Find', schema: CANDIDATES },
  ),
  (found, lens) => {
    const list = (found && found.candidates) || []
    if (!list.length) return { lens: lens.key, candidates: [], verdicts: [] }
    return agent(
      `${BRIEF}\n\nYou are the SCEPTIC for the "${lens.key}" shape. Another agent proposed these:\n\n` +
      JSON.stringify(list, null, 2) +
      `\n\nRefute each one. Default to survives=false when unsure. Four tests, all DONE rather than reasoned:
      1. Grep docs/sources.md by NAME and by POPULATION. Roughly 110 families are already closed there.
      2. Actually fetch the URL. Report the HTTP status and byte count you got. A 404, a login wall, a
         Cloudflare interstitial or a 159-byte stub is dead however good the description sounds. Prove any
         zero against a positive control fetched in the same minute, because nothing-found and
         pointed-wrong look identical.
      3. Check the dating claim against the artifact itself. If "what dates an item" turns out to be an
         aggregate snapshot date, or a year inferred from anything other than the record, it is
         candidate-only at best. Say which.
      4. Name the numbered killer it dies on. Correct any inflated size, and say how you checked. A
         candidate whose corrected size is under about 3,000 equivalent-English does not survive: it cannot
         move a 270,000 gap and it costs a day to build.`,
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

log(`${survivors.length} survived, ${killed.length} refuted, across ${clean.length} shapes`)

return { survivors, killed }
