# Security

What can go wrong while collecting dated corpora for a public repository, and what to do when it does.
The detail behind any incident (hashes, hostnames, paths) lives in `private/security/` and never ships.

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
| 2026-09-03 | The collector host's login, as user and address, is in seven files of this repository's PUBLISHED history, and reachable from `main` and `live` themselves since the phase-4 squash merge of 2026-08-09. Current trees are clean, so it is visible only by reading history. Found while checking whether the `log/<branch>` tags were safe to push, so the tags did not cause it and were held | open, and only rotation remediates: deleting branches does NOT, because the two branches that carry it cannot be deleted. A first reading of this incident said `live` and `main` were clean; that was wrong, and the correction is the reason rotation is now the single recommendation | `private/security/`, with the affected refs and files. Neither value is repeated in any tracked file, which is the rule this predates |
