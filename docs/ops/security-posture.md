# Security posture

What can go wrong while collecting dated corpora for a public repository, and what to do when it does.
The detail behind any incident (hashes, hostnames, paths) lives in `private/security/` and never ships.

**Deliberately not called `SECURITY.md`** (Ivo, 2026-09-03). GitHub treats a file of that name in
the root, `docs/` or `.github/` as the repository's security policy and advertises it on the public
front page and in the Security tab. This page is an operating note for whoever is collecting, not a
vulnerability-disclosure policy, and the incident table below says where to look for what leaked. It
stays public; it just stops being the thing GitHub puts a banner on.

## Threat model

- Dated mail and Usenet corpora carry the era's worms as message content. That is corpus fidelity,
  not compromise: parse archives in-stream, never extract attachments, delete probe bytes after
  measurement.
- The repository is public. Every commit message, issue and pushed file is world-readable the moment
  it lands, so none of them names a host, an address, a mail body or personal context.
- The fleet's token lives only in the fleet's secrets. It is never in a tracked file, a dotenv under
  the tree, a log or a commit.
- `robots.txt` is read whole before the first request to a host, and a by-name refusal anywhere in
  the file is honoured, whatever the `User-agent: *` block above it allows. The refusal list is
  in `CLAUDE.md`.
- Nothing under `private/` ships. The delivery archive is built from the tracked tree with
  `export-ignore` applied, and a test pins the names that must stay out.

## On an antivirus alert

1. Do not act on the alert's name alone. Hash the flagged file and match the alert's hashes against
   it; an alert on a file we never downloaded is a different problem.
2. If the hashes match and the file is a downloaded corpus, the hit is content. Confirm it is inert
   (nothing was extracted, nothing ran) and keep the file; the corpus is the evidence.
3. Write the detail to `private/security/` and add a row to the table below. No hashes here.

## Incidents

| date | what | verdict | detail |
|---|---|---|---|
| 2026-09-01 | Antivirus flagged the Klez.H worm inside a downloaded newsgroup zip | inert; corpus fidelity, not compromise | `private/security/` |
| 2026-09-03 | The collector host's login, a username against a PRIVATE-RANGE address plus the remote path, is in seven files of published history, reachable from `main` and `live` since the phase-4 squash merge of 2026-08-09. Current trees are clean, so it is visible only by reading history | LOW, closed on assessment. The address is RFC 1918 and not routable from the internet, so it is not somewhere an outsider can reach; no key, password or port accompanies it, and no public address for that host appears anywhere in the history. Two earlier readings of this incident overstated it, first calling branch deletion a remediation and then calling it reconnaissance material. Rotation is hygiene here, not urgent | `private/security/`. The real finding is the guard gap it exposed, fixed the same day: `ark.hygiene` flagged only globally routable addresses, so this exact line would still have passed. A `host login` rule now refuses a login against an address in any range, with the RFC 5737 documentation ranges skipped for fixtures |
