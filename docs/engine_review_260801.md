# Adversarial review of the English verification engine, 1 August 2026

Findings from two review passes over `src/ark/language.py`, briefed in opposite directions: one to
find pairs that could reach the English annual files wrongly, one to find pairs that could be
wrongly excluded. Every finding was reproduced before being accepted as a defect, and the four most
serious were checked against live archived pages.

This file ships with the delivery so the process can be inspected rather than taken on trust. The
report summarises it; this is the detail.

**All verdicts held at the time were discarded.** Their journals are retained under
`journals/lang_superseded/` with a note explaining what was wrong with each engine version, so a
discarded verdict remains reproducible rather than merely deleted.

---

## Confirmed defects, in order of severity

### 1. A replay could be answered with a capture from a different year

`web.archive.org` answers a replay request it cannot serve exactly with a redirect to the nearest
capture in time, in **any** year. The HTTP client followed it silently and reported success.

Reproduced live: `GET /web/19970601000000id_/http://1697.com/` returned 302 to
`/web/20001017120626id_/http://1697.com/`, followed, 200. A 1997 request answered with content from
October 2000.

**Why this was the worst of the ten.** The engine recorded the URL it had *asked* for, so a reviewer
refetching the stored URL would receive the same substitution and see agreement. The audit trail
would have confirmed the error rather than exposed it, which is the one property a provenance record
must never have. It is also the only route by which a single capture could satisfy two different
years.

Fixed: the fetcher returns the URL that answered, a sample whose timestamp year differs from the
target year is discarded, and `evidence_urls` records what was served.

### 2. The sampler preferred pages that are not the website

Selecting the largest archived record under a domain, with `matchType=domain` and no host or path
constraint, systematically finds third-party application chrome rather than site content.

- `1stflatrate.com` 2001 was admitted as an English website on an Ipswitch IMail login screen served
  from port 8383.
- Across the journals, 68 of the URLs behind `english` verdicts pointed at `cgi-bin`, `.pl`, `.cgi`,
  webmail, guestbooks, or non-web ports.
- `robots.txt` is indexed as `text/html` with status 200 and on a small site is frequently *longer*
  than the homepage, so the length sort put it first. Measured on `1125.com` 2001: the archive holds
  two URLs for that year, the homepage at 358 bytes and `robots.txt` at 785. Two domains were
  admitted on a `robots.txt` and nothing else.

Fixed: non-content paths, non-web ports and mail hosts are excluded from the candidate set before
sorting, so size ranks real pages rather than selecting among everything.

### 3. Placeholder detection skipped the pages that needed it

`is_non_site_text` returned False for any page over 1,000 characters before testing a single marker.

- `2000s.com` 2001 was admitted at confidence 1.000 on 1,060 characters of comma-separated category
  names: a monetised keyword link farm, 60 characters above the cutoff.
- `1pm.com` 2000 was admitted on 221 characters announcing that the site had moved elsewhere.

Fixed three ways, because three shapes of non-site need three shapes of test. Unambiguous phrases
apply at any length, and forwarding-notice phrases were added. Ambiguous phrases such as "under
construction" are judged on what remains once the phrase is removed, because length alone cannot
separate a 299-character plumber's page mentioning it in passing from a 55-character stub (282
characters of residual text against 38). And a structural test catches the link-farm family, which
contains no giveaway phrase at all: many separators, almost no sentences.

### 4. A truncated sample could settle a verdict

A failed page fetch was a non-event: the loop continued and whatever survived decided the verdict.
The guard only fired when *every* fetch failed.

Measured across the journals: **124 of 839 `english` verdicts, 14.8%, were decided on one page after
another fetch failed**, and 445 of 839 rested on a single usable capture.

Fixed: a verdict reached on a truncated sample leaves the pair unsettled for a later run, and
`samples` is now a budget of usable reads rather than of attempts, so a pair whose largest captures
are unreachable no longer settles while unread candidates sit in the same index response.

### 5. Nothing could ever re-judge a pair

`write_lang_targets` excluded any pair that had a `domain_language` row at all. So every defect above
became permanent at the moment it produced output, and this is why the same class of problem has now
cost this project two rounds of discarded verdicts.

Fixed structurally. Every verdict carries the `ENGINE_VERSION` that produced it, only current-version
verdicts can reach an annual file, and a pair leaves the work queue only when asking again could not
change the answer. The single exception is `no_capture_in_year`, which is final because the archive's
index for a past year does not grow.

### 6. "No capture in this year" rested on a filtered question

The capture query filters on `statuscode:200` and `mimetype:text/html`. A year in which the archive
holds only redirects or plain text answers it empty, and the engine recorded that as though the
archive held nothing.

Three of three answerable live probes contradicted a stored "no capture" claim: `10thgrade.com` 2000
had ten or more rows, `1981.com` 1999 had three, `844.com` 1999 had two.

Fixed: an empty filtered result triggers a second, completely unfiltered index probe. Nothing at all
(`no_capture_in_year`), something but not readable HTML (`no_readable_html_capture`), or the probe
itself failed, in which case the pair stays unsettled and no verdict is written.

### 7. Duplicate documents consumed the sample

`collapse=urlkey` collapses identical index keys, and `http://www.foo.com:80/`, `http://foo.com/` and
`http://www.foo.com/index.htm` are three keys for one page. Measured: 8 of 181 two-sample records
read the same document twice, spending the whole sample on the front page.

Fixed: candidates are collapsed on a normalised document key before sampling.

### 8. Escaped markup was counted as prose

`HTMLParser` with `convert_charrefs=True` turns `&lt;p&gt;` into the literal text `<p>`, so a page
that escaped its own markup fed tag names, attribute names and URLs to the classifier. Those tokens
are ASCII and read as English, which biases a non-English page carrying an escaped-HTML block toward
admission. Confirmed in a shipped verdict, `0f3.com` 2001, whose extracted text included `href`,
`body`, `p`, `br` and a hostname.

Fixed: escaped tags are stripped after extraction.

### 9. Gzip-encoded captures decoded to noise

A capture whose original response carried `Content-Encoding: gzip` replays as compressed bytes, which
decode to binary garbage and score as unusable text, silently excluding the pair. Fixed by sniffing
the gzip magic number and decompressing.

### 10. `--samples 0` would settle the entire work list

`captures[:0]` is empty, so the scoring path was reached with nothing collected and no fetch failures
recorded, the pair was settled at status 200 and written as `undetermined`. One typo in a command
would have settled every remaining pair as rejected, in minutes, irreversibly under defect 5. Fixed:
the value is validated.

---

## Verified live after the fixes

| pair | before | after |
|---|---|---|
| `2000s.com` 2001 | `english`, share 1.000 | `undetermined`, `non_site_text` |
| `1pm.com` 2000 | `english`, share 1.000 | `undetermined`, `non_site_text` |
| `62.com` 2001 | `english`, on a `robots.txt` | `undetermined`, after reading 7 real pages |
| `1stflatrate.com` 2001 | `english`, on an IMail login | `english`, on the site's own pages |

The last row is the outcome worth noticing. A correct admission was kept, on correct evidence, which
is what distinguishes a fix from a blanket tightening.

---

## Findings considered and not acted on

**Collecting `alt` attribute text.** Both passes suggested it, since image-heavy pages of this era
often carried their English in `alt=`. Declined: `alt` text is frequently English boilerplate
("click here", "home", "email us") on non-English sites, so admitting it would bias toward
admission. The asymmetry decides it. A false admission is a claim made to a reviewer; a false
exclusion leaves a pair retryable, and under fix 5 it now genuinely is retryable. Recorded as a
limitation instead.

**Pooling text across captures below the 200-character threshold.** A site with three 150-character
English pages currently scores undetermined while the same 450 characters on one page scores
English, and section 6's "across the sampled captures" arguably points at the pooled reading.
Measured: 30 answered pairs in the journals had pooled text over the threshold with no individual
capture above it. Not changed under time pressure, because it alters what a verdict would be and so
requires an engine-version bump and another discard. It is the first change to make after the next
snapshot.

**Merging the filtered capture query with the unfiltered probe.** One request instead of two on the
roughly quarter of pairs that need the probe, worth about 10% of total requests. Same reason for
deferring: it changes the meaning of two reason values, so it needs a version bump.
