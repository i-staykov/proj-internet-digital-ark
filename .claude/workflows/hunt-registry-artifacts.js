export const meta = {
  name: 'hunt-registry-artifacts',
  description: 'One agent per namespace: an archived register LISTING or a dated CHANGE report, the two shapes that paid 18,769.9 EE for .ie and 11,445 net-new pairs for .my',
  phases: [
    { title: 'Probe', detail: 'one namespace or region each, CDX-enumerate the registry hosts' },
    { title: 'Verify', detail: 'per namespace: re-fetch, read the in-body date, re-count, price against the live store' },
  ],
}

// Repo root. Defaults to the working directory; set ARK_REPO when the checkout is elsewhere.
const REPO = globalThis.process?.env?.ARK_REPO ?? '.'

const BRIEF = `
Repository: ${REPO}. READ-ONLY: create, edit and delete nothing in it.

TWO SHAPES HAVE PAID, and you are looking for either one in a namespace that has neither.

**A register LISTING.** The IE Domain Registry published its WHOLE .ie register as static A-Z pages
at domainregistry.ie/statistics/{0-9,a..z}-doms.html, machine-generated from the live register, each
page carrying its own in-body line, verbatim: "Last updated automatically at 14:51 GMT on Friday, 21
December 2001". The Wayback Machine captured them: 24,805 distinct .ie names, banked at 19,263
net-new pairs worth 18,769.9 EE (\`iedr_register\`).

**A CHANGE report.** MYNIC published a fortnightly "Domain Name Listing" at
\`mynic.net.my/my/stats/<month><year>-<half>.htm\` giving every name that ENTERED or LEFT the register
in that fortnight, under per-day headings in the page body. 34 archived pages, 12,902 distinct \`.my\`
names, 13,124 dated pairs, 11,445 net-new. This REFUTED our own register row of 2026-08-18, which had
concluded that a registry of this era published either dates without names or names without dates and
that the intersection existed in exactly one namespace. It does exist, and one registry is unlikely to
be the only one.

WHY THEY PAY, so you can recognise the shape:
 - Machine-generated, so no name on the page was typed by a human and no corroboration split applies.
 - The date is INSIDE the artifact, not just the capture stamp.
 - A register regeneration ASSERTS registration at a stated instant: the same instrument as a zone file
   or a registry survey, not the same as a directory listing names it happens to know.
 - A listing is the complete namespace A to Z, so nothing is selected for fame. A change report needs no
   first-appearance diff at all: each edition is already a diff.

YOUR JOB: find either artifact for the namespace you are given. Not the registry's home page, not a
statistics summary, not an aggregate count, not a modern zone-file programme, not a whois form. A LIST
OF NAMES with a date on it, or a dated list of names ADDED to or REMOVED from a register. The registry
of that era may have published it under any of: /statistics/, /lists/, /registered/, /domains/, /db/,
/zone/, /reports/, an FTP tree, a monthly bulletin, a registry newsletter with a name annex, a
university computer-centre page, or the national research network that ran the namespace before a
company did.

TWO SCREENS BEFORE YOU FETCH:
 1. **One operator, one database.** Ask who HELD the register before asking what the archive holds.
    \`.ie\` paid because a single university computing service regenerated one register onto a static
    tree. \`.za\` paid almost nothing because eleven second levels were separately administered, most
    accepting applications by e-mail to a named individual, so there was no single machine to regenerate.
 2. **Read the page for its own generator.** The \`.my\` pages carry
    \`META NAME="Generator" CONTENT="Microsoft Word 97"\` on 33 of 34, and 21 carry
    \`saved from url=(0022)http://internet.e-mail\`, so they are a registry report hand-published through
    Word rather than a machine regeneration. That matters enormously: a hand-assembled list takes the
    corroboration split and its value falls 15x, from 8,675 EE to 580. Report the generator string, the
    whitespace consistency and any malformed entries, so a human can rule on the split.

**PENDING APPLICATIONS ARE NOT REGISTRATIONS.** The \`.ie\` tree published \`stalled.html\` and the \`.nz\`
registry published \`pending.html\`; both list names nobody had registered yet, and reading either as a
register manufactures registrations that never happened. Our parser refuses them by filename. If the
only listing you find is a pending or applied-for queue, the answer is found=false.

THE METRIC. Each (domain, year) scores its TLD's English share: au 0.9904, nz 0.9895, uk 0.9813,
ie 0.9744, za 0.9682, ph 0.9483, sg 0.9476, us 0.9261, in 0.8361, ca 0.8365, my 0.7580, hk 0.4784,
com 0.6321, net 0.4530. Weights live in \`src/ark/data/tld_english_share.json\` as an \`eng\` row in
percent; read them there rather than guessing, and say which you used.

ALREADY DONE, DO NOT REPEAT: .ie (banked, above), .my (found, above), .za (measured, 4,462 EE),
.ph (measured, 467 EE), .in ISP roster (62.7 EE), the .au family (AUNIC, auDA and AARNet are closed as
having no bulk artifact), .ca's Usenet approval notices (banked; a LISTING artifact would be new), .nz,
.sg, .hk, and the .us \`domain-delegated.txt\` file, a CLOSED FAMILY worth 1 to 2 net-new pairs that has
been re-proposed by mistake. Run \`just find <term>\` before proposing anything.

HOW TO LOOK, cheapest first:
 1. Work out who actually ran the namespace in 1996-2001. It was very often a university computing
    service or a national research network, not today's registry company, and the artifact lives on
    THAT host. UCD Computing Services ran .ie, which is why the .ie pages are on domainregistry.ie.
 2. Enumerate with the CDX index rather than guessing paths:
    \`https://web.archive.org/cdx/search/cdx?url=<host>&matchType=domain&collapse=urlkey&limit=3000&output=json\`
    then read the path list for anything that looks like a listing. A CDX zero must be proved against a
    control query that returns rows, because a wrong parameter and an empty archive look identical.
    \`url=<tld>\` with \`matchType=domain\` over a bare TLD returns HTTP 403 and cannot be used.
 3. Only then fetch pages. Use https and follow redirects: Wayback 302s each URL to its nearest capture,
    and a fetch without redirects returns zero bytes, which reads exactly like a dead page.
 4. web.archive.org refuses roughly half our connections, so retry with a short wait; one failure is not
    a negative result.

WHAT TO REPORT for each candidate: the URL, its byte count, the exact in-body date line quoted verbatim,
whether the page asserts names ENTERING, LEAVING or merely applied for, how many distinct registrable
names you counted and how you counted them. If the namespace has no such artifact, say so and name what
you enumerated to establish it.

NEVER state a number you did not derive. A page you could not fetch is not a page with zero names.
`

const SCHEMA = {
  type: 'object',
  required: ['namespace', 'found', 'artifacts', 'what_was_enumerated'],
  properties: {
    namespace: { type: 'string' },
    found: { type: 'boolean', description: 'true only if you fetched a dated list of names' },
    artifacts: {
      type: 'array',
      maxItems: 8,
      items: {
        type: 'object',
        required: ['url', 'bytes', 'in_body_date', 'names_counted', 'how_counted', 'asserts'],
        properties: {
          url: { type: 'string' },
          bytes: { type: 'integer' },
          in_body_date: { type: 'string', description: 'quoted verbatim from the page, or "none, capture stamp only"' },
          names_counted: { type: 'integer' },
          how_counted: { type: 'string' },
          asserts: { type: 'string', description: 'the register as it stood, names that ENTERED or LEFT it, or names merely applied for' },
          generator: { type: 'string', description: 'any Generator meta tag, save-from comment, or sign of hand assembly' },
          whole_tree: { type: 'string', description: 'how many sibling editions exist and how you know' },
        },
      },
    },
    who_held_the_database: { type: 'string', description: 'one operator or many, on which host, and how you established it' },
    what_was_enumerated: { type: 'string', description: 'the CDX queries and hosts you actually ran, with row counts' },
    priced: { type: 'string', description: 'in-window names across the whole tree, net-new pairs and EE if you got that far, and against WHICH file or database' },
  },
}

const NAMESPACES = [
  { key: 'nz', prompt: 'NAMESPACE: .nz, English share 0.9895. Waikato University ran it, then Domainz, then InternetNZ. Second levels co.nz, org.nz, net.nz, ac.nz, govt.nz, school.nz. Try domainz.net.nz, waikato.ac.nz, nzrs.net.nz, dnc.org.nz, isocnz.org.nz.' },
  { key: 'au-ca', prompt: 'NAMESPACE: .au 0.9904, the highest weight available, and .ca 0.8365. Robert Elz ran .au from Melbourne University, then AUNIC, then auDA; the CA Domain Registry under John Demco at UBC ran a famously public approval process. Both are closed for the artifacts already tested, so read those rows FIRST. What was NOT tested: munnari.oz.au listing trees, Melbourne University computer science pages, the pre-AUNIC hostmaster reports, and any .ca LISTING as opposed to the notices already banked.' },
  { key: 'asia-pacific', prompt: 'NAMESPACE: Asia-Pacific other than .my, .sg, .hk, .in, .ph, .au and .nz. Try .th (THNIC, AIT), .kr (KRNIC), .tw (TWNIC), .id (IDNIC), .vn, .lk (run by one person at Moratuwa for decades), .pk, .bd, .np, .mn, .bn, .fj, .pg, .ws, .to, .nu, .cc. Several were run by a single academic on a single machine, which is the shape that pays. Most weights are low, so say plainly when a find is worth little, but .ws, .to, .nu and .cc were sold internationally to English-speaking registrants and .fj, .pg and .lk skew English.' },
  { key: 'europe-english', prompt: 'NAMESPACE: Europe, English-facing or English-adjacent. .ie is banked; try .is, .mt, .cy, .gi, .im, .je, .gg, .fo, .gl, .li, .lu, .ee, .lv, .lt, .si, .hr, .mk, .al, .ba, .md, .sm, .ad, .mc, .va. Also the pan-European bodies that published registry data before EURid existed: RIPE NCC (ncc.ripe.net), RARE, TERENA, EUNET, and the national research networks that held ccTLD delegations before commercial registries did.' },
  { key: 'americas-caribbean', prompt: 'NAMESPACE: the Americas and Caribbean excluding .us and .ca. Many Caribbean namespaces are English-speaking and were run by one person or one university: .bm, .bb, .bs, .jm, .tt, .ag, .ai, .aw, .bz, .dm, .gd, .kn, .lc, .vc, .vg, .ky, .ms, .tc, .gy, .sr, .fk. Also .gs, .sh, .ac, .io 0.8111 and .tk, administered from a single office and sold internationally. And Latin America\'s registries that published bulletins: NIC Mexico, NIC Chile (a famously public dispute and listing process), NIC Argentina, NIC Brazil\'s FAPESP.' },
  { key: 'africa-middle-east', prompt: 'NAMESPACE: Africa and the Middle East. .za is measured and closed; try .ke, .ng, .gh, .tz, .ug, .zm, .zw, .mw, .bw, .na, .sz, .ls, .mu, .sc, .eg, .ma, .tn, .il, .tr, .ae, .sa, .jo, .lb, .kw, .bh, .qa, .om. English-facing and often run by one university computer centre: Randy Bush and the NSRC helped set several up and their records are unusually well documented. .il weighs 0.1958 and most Arabic-script namespaces are low weight, so screen on weight before spending time.' },
  { key: 'gtld-and-registrars', prompt: 'NAMESPACE: not a ccTLD at all. The gTLD side and the registrar layer. Network Solutions published registration reports and press material; the post-1999 shared registry brought dozens of accredited registrars, each publishing their own new-registration or expiring-domain pages; the drop-catching and aftermarket industry published deletion lists. Also registrar newsletters, ICANN registrar monthly reports, and "recently registered domains" pages that predate 2002. Screen hard: an aftermarket list of names FOR SALE asserts nothing about registration in that year, whereas a registry deletion queue does. .com 0.6321 and .net 0.4530, and the volume here could dwarf any ccTLD.' },
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
      `\n\nRefute it. Default to found=false when unsure. Do these rather than reason about them.
      1. Re-fetch every URL and report the status and byte count YOU got. A 302 to zero bytes is a
         missing redirect follow on their side, not a dead page.
      2. Read the in-body date yourself with the HTML tags stripped, and check it falls in 1996-2001: a
         footer that spans a tag defeats a naive regex, and exactly one of the 27 .ie pages carried a
         March 2002 footer and had to be dropped.
      3. Re-count the names with the public suffix in mind. Exclude the registry's own hostnames,
         www-prefixed duplicates and bare public suffixes. One agent overcounted .us by 300 by keeping
         public suffixes, and another undercounted .ph by 31 by reading only one of three columns.
      4. Check whether the page asserts REGISTRATION or only APPLICATION. A pending queue is not a register.
      5. Report the Generator meta tag and any sign of hand assembly, because that decides whether the
         corroboration split applies and the split is worth 15x on the .my artifact.
      6. Say whether the tree is COMPLETE or a fragment, and how many in-window names it really reaches.
      7. Price it against the LIVE STORE at data/ark.duckdb if you can open it read-only, and say so;
         otherwise against the newest baseline named in docs/registers/releases.md plus output/netnew.
         **Do not price against legacy-data**: that is the SUPERSEDED original baseline, and pricing
         against it overstated a source by about 1,000 EE.
      8. Run \`just find <term>\` for the artifact by name and by population. One agent re-proposed
         a family closed on 2026-08-18 and quoted a figure that row exists to refute.
      Correct every number and say how you checked it. Set found=true only if a dated list of names
      genuinely fetched today.`,
      { label: `verify:${ns.key}`, phase: 'Verify', schema: SCHEMA },
    ).then((v) => ({ ns: ns.key, found: !!(v && v.found), proposed: found, verified: v }))
  },
)

const clean = results.filter(Boolean)
log(`${clean.filter((r) => r.found).length} of ${clean.length} namespaces hold a dated register listing or change report`)
return clean
