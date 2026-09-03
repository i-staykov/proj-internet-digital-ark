export const meta = {
  name: 'hunt-high-potential',
  description: 'Five named leads, each plausibly worth over 5,000 EE. Ivo approval time is the scarce resource, so small finds are not wanted',
  phases: [
    { title: 'Chase', detail: 'one agent per named lead' },
    { title: 'Verify', detail: 'per lead: re-fetch, re-count, price against the live store' },
  ],
}

// Repo root. Defaults to the working directory; set ARK_REPO when the checkout is elsewhere.
const REPO = globalThis.process?.env?.ARK_REPO ?? '.'

const BRIEF = `
Repository: ${REPO}. READ-ONLY: create, edit and delete nothing in it.

**THE SCARCE RESOURCE IS A HUMAN'S APPROVAL TIME, NOT YOUR TIME.** Every source needs one word from
Ivo before it can date a year. A source worth 18,000 equivalent-English and a source worth 400 cost him
the same minute. So **do not report anything you cannot argue is plausibly worth 5,000 EE or more**.
An honest "this lead is two orders short and here is the number" is a good result. A list of small
finds is not.

WHAT PAID TODAY, so you know the shape and the size to beat. The IE Domain Registry regenerated its
whole \`.ie\` register as static A-Z web pages, each carrying its own line \`updated automatically at
14:51 GMT on Friday, 21 December 2001\`. That is the same instrument as a DNS zone file: the registry
asserting what was registered at a stated instant. **19,341 net-new pairs and 18,846 equivalent-English
from 38 HTTP requests and 1.1 MB.** Nine further namespaces were then tried and gave 144 to 4,462 EE
each, which is the size NOT to bring back.

**THE SCREEN THAT SEPARATES THE WINNERS, in two clauses.** Ask who held the register's database, and
then ask whether they ever wrote it to a file. \`.ie\` was one university computing service regenerating
one register onto one static tree. \`.za\` was eleven separately administered second levels taking
applications by e-mail, so there was no single machine to regenerate. \`.lk\`, \`.th\`, \`.kr\` and \`.nz\`
each had one operator and one database and exposed it ONLY through a per-name query form, which is the
commonest failure mode of all.

THE METRIC. Each (domain, year) scores its TLD's English share, read from
\`src/ark/data/tld_english_share.json\` as an \`eng\` row in percent. uk 0.9813, au 0.9904, nz 0.9895,
ie 0.9744, us 0.9261, za 0.9682, ca 0.8365, com 0.6321, net 0.4530, de 0.1324, nl 0.1629, se 0.2135,
jp 0.0605. **A large non-English namespace is a small source**: 100,000 \`.de\` pairs are worth 13,240
and 14,000 \`.uk\` pairs are worth 13,738. Say the arithmetic out loud before you get excited.

THE SEVEN KILLERS. Screen every candidate and say which it survives.
 1. Derived from Internet Archive crawls: our baseline is too, so net-new is about zero. The exception
    is a bulk PROJECTION of IA holdings, which is why one capture census paid 227,273 pairs.
 2. Lists names without asserting they were live. Proves the artifact's date, not the names' liveness.
 3. Trust-selected rather than sampled: award lists, citations and certificate bundles hold authorities.
 4. A current-state snapshot cannot evidence a past year.
 5. Human-typed, so a novel name takes the corroboration split and earns no year. **This one is worth
    15x on a real source measured today**, so always report a page's \`Generator\` meta tag, its
    whitespace consistency and any malformed entries, and let a human rule.
 6. Anonymised or hashed hostnames.
 7. Dating and URL-bearing anticorrelate: a record still carrying an in-window date is one nobody edited.

TODAY'S NETWORK REALITY, so you do not misread a refusal as an absence.
 - \`web.archive.org\` refuses roughly three connections in four. Retry with a wait; one failure is not a
   negative result, and a CDX zero must be proved against a control query that returns rows.
 - \`archive.org\` itself answers reliably, so item metadata and downloads are cheap.
 - Use https, and follow redirects: Wayback 302s to the nearest capture and a fetch without redirects
   returns zero bytes, which reads exactly like a missing page.
 - \`matchType=domain\` with a row limit truncates ALPHABETICALLY, not by date, so add \`from=\` and \`to=\`
   or a host with a large modern footprint hides its era tree completely.
 - Kill session noise with \`filter=!original:.*\\?.*\` when a commercial host burns the row budget.
 - **The CDX \`length\` column is the COMPRESSED record size, not the page size.** A big uniform table
   compresses hardest, so ranking candidates by CDX length under-ranks exactly the pages worth having.

BEFORE PROPOSING ANYTHING, grep \`docs/sources.md\` by NAME and by POPULATION. It holds roughly 180
families, most of them closed with the measurement that closed them, and re-proposing one wastes the
only thing that matters here. Already done today and NOT to be repeated: .ie, .my, .za, .ph, .in, .nz,
.au, .ca, .sg, .hk, .tw, .id, .nu, .lu, .mt, .sa, .il, .ve, the \`nic.us/domain-delegated.txt\` file,
squidGuard blacklists, DataCite dataset search, Arquivo.pt, the Wayback sparkline endpoint, and the
Not Your Parents' Web TimeMaps.

NEVER state a number you did not derive, and say how you derived each one.
`

const SCHEMA = {
  type: 'object',
  required: ['lead', 'worth_a_decision', 'artifacts', 'what_was_enumerated', 'honest_size'],
  properties: {
    lead: { type: 'string' },
    worth_a_decision: {
      type: 'boolean',
      description: 'true ONLY if you can argue this is plausibly 5,000+ net-new EE',
    },
    artifacts: {
      type: 'array',
      maxItems: 6,
      items: {
        type: 'object',
        required: ['url', 'bytes', 'in_body_date', 'names_counted', 'how_counted'],
        properties: {
          url: { type: 'string' },
          bytes: { type: 'integer' },
          in_body_date: { type: 'string', description: 'quoted verbatim, or "none, capture stamp only"' },
          names_counted: { type: 'integer' },
          how_counted: { type: 'string' },
          generator: { type: 'string', description: 'Generator meta tag or other sign of hand assembly' },
          asserts: { type: 'string', description: 'registration, liveness, application, or mere mention' },
        },
      },
    },
    who_held_the_database: { type: 'string' },
    wrote_it_to_a_file: { type: 'string', description: 'the second clause of the screen, answered' },
    killers_survived: { type: 'string' },
    what_was_enumerated: { type: 'string', description: 'queries and hosts actually run, with row counts' },
    honest_size: { type: 'string', description: 'net-new EE and how you derived it. Say plainly if two orders short' },
    priced_against: { type: 'string', description: 'the live store at data/ark.duckdb, or which exported files' },
  },
}

const LEADS = [
  {
    key: 'uk-naming-committee',
    prompt: `LEAD: the pre-Nominet \`.uk\` register. **This is the highest-value question left in the project**,
because \`.uk\` weighs 0.9813 and the namespace held hundreds of thousands of names in window, so an
artifact here is worth an order of magnitude more than anything found today. Nominet was formed in August
1996; before that \`.uk\` was run by the UK Naming Committee, a volunteer body operating IN PUBLIC out of
ULCC and Imperial College, and public bodies write minutes and lists. Chase: \`nic.uk\`, \`nominet.org.uk\`,
\`nominet.net\`, \`ulcc.ac.uk\`, \`ic.ac.uk\`, \`ja.net\`, \`ukerna.ac.uk\`, and the naming-committee archives
wherever they landed. Look specifically for lists of APPLICATIONS RECEIVED and REGISTRATIONS GRANTED, the
committee's agendas and minutes with name annexes, and any published register or zone extract. Also check
whether Nominet itself ever published a register listing, a monthly new-registrations report, or a
deletions list in 1996-2001. Note: bulk QUERYING of Nominet is forbidden on this project for legal
reasons, so a published FILE is what is wanted, never a plan to query the registry.`,
  },
  {
    key: 'usenet-registration-announcements',
    prompt: `LEAD: registration announcements in national \`uk.*\` and other English-language newsgroup
hierarchies. The register already banks the CA Domain Registry's public approval notices from
\`can.domain\` at 936 post-split pairs, and records that the intersection of names AND dates existed
"only where a registry ran its approval process in public". **The UK Naming Committee ran its process in
public too**, so the analogue should exist in \`uk.net.news.announce\`, \`uk.net.news.config\`, \`uk.misc\` or
a committee mailing list mirrored to news. Note the corpus of 411 GB of Usenet archives was DELETED from
this machine to free disk, but the per-file ledger is kept and archive.org publishes the per-file sha1,
so a named group can be re-fetched cheaply from the \`usenethistorical\` collection on archive.org, which
answers reliably today. Identify the exact groups and items worth re-fetching and estimate the pairs
before proposing a download. \`.uk\` at 0.9813 is what makes this worth asking.`,
  },
  {
    key: 'us-locality-registers',
    prompt: `LEAD: the \`.us\` locality namespace, weight 0.9261, which was delegated in a tree of tens of
thousands of names: \`ci.<city>.<state>.us\`, \`co.<county>.<state>.us\`, \`k12.<state>.us\`,
\`lib.<state>.us\`, \`cc.<state>.us\`, \`state.<state>.us\`. Each state's subtree had its OWN delegated
administrator who published a list, which is the one-operator-one-database shape that pays. The
\`nic.us/domain-delegated.txt\` file is a CLOSED family here worth 1 to 2 net-new pairs, so do not propose
it; what is wanted is the PER-STATE registers and the school and library directories that listed them.
Try \`nic.us\`, \`isi.edu\`, \`us-domain.org\`, state education department and state library hosts, and the
regional network operators who held the delegations. Population arithmetic first: if the whole in-window
\`.us\` locality tree is order 50,000 names, that is 46,000 EE and worth chasing hard; if it is 5,000, say so.`,
  },
  {
    key: 'machine-authored-commercial-indexes',
    prompt: `LEAD: large dated indexes that a MACHINE wrote, published by commercial services rather than
registries. Killer 5 costs 15x on this project, so a machine-authored index is worth many times a
hand-made directory of the same size, and killer 2 is the other half: the index must assert the site was
live, not merely name it. Shapes that qualify: a banner or ad network's member list generated from its
own serving database; a web counter or ranking service's participant list generated from its own logs; a
search engine's own "sites added this week" page generated from its crawler; a webring engine's machine
listing; a hosting company's generated customer index; an affiliate network's generated merchant list.
The register already closed hand-made award galleries, WebRing member pages that hide members behind a
redirector, and Netcraft's search cache on contemporaneity, so read those rows first and bring something
of a different mechanism. State for each whether the page was generated or typed, and how you can tell.`,
  },
  {
    key: 'wildcard-over-twenty-thousand',
    prompt: `LEAD: wildcard, and the bar is deliberately high. Name any single artifact you can argue is
plausibly worth **more than 20,000 net-new equivalent-English**, which is more than anything found today.
Think about what has NOT been asked. Things this project has never looked for, as far as the register
shows: a registry's own published ZONE extract for a high-weight namespace other than InterNIC's;
a national telecom or postal authority's published list of registered internet addresses; a
standards-body or trade-association membership register generated from a database; an ISP association's
member-domain list; a stock exchange or securities regulator's machine-generated issuer web-address
field; an insurance, banking or medical regulator's licensee register with a website column and a
per-row date. Screen hard on the two-clause question and on weight times volume, and if your best idea
is two orders short then say the number and say so.`,
  },
]

phase('Chase')

const results = await pipeline(
  LEADS,
  (l) => agent(`${BRIEF}\n\n${l.prompt}`, { label: `chase:${l.key}`, phase: 'Chase', schema: SCHEMA }),
  (found, l) => {
    if (!found || !found.worth_a_decision) return { lead: l.key, worth: false, detail: found || null }
    return agent(
      `${BRIEF}\n\nYou are the SCEPTIC for "${l.key}". Another agent reports this:\n\n` +
      JSON.stringify(found, null, 2) +
      `\n\nRefute it, and default to worth_a_decision=false. Do these rather than reason about them.
      1. Re-fetch every URL and report the status and byte count YOU got.
      2. Read any in-body date yourself with the HTML tags stripped, and check it falls in 1996-2001.
         One of 27 pages in today's winning source carried a 2002 footer and had to be dropped.
      3. Re-count the names. Exclude the registry's own hostnames, www-prefixed duplicates and bare
         public suffixes. Agents today overcounted by 300 by keeping public suffixes and undercounted by
         31 by reading one of three columns.
      4. Ask whether the page asserts REGISTRATION or only APPLICATION. A pending queue is not a
         register, and two agents today returned found=true on one.
      5. Price against the LIVE STORE at data/ark.duckdb read-only if you can open it, and say so.
         **Never price against legacy-data**: that is the superseded original baseline and an agent did
         exactly that today, overstating a source by about 1,000 EE. **And price on the CANONICAL form**:
         one pricing script joined raw URLs against a domain column and reported 6.3 MILLION EE where the
         truth was 4,509, because the top net-new TLDs it found were htm, html and php.
      6. Grep docs/sources.md by name and by population. A family closed there is worth nothing.
      7. Apply the 5,000 EE bar honestly. If the corrected size is under it, say worth_a_decision=false
         even if the artifact is real and interesting.`,
      { label: `verify:${l.key}`, phase: 'Verify', schema: SCHEMA },
    ).then((v) => ({ lead: l.key, worth: !!(v && v.worth_a_decision), proposed: found, verified: v }))
  },
)

const clean = results.filter(Boolean)
log(`${clean.filter((r) => r.worth).length} of ${clean.length} leads clear the 5,000 EE bar`)
return clean
