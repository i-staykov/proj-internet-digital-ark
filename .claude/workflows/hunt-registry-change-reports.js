export const meta = {
  name: 'hunt-registry-change-reports',
  description: 'Registry change reports: fortnightly new/deleted name lists with dates. MYNIC refuted the register closure that said these do not exist',
  phases: [
    { title: 'Probe', detail: 'one region each, CDX-enumerate registry hosts for change reports' },
    { title: 'Verify', detail: 'per region: re-fetch, read the in-body date, price against the live store' },
  ],
}

// Repo root. Defaults to the working directory; set ARK_REPO when the checkout is elsewhere.
const REPO = globalThis.process?.env?.ARK_REPO ?? '.'

const BRIEF = `
Repository: ${REPO}. READ-ONLY: create, edit and delete nothing in it.

A CLOSURE IN OUR OWN REGISTER HAS JUST BEEN REFUTED, AND THAT IS WHY THIS LENS IS OPEN.

\`docs/sources.md\` contains a row, "Dated announcements of new domain registrations (2026-08-18)",
which concluded: "a registry of this era published either dates without names (statistics) or names
without dates (a zone snapshot). The intersection existed only where a registry ran its approval
process in public, and that was exactly one namespace: the CA Domain Registry."

**That is false.** MYNIC, the Malaysian registry, published a fortnightly "Domain Name Listing" at
\`mynic.net.my/my/stats/<month><year>-<half>.htm\` giving every name that ENTERED or LEFT the register
in that fortnight, under per-day headings inside the page body. 34 archived pages, 12,902 distinct
\`.my\` names, 13,124 dated (domain, year) pairs, 11,445 of them net-new against our store. So the
intersection does exist and one registry is unlikely to be the only one.

YOUR JOB: find more registry CHANGE reports. Not a zone snapshot, not a whois form, not an aggregate
count. A dated list of names ADDED to or REMOVED from a register: "new registrations this month",
"domains deleted", "recently registered", "pending deletion", a fortnightly or monthly bulletin, a
registry newsletter with a name annex, an FTP drop of daily deltas.

WHY THIS SHAPE IS WORTH MORE THAN A SNAPSHOT. A change report asserts registration at a stated
instant, which is what makes it master-eligible rather than a mere mention. And unlike an accumulating
list it needs no first-appearance diff: each edition is already a diff.

TWO SCREENS TO APPLY BEFORE FETCHING, both earned today:
 1. **One operator, one database.** \`.ie\` paid 18,038 EE because a single university computing service
    regenerated a single register onto a static tree. \`.za\` paid almost nothing because eleven second
    levels were separately administered, most accepting applications by e-mail to a named individual,
    so there was no single machine to regenerate. Ask who held the database before you ask what the
    archive holds.
 2. **Read the page for its own generator.** The \`.my\` pages carry
    \`META NAME="Generator" CONTENT="Microsoft Word 97"\` on 33 of 34, and 21 carry
    \`saved from url=(0022)http://internet.e-mail\`, so they are a registry report hand-published
    through Word rather than a machine regeneration. That matters enormously: a hand-assembled list
    takes the corroboration split and its value falls 15x, from 8,675 EE to 580. Report the generator
    string, the whitespace consistency and any malformed entries, so a human can rule on the split.

**PENDING APPLICATIONS ARE NOT REGISTRATIONS.** The \`.ie\` tree published \`stalled.html\` and the \`.nz\`
registry published \`pending.html\`; both list names nobody had registered yet, and reading either as a
register manufactures registrations that never happened. Our parser refuses them by filename. If the
only listing you find is a pending or applied-for queue, the answer is found=false.

THE METRIC. Each (domain, year) scores its TLD's English share: au 0.9904, nz 0.9895, uk 0.9813,
ie 0.9744, za 0.9682, ph 0.9483, sg 0.9476, us 0.9261, in 0.8361, ca 0.8365, my 0.7580, hk 0.4784,
com 0.6321, net 0.4530. Weights live in \`src/ark/data/tld_english_share.json\` as an \`eng\` row in
percent; read them there rather than guessing, and say which you used.

ALREADY DONE, DO NOT REPEAT: .ie (banked, 18,846 EE), .my (found, above), .za (measured, 4,462 EE),
.ph (measured, 467 EE), .in ISP roster (62.7 EE), .au, .ca, .nz, .sg, .hk and the .us
\`domain-delegated.txt\` file, which is a CLOSED FAMILY in the register worth 1 to 2 net-new pairs and
was re-proposed today by mistake. Grep \`docs/sources.md\` before proposing anything.

HOW TO LOOK. Enumerate with the CDX index rather than guessing paths:
\`https://web.archive.org/cdx/search/cdx?url=<host>&matchType=domain&collapse=urlkey&limit=3000&output=json\`
Use https, follow redirects (Wayback 302s to the nearest capture and a fetch without redirects returns
zero bytes), and retry: the archive refuses roughly half our connections today, so one failure is not a
negative result. A CDX zero must be proved against a control query that returns rows. \`url=<tld>\` with
\`matchType=domain\` over a bare TLD returns HTTP 403 and cannot be used.

NEVER state a number you did not derive, and say how you derived each one.
`

const SCHEMA = {
  type: 'object',
  required: ['region', 'found', 'reports', 'what_was_enumerated'],
  properties: {
    region: { type: 'string' },
    found: { type: 'boolean', description: 'true only if you fetched a dated list of ADDED or REMOVED names' },
    reports: {
      type: 'array',
      maxItems: 8,
      items: {
        type: 'object',
        required: ['url', 'bytes', 'in_body_date', 'names_counted', 'how_counted', 'added_or_removed'],
        properties: {
          url: { type: 'string' },
          bytes: { type: 'integer' },
          in_body_date: { type: 'string', description: 'quoted verbatim, or "none, capture stamp only"' },
          names_counted: { type: 'integer' },
          how_counted: { type: 'string' },
          added_or_removed: { type: 'string', description: 'does the page assert these names entered the register, left it, or were merely applied for' },
          generator: { type: 'string', description: 'any Generator meta tag, save-from comment, or sign of hand assembly' },
        },
      },
    },
    who_held_the_database: { type: 'string', description: 'one operator or many, and how you established it' },
    whole_tree: { type: 'string', description: 'how many editions exist in the archive and how you counted them' },
    what_was_enumerated: { type: 'string', description: 'the CDX queries and hosts you ran, with row counts' },
    priced: { type: 'string', description: 'net-new pairs and EE against the store if you got that far, and against WHICH file or database' },
  },
}

const REGIONS = [
  { key: 'asia-pacific', prompt: `REGION: Asia-Pacific other than .my, .sg, .hk, .in, .ph, .au, .nz, all done. Try .th (THNIC, AIT), .kr (KRNIC), .tw (TWNIC), .id (IDNIC), .vn, .lk (LK Domain Registry, run by one person at Moratuwa for decades), .pk, .bd, .np, .mn, .bn, .fj, .pg, .ws, .to, .nu, .cc. Several were run by a single academic on a single machine, which is the shape that pays. Weights: most are low, so say plainly when a find is worth little, but .ws, .to, .nu and .cc were sold internationally to English-speaking registrants and .fj, .pg and .lk skew English.` },
  { key: 'europe-english', prompt: `REGION: Europe, English-facing or English-adjacent namespaces. .ie is banked; try .is, .mt, .cy, .gi, .im, .je, .gg, .fo, .gl, .li, .lu, .ee, .lv, .lt, .si, .hr, .mk, .al, .ba, .md, .sm, .ad, .mc, .va. Also the pan-European bodies that published registry data before EURid existed: RIPE NCC's ncc.ripe.net, RARE, TERENA, EUNET, and the national research networks that held ccTLD delegations before commercial registries did. Say which weights you read and from where.` },
  { key: 'americas-caribbean', prompt: `REGION: the Americas and Caribbean excluding .us and .ca, both done. Many Caribbean namespaces are English-speaking and were run by one person or one university: .bm, .bb, .bs, .jm, .tt, .ag, .ai, .aw, .bz, .dm, .gd, .kn, .lc, .vc, .vg, .ky, .ms, .tc, .gy, .sr, .fk. Also .gs, .sh, .ac, .io and .tk, all administered from a single office and sold internationally. And Latin America's registries that published bulletins: NIC Mexico, NIC Chile (which ran a famously public dispute and listing process), NIC Argentina, NIC Brazil's FAPESP.` },
  { key: 'africa-middle-east', prompt: `REGION: Africa and the Middle East. .za is measured and closed; try .ke, .ng, .gh, .tz, .ug, .zm, .zw, .mw, .bw, .na, .sz, .ls, .mu, .sc, .eg, .ma, .tn, .il, .tr, .ae, .sa, .jo, .lb, .kw, .bh, .qa, .om. English-facing and often run by one university computer centre: Randy Bush and the NSRC helped set several up and their records are unusually well documented. Note that .il weighs 0.1958 and most Arabic-script namespaces are low weight, so screen on weight before spending time.` },
  { key: 'gtld-and-registrars', prompt: `REGION: not a ccTLD at all. The gTLD side and the registrar layer. Network Solutions published registration reports and press material; the post-1999 shared registry brought dozens of accredited registrars, each publishing their own new-registration or expiring-domain pages; the drop-catching and aftermarket industry published deletion lists. Also consider registrar newsletters, ICANN registrar monthly reports, and the "recently registered domains" pages that predate 2002. Screen hard on killer 2: an aftermarket list of names FOR SALE asserts nothing about registration in that year, whereas a registry deletion queue does. .com 0.6321 and .net 0.4530 are the weights, and the volume here could be far larger than any ccTLD.` },
]

phase('Probe')

const results = await pipeline(
  REGIONS,
  (r) => agent(`${BRIEF}\n\n${r.prompt}`, { label: `probe:${r.key}`, phase: 'Probe', schema: SCHEMA }),
  (found, r) => {
    if (!found || !found.found) return { region: r.key, found: false, detail: found || null }
    return agent(
      `${BRIEF}\n\nYou are the SCEPTIC for ${r.key}. Another agent reports this:\n\n` +
      JSON.stringify(found, null, 2) +
      `\n\nRefute it. Default to found=false when unsure. Do these rather than reason about them.
      1. Re-fetch every URL and report the status and byte count YOU got. A 302 to zero bytes is a
         missing redirect follow on their side, not a dead page.
      2. Read the in-body date yourself with the HTML tags stripped, and check it falls in 1996-2001.
         Exactly one of 27 .ie pages carried a 2002 footer and had to be dropped.
      3. Re-count the names. Exclude the registry's own hostnames, www- prefixed duplicates and bare
         public suffixes. One agent today overcounted .us by 300 by keeping public suffixes, and
         another undercounted .ph by 31 by reading only one of three columns.
      4. Check whether the page asserts REGISTRATION or only APPLICATION. A pending queue is not a
         register.
      5. Report the Generator meta tag and any sign of hand assembly, because that decides whether the
         corroboration split applies and the split is worth 15x on the .my artifact.
      6. Price it against the LIVE STORE at data/ark.duckdb if you can open it read-only, and say so;
         otherwise against output/internet-digital-ark-1996-2001/baseline/merged260821 plus
         output/netnew. **Do not price against legacy-data**: that is the SUPERSEDED original baseline
         and an agent did exactly that today, overstating a source by about 1,000 EE.
      7. Grep docs/sources.md for the artifact by name and by population. One agent today re-proposed a
         family closed on 2026-08-18 and quoted a figure that row exists to refute.
      Correct every number and say how you checked it.`,
      { label: `verify:${r.key}`, phase: 'Verify', schema: SCHEMA },
    ).then((v) => ({ region: r.key, found: !!(v && v.found), proposed: found, verified: v }))
  },
)

const clean = results.filter(Boolean)
log(`${clean.filter((x) => x.found).length} of ${clean.length} regions hold a dated registry change report`)
return clean
