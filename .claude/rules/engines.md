---
paths:
  - scripts/engines/**
  - scripts/sources/**
---

# Collectors and anything that leaves the machine

- The politeness rules are in `docs/rules.md`, section Engines and politeness: two archive
  clients maximum, honest User-Agent, honour `Retry-After`, back off on 429/503/504.
- Read the terms in full, and the whole robots.txt of the host in the download URL, before the
  first request. The hosts that refuse us by name are listed in `docs/traps.md`; so are the
  measured tier costs and the 403-is-not-a-refusal case.
- A collector takes an absolute deadline and outlives the session. Restart a loop after editing
  what it imports.
- Watch the hit rate, not the query rate: `just engines` prints both.
- A journal is written first and priced afterwards; collectors write no evidence and so never
  hold the store's write lock.
- An AV alert on a dated mail or Usenet corpus is corpus fidelity, not compromise. The handling
  is in `docs/security.md`.
