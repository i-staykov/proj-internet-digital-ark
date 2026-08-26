# Email sections for the current round

**Read by `scripts/fill_report.py`, one block per `## ` heading, in the order the template's stubs
appear.** It lives here rather than in the draft because `private/email-draft.md` is regenerated and
prose typed into it is destroyed by the next fill. Export-ignored, so it never reaches the reviewer.

Written for the threshold being met, since that is the only condition under which we send.

## opening

This round passes the 5% threshold you set.

## substance

Eleven sources are new this round and every one is a machine-written record rather than a person's
list. The largest came from a file already on disk. The 1999 RIPE database snapshot had been read for
one attribute, the domain name, and dated to the file's own instant; each object also carries a
`changed:` line per update applied to it, each with its own date. An object cannot be modified before
it exists, so those lines reach 1996, 1997 and 1998, which the snapshot's own date cannot: 399,401
further pairs and 58,398 equivalent-English, with no new download. It is used with the written
permission of the RIPE NCC, gratefully acknowledged, and the parser reads the domain name and nothing
else, enforced by tests that fail on a leaked address or telephone number.

The method finding is about which names to ask about. Asking RDAP about the 2,395,205 undated names
in our candidate pool returns nothing: 602 queries, drawn once from the head and once seeded-random,
produced zero in-window creation dates, because 73% of that pool answers 404 against 21.6% for
domains we hold. A name no crawler captured is usually a name that was never much of a site. So we
priced four invented populations against each other instead, and sibling names, every `.com`, `.net`
and `.org` label we hold re-suffixed to the other two, returned 14,205 in-window creation dates from
150,000 queries. Invented two-word compounds returned exactly zero from 859. A registry can only date
a name that survived, so inventing plausible survivors beats enumerating known casualties.

The gate is unchanged and is in code rather than in habit: no class may date a year until a human has
written its decision, and `ark ingest` refused twice this round until the decision existed. Eleven
sources, eleven written decisions, each with the primary link and the measurement it was approved on.
Section 2 of the report lists all eleven with what dates one item and where the artifact is, so any of
them can be opened and checked.
