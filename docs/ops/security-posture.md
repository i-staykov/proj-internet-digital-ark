# Security posture

What can go wrong while collecting dated corpora for a public repository, and what to do when it does.

Not `SECURITY.md`: GitHub advertises a file of that name in the root, `docs/` or `.github/` as the
repository's vulnerability-disclosure policy, and this is an operating note.

## Threat model

- Dated mail and Usenet corpora carry the era's worms as message content. That is corpus fidelity,
  not compromise: parse archives in-stream, never extract attachments, delete probe bytes after
  measurement.
- The fleet's token lives only in the fleet's secrets. It is never in a tracked file, a dotenv under
  the tree, a log or a commit.
- The delivery ships the code as `git archive HEAD`, so `export-ignore` applies;
  `tests/test_delivery_privacy.py` pins what stays out.

## On an antivirus alert

1. Do not act on the alert's name alone. Hash the flagged file and match the alert's hashes against
   it; an alert on a file we never downloaded is a different problem.
2. If the hashes match and the file is a downloaded corpus, the hit is content. Confirm it is inert
   (nothing was extracted, nothing ran) and keep the file; the corpus is the evidence.
3. Write the detail to `private/security/` and add a row to the table below. No hashes here.

## Incidents

| date | what | verdict | detail |
|---|---|---|---|
| 2026-09-01 | Antivirus flagged the Klez.H worm inside a downloaded newsgroup zip | inert; corpus fidelity, not compromise | n/a |
| 2026-09-03 | A collector login against a private-range address is in published history; current trees are clean | LOW: RFC 1918, not routable, and no key, password, port or public address beside it | `ark.hygiene` refuses a login against an address in any range, RFC 5737 ranges skipped for fixtures |
