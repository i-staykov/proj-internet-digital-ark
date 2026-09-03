export const meta = {
  name: 'hunt-registry-listings',
  description: 'One agent per high-weight ccTLD: find an archived register listing of the same shape that just paid 18,038 EE for .ie',
  phases: [
    { title: 'Probe', detail: 'one namespace each, CDX-enumerate the registry hosts' },
    { title: 'Price', detail: 'per namespace: count names, read the in-body date, price against the store' },
  ],
}

// Repo root. Defaults to the working directory; set ARK_REPO when the checkout is elsewhere.
const REPO = globalThis.process?.env?.ARK_REPO ?? '.'

const BRIEF = `
Repository: ${REPO}. READ-ONLY: create, edit and delete nothing in it.

WHAT JUST WORKED, and you are looking for the same thing in a different namespace.

The IE Domain Registry published its WHOLE .ie register as static A-Z web pages at
domainregistry.ie/statistics/{0-9,a..z}-doms.html, machine-generated from the live register. Each page
carries its own in-body line, verbatim: "Last updated automatically at 14:51 GMT on Friday, 21 December
2001". The Wayback Machine captured them. Measured three times independently today: 24,805 distinct .ie
names, 18,512 net-new (domain, 2001) pairs, 18,038 equivalent-English.

WHY IT PAID, so you can recognise the shape:
 - It is machine-generated, so it takes no corroboration split and no name on it was typed by a human.
 - Its date is INSIDE the artifact, not just the capture stamp.
 - A register regeneration ASSERTS registration at a stated instant. That is the same instrument as a
   DNS zone file or a registry survey, not the same as a directory listing names it happens to know.
 - It is the complete namespace A to Z, so nothing is selected for fame or authority.
 - One page of a letter is thousands of names for one HTTP request.

YOUR JOB: find the same artifact for the namespace you are given. Not the registry's home page, not its
statistics summary, not an aggregate count, not a modern zone-file programme, not a whois form. A LIST
OF NAMES with a date on it. The registry of that era may have published it under any of: /statistics/,
/lists/, /registered/, /domains/, /db/, /zone/, /reports/, an FTP tree, a monthly report, a university
computer-centre page, or the national research network that ran the namespace before a company did.

HOW TO LOOK, cheapest first:
 1. Work out who actually ran the namespace in 1996-2001. It was very often a university computing
    service or a national research network, not today's registry company, and the artifact lives on
    THAT host. UCD Computing Services ran .ie, which is why the .ie pages are on domainregistry.ie.
 2. Enumerate with the CDX index rather than guessing paths:
    https://web.archive.org/cdx/search/cdx?url=<host>&matchType=domain&collapse=urlkey&limit=3000&output=json
    then read the path list for anything that looks like a listing. A CDX zero must be proved against a
    control query that returns rows, because a wrong parameter and an empty archive look identical.
 3. Only then fetch pages. Use https, and follow redirects: Wayback 302s each URL to its nearest
    capture, and a fetch without -L returns 302 and zero bytes, which reads exactly like a dead page.
 4. web.archive.org refuses roughly half our connections today. Retry with a short wait; a single
    failure is not a negative result.

WHAT TO REPORT. For each candidate listing you find: the URL, its byte count, the exact in-body date
line quoted verbatim, how many distinct registrable names you counted on the page, and how you counted
them. If the namespace has no such artifact, say so and name what you enumerated to establish it.

NEVER state a number you did not derive. A page you could not fetch is not a page with zero names.
`

const SCHEMA = {
  type: 'object',
  required: ['namespace', 'found', 'listings', 'what_was_enumerated'],
  properties: {
    namespace: { type: 'string' },
    found: { type: 'boolean', description: 'true only if you fetched a dated list of names' },
    listings: {
      type: 'array',
      maxItems: 6,
      items: {
        type: 'object',
        required: ['url', 'bytes', 'in_body_date', 'names_counted', 'how_counted'],
        properties: {
          url: { type: 'string' },
          bytes: { type: 'integer' },
          in_body_date: { type: 'string', description: 'quoted verbatim from the page, or "none, capture stamp only"' },
          names_counted: { type: 'integer' },
          how_counted: { type: 'string' },
          whole_tree: { type: 'string', description: 'how many sibling pages exist and how you know' },
        },
      },
    },
    who_ran_it: { type: 'string', description: 'who operated the namespace in 1996-2001, and on which host' },
    what_was_enumerated: { type: 'string', description: 'the CDX queries and hosts you actually ran, with row counts' },
    projected_names: { type: 'string', description: 'in-window names across the whole tree, and how you got there' },
  },
}

const NAMESPACES = [
  { key: 'nz', prompt: 'NAMESPACE: .nz, English share 0.9895. Waikato University ran it, then Domainz, then InternetNZ. Second levels co.nz, org.nz, net.nz, ac.nz, govt.nz, school.nz. Try domainz.net.nz, waikato.ac.nz, nzrs.net.nz, dnc.org.nz, isocnz.org.nz.' },
  { key: 'za', prompt: 'NAMESPACE: .za, English share 0.9682. Mike Lawrie ran it personally from Rhodes University for years and was unusually open about publishing the register. Try uniforum.co.za, frd.ac.za, apies.frd.ac.za, rucus.ru.ac.za, zadna.org.za, and anything at co.za administered by UniForum SA.' },
  { key: 'au', prompt: 'NAMESPACE: .au, English share 0.9904, the highest weight available. Robert Elz ran it from Melbourne University, then AUNIC, then auDA. The register already closed AUNIC, auDA and AARNet as having no bulk artifact, so read that row in docs/sources.md FIRST and do not repeat it. What it did NOT test: munnari.oz.au listing trees, Melbourne University computer science pages, and the pre-AUNIC hostmaster reports.' },
  { key: 'sg-hk-in', prompt: 'NAMESPACE: .sg 0.9476, .hk, .in 0.8361, .my, .ph. Each was run in-window by a university or national computer centre: NUS/Technet for .sg, HKU/JUCC for .hk, NCST/IISc and later ERNET for .in, MIMOS for .my, PHNET for .ph. Look for register listings on those hosts.' },
  { key: 'ca-il-others', prompt: 'NAMESPACE: .ca 0.8365 and any other namespace above 0.8 weight you can reach. The CA Domain Registry under John Demco at UBC ran a famously public approval process and its Usenet notices are ALREADY banked here, so read that row first: what is wanted is a LISTING artifact rather than the notices. Also consider .il, .ie siblings, .gs, .io 0.8111, .ac, .sh, and any second-level tree under .us that published a register.' },
]

phase('Probe')

const results = await pipeline(
  NAMESPACES,
  (ns) => agent(`${BRIEF}\n\n${ns.prompt}`, { label: `probe:${ns.key}`, phase: 'Probe', schema: SCHEMA }),
  (found, ns) => {
    if (!found || !found.found) return { ns: ns.key, found: false, detail: found || null }
    return agent(
      `${BRIEF}\n\nYou are the SCEPTIC for the ${ns.key} namespace. Another agent reports this:\n\n` +
      JSON.stringify(found, null, 2) +
      `\n\nRefute it. Default to found=false when unsure. Do these rather than reason about them:
      1. Re-fetch every URL. Report the status and byte count you got. If it 302s to zero bytes, that is
         a missing -L on their side, so retry with redirects followed before calling it dead.
      2. Read the in-body date yourself, with the HTML tags stripped first. A footer that spans a tag
         defeats a naive regex, and a page whose date falls OUTSIDE 1996-2001 must be dropped: exactly
         one of the 27 .ie pages carried a March 2002 footer and had to go.
      3. Re-count the names with the public suffix in mind. A count that includes the registry's own
         host, or counts www-prefixed forms separately, is inflated.
      4. Say whether the tree is COMPLETE or a fragment, and how many in-window names it really reaches.
      Correct the numbers. Set found=true only if a dated list of names genuinely fetched today.`,
      { label: `price:${ns.key}`, phase: 'Price', schema: SCHEMA },
    ).then((v) => ({ ns: ns.key, found: !!(v && v.found), proposed: found, verified: v }))
  },
)

const clean = results.filter(Boolean)
log(`${clean.filter((r) => r.found).length} of ${clean.length} namespaces have a dated register listing`)
return clean
