---
name: hunt-family
description: Open a new source family: pick a lens never tried, screen it against the closed register and the measured killers, then report the result positive or negative. Use when choosing what to hunt next.
---

# Hunt a new source family

`docs/rules.md` has the hunting rules and Ding's own list of shapes he expects tried;
`docs/discovery.md` is the long form; `docs/laws.md` holds the killers and the arithmetic.

1. One lens per cycle, and never the same lens twice running. Rotate even when the last one paid.
2. Kill it from the desk first: `grep -n '<family>' docs/sources-closed.md`, then
   `grep -n '<family>' docs/sources.md`. A family already closed is not re-tested, and a brief
   that calls a closed lens untried wastes the whole run.
3. Screen the shape against the eight laws in `docs/laws.md` before any request. Undated is
   fatal; so are terms we do not hold. IA-derived cannot be net-new. Ask which YEAR the artifact
   can add to names already held, and aim at 2001.
4. Read the terms in full, and the whole robots.txt of the host in the download URL, before the
   first request. `docs/traps.md` lists the hosts that refuse us by name.
5. Price it with the `price-source` skill. A measured negative with a reason is a result.
6. Log it in `docs/sources.md` either way, so nobody re-tests it.

For a fan-out across several candidate shapes at once, the five `hunt-*` workflows already do
that; this skill is the single-lens protocol and the screen.

If two hunts in a row return nothing, change the method, not the effort: ask what KIND of
artifact has never been looked for, not which host has not been tried.
