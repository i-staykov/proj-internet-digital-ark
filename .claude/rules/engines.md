---
paths:
  - scripts/engines/**
  - scripts/sources/**
---

# Collectors and anything that leaves the machine

- Politeness and the client cap: `docs/lore/rules.md`, section Engines and politeness.
- Read the terms and the host's whole robots.txt before the first request. Hosts that refuse us
  by name, the measured tier costs and the 403 case are in `docs/lore/traps.md`.
- A collector takes an absolute deadline and outlives the session. Restart a loop after editing
  what it imports.
- A journal is written first and priced afterwards; collectors write no evidence and so never
  hold the store's write lock.
- An AV alert on a dated mail or Usenet corpus is corpus fidelity, not compromise. The handling
  is in `docs/ops/security-posture.md`.
