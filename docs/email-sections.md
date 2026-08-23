# Email sections for the current round

**Read by `scripts/fill_report.py`, one block per `## ` heading, in the order the template's stubs
appear.** It lives here rather than in the draft because `private/email-draft.md` is regenerated and
prose typed into it is destroyed by the next fill. Export-ignored, so it never reaches the reviewer.

Written for the threshold being met, since that is the only condition under which we send.

## opening

This round passes the 5% threshold you set.

## substance

The round came from three routes, all self-dating or split-tested, and none of them new to you in
principle:

- **Registry creation dates**, read from RDAP rather than a compilation, as `whois_creation`. Used
  strictly as your rule 6 requires: a creation date in 1998 writes 1998 and no other year, and no later
  year is inferred from the domain still existing. I priced the opposite reading, treating creation plus
  present existence as an interval, at over 1.7 million equivalent-English, then found your rule forbids
  it and built nothing. Falsified before admitting: no TLD may predate its own delegation, checked
  across every TLD in the set.
- **Archive capture timestamps** from the Wayback CDX index, as `cdx_timestamp`, with the queue ordered
  by measured yield per query rather than by TLD weight. Ranking on weight alone puts namespaces
  delegated in 2013 at the head, which was worth nothing.
- **Dated Usenet announcements**, admitted only under the corroboration split: a hostname somebody typed
  earns a year only if a different source already dates that domain, and the corpus is excluded from
  corroborating itself.

The useful negative is about our own data rather than a source. The candidate pool accumulated 575,417
names that cannot ever have existed, strings under three namespaces that have never allowed arbitrary
registration, mostly from address extraction where anti-spam munging garbles text. **Not one reached an
annual file.** Every shipped `.mil`, `.gov` and `.edu` domain carries independent attestation, 100.0% of
them, on the three highest-weighted namespaces in the model. The evidence wall was tested by accident and
held, which I would rather report than a source count.

The report leads with the discovery architecture rather than the totals, because that is the part you
said the project is for: what bounds an agent nobody is watching, why the collectors outlive the agent,
and the four measurement rules that each cost a day to learn.
