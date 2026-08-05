# Source research, 5 August 2026

Session on branch `outsource-research`, 16:20 to 18:00 CEST. Brief: find new sources of 1996-2001
domain names carrying per-item year evidence, download them, and prove their worth by measurement.

**Headline, stated plainly: I found two sources that clear the bar, not three.** Both are measured
against the store rather than argued for. The third, fourth and fifth candidates are ranked below
with what is known and what is not, and none of them is presented as measured, because none is.

The scoring metric is equivalent-English domains, so every figure below is reported with its measured
mean TLD weight, not as a raw pair count.

---

## 1. Ranked recommendations

| # | Source | Access route | Licence | Dated artifact | Sample | Net-new pairs in sample | Extrapolated net-new pairs | Measured mean EE weight | Expected EE contribution |
|---|---|---|---|---|---|--:|--:|--:|--:|
| 1 | **Unexploited Usenet hierarchies** (`uk.*`, `aus.*`, `can.*`, `rec.*`, `comp.*`, and the `alt.*` remainder) | `archive.org/download/usenet-<hierarchy>/<group>.mbox.zip` | archive.org public item, Giganews donation | the post's own `Date:` header, `Message-ID` as evidence value | 11 groups, 2.47 GB, 2.47M messages | **8,819** (run A, 8 groups) and **7,190** (run B, 6 groups, 3 shared with A) | 50,000 to 150,000 over the next ~200 groups | **0.7389** (A), **0.6726** (B) | **35,000 to 105,000** |
| 2 | **archive.org dated computer and internet trade press** (Boardwatch, `collection:computermagazines`) | `archive.org/download/<id>/<id>_djvu.txt` | archive.org community texts, freely downloadable | the issue's publication year in item metadata | 34 + 40 items sampled, 38 with reachable full text | **216** (Boardwatch) and **116** (computermagazines) | 5,000 to 12,000 across `computermagazines` | **0.6716** and **0.6323** | **3,200 to 7,600** |

Neither number is a guess about a corpus I have not touched: both come from parsing bytes now on disk
and differencing them against `domain_year` in `data/ark.duckdb`.

**I did not reach a third qualifying source.** Section 4 ranks the unfinished candidates honestly.

---

## 2. Source 1: unexploited Usenet hierarchies

### Why it was worth re-opening

`usenet_announce` added 335,504 domains, the largest single addition this project has made, and it did
so from **54 groups of 19,233**. The existing selector in `scripts/fetch_usenet_groups.py` matches on
name tokens like `announce`, `business`, `commerce`, `webmaster`. That filter has now been drained:
all 697 archives under `data/raw/usenet/` appear in `data/raw/usenet/.processed`, and the whole `biz.*`
hierarchy is exhausted. What remains untouched is 18,536 groups and roughly 400 GB.

The open question was not "is there more Usenet" but a much sharper one: **does a group that announces
nothing still pay?** `uk.d-i-y` is a do-it-yourself discussion group. If ordinary English-language
discussion groups yield, the remaining corpus is effectively unbounded; if only announcement forums
yield, the route is finished. That is a measurable question and it had never been measured, because
the name filter never selected such a group in the first place.

### What I fetched

New script `scripts/probe_usenet_groups.py` takes an explicit group list rather than a name filter,
and writes to `data/raw/usenet_probe/` so a probe cannot be swept into the store by
`scripts/ingest_new_usenet.sh` before it has been judged.

```bash
printf '%s\n' uk.misc uk.local.london uk.finance uk.d-i-y uk.jobs.offered \
  aus.general aus.computers aus.net.access can.general can.infohighway can.forsale \
  rec.travel.usa-canada rec.arts.books rec.food.recipes \
  comp.infosystems.www.misc comp.internet.net-abuse.misc misc.consumers soc.culture.british \
  > /tmp/probe_groups.txt
uv run python scripts/probe_usenet_groups.py --from-file /tmp/probe_groups.txt --max-mb 200
```

11 of 18 arrived, 2.47 GB. Four were skipped by the 200 MB cap (`aus.general`, `can.general`,
`rec.arts.books`, `misc.consumers`, `soc.culture.british`), one is absent from the catalogue
(`comp.internet.net-abuse.misc`) and one failed with an archive.org HTTP 500 (`can.forsale`).

### The measurement

`scripts/measure_usenet_yield.py`, extended this session to report equivalent-English, since a pair
count no longer says what a tranche is worth.

**Run A, the eight archives present at the time of the run** (`uk.misc`, `uk.local.london`,
`uk.finance`, `uk.d-i-y`, `uk.jobs.offered`, `aus.computers`, `aus.net.access`, `can.infohighway`):

```bash
uv run python scripts/measure_usenet_yield.py data/raw/usenet_probe/*.mbox.zip
```

```
parse stats: messages 1,654,024  out_of_window 1,082,596  unreadable_date 11,984
             messages_with_domains 539,589  records 683,648  no_domains 19,831  no_message_id 24
extracted 34,185 pairs over 24,662 domains
net-new pairs  : 8,819
net-new domains: 5,685
  1996 150   1997 426   1998 672   1999 1,511   2000 2,763   2001 3,297
net-new pairs on domains some other source attests: 5,304
net-new pairs on names appearing only here        : 3,515
equivalent-English of net-new pairs: 6516.5099 (mean weight 0.7389)
equivalent-English of the corroborated half       : 3862.4374
typo upper bound: 1,473 of 4,000 sampled net-new names (36.8%) within one edit of a held name
```

**Run B, six archives, of which three (`aus.computers`, `aus.net.access`, `can.infohighway`) also
appear in run A** and three are new (`rec.travel.usa-canada`, `rec.food.recipes`,
`comp.infosystems.www.misc`):

```bash
uv run python scripts/measure_usenet_yield.py data/raw/usenet_probe/rec.*.zip \
    data/raw/usenet_probe/comp.*.zip data/raw/usenet_probe/aus.*.zip data/raw/usenet_probe/can.*.zip
```

```
parse stats: messages 811,270  out_of_window 493,896  unreadable_date 5,294
             messages_with_domains 300,019  records 412,074
extracted 42,845 pairs over 29,397 domains
net-new pairs  : 7,190
net-new domains: 4,180
  1996 152   1997 476   1998 598   1999 1,733   2000 2,060   2001 2,171
net-new pairs on domains some other source attests: 5,092
net-new pairs on names appearing only here        : 2,098
equivalent-English of net-new pairs: 4836.0103 (mean weight 0.6726)
equivalent-English of the corroborated half       : 3415.7295
```

**The two runs overlap in three archives, so they must not be added.** Run A alone is the clean
figure: 8,819 net-new pairs from eight groups, 1,102 per group, at a mean weight of 0.7389. Run B
establishes separately that global-interest hierarchies (`rec.*`, `comp.*`) behave like the regional
ones rather than worse.

### What this settles

The answer to the sharp question is **yes: ordinary discussion groups pay, and pay well.** None of
these eleven groups would have been selected by the existing name filter. `uk.d-i-y` and
`rec.food.recipes` announce nothing and still produce thousands of dated, English-weighted pairs,
because people quote URLs in ordinary conversation and every post carries its own date.

Two secondary findings, both favourable under the current metric:

- **The mean weight is high, 0.6726 to 0.7389**, against 0.6321 for a pure `.com` tranche. The `uk.*`
  groups pull it up: `.uk` is worth 0.9813. English regional hierarchies are the best-weighted large
  material this project has found.
- **The year distribution is late**, 1999 to 2001 carrying roughly three quarters of the pairs. That
  is the opposite shape to `usenet_announce`, whose value was in 1996-1998, so the two are
  complementary rather than competing. It is also the weaker half of the argument: the years that are
  hardest to evidence are the early ones, and this stratum does not help there much.

### Extrapolation, and my confidence in it

Measured: 1,102 net-new pairs per group over eight groups, mean weight 0.7389.

Naive multiplication over 18,536 unexploited groups gives twenty million, which is obviously wrong:
the pool saturates. What actually happens is that each additional group's marginal yield falls as the
store absorbs the common names, and the previous round saw exactly that (the second pair of groups
added 25,401 pairs and the marginal rate then declined).

My working estimate is therefore a band, not a point: **50,000 to 150,000 net-new pairs from the next
200 groups**, assuming marginal yield decays to between 25% and 70% of the measured rate. At a mean
weight of 0.70 that is **35,000 to 105,000 equivalent-English**.

**Confidence: high on the direction, medium on the magnitude.** What I measured is solid, eleven
groups is a real sample, and the result is unambiguous. What I did not measure is the decay curve,
and that is the whole width of the band. It would take about forty minutes to settle: take 40 more
groups, measure them in four batches of ten with the store differenced between batches, and read the
marginal rate directly. **What would change my mind:** a marginal rate that halves every batch, which
would cap the route near 30,000 pairs and make it a smaller source than it looks.

### Concrete next step

The parser already exists and needs no change. `src/ark/usenet.py` parses these archives correctly,
including the Giganews `YYYY/MM/DD` date rewrite, and `scripts/split_usenet.py` applies the
corroboration split.

1. Widen the selection in `scripts/fetch_usenet_groups.py`. The token filter is no longer the right
   instrument. Replace it with a hierarchy quota: take everything under `uk.*`, `aus.*` and `can.*`
   (761 groups, 21.3 GB) first, because they are English-weighted and small enough to finish, then
   proceed through `comp.*` and `rec.*` by ascending size.
2. Emit the same two evidence types as before and for the same reason: `usenet_announce`
   (`dated_directory`) where the domain already appears in `domain_year`, `usenet_mention`
   (`link_target`) otherwise. **Do not relax this.** The typo upper bound measured here is 36.8% and
   40.0%, in line with the 35.4% seen previously, so the free-text transcription risk is unchanged.
3. Raise the per-group size cap. Five of the eighteen groups I asked for were skipped for exceeding
   200 MB, and `soc.culture.british` at 496 MB is exactly the kind of large English group the old
   100 MB cap was designed to defer. The cap existed to buy breadth before evidence; there is now
   evidence.

### Two traps I hit, recorded so the next person does not

- **`uk.misc.mbox.zip` is 172.9 MB and parsed to one record.** Every other archive parsed in
  proportion to its size. That is a defect, not a property of the group, and it is worth ten minutes
  before the bulk run: either the zip is truncated, or it contains a member layout the parser walks
  past. Whatever it is, it is silent, and a silent zero on a large group is the failure mode most
  likely to make a bulk run look finished when it is not.
- **archive.org returned HTTP 500 for `can.forsale.mbox.zip`** and 200 for everything else in the same
  minute. Transient, but a bulk fetcher must treat it as retryable rather than as an empty group.

---

## 3. Source 2: archive.org dated computer and internet trade press

### The idea

archive.org holds scanned, OCR'd periodicals with hard publication dates in item metadata, and a 1997
issue of a trade magazine that prints `foo.com` is a dated artifact attesting `foo.com` for 1997. That
is structurally identical to the dated directory page `page_directory` already accepts. It appears
nowhere in the rejected table.

Three things had to be measured before believing any of it, and the third is the one that decided the
shape of the recommendation.

### Access route and licence

Free, no login, and **not** `web.archive.org`, so it does not compete with the running engines.

```bash
# what exists in window
curl -A "internet-digital-ark research (contact: ivaylo.staykov@taktile.com)" \
  "https://archive.org/advancedsearch.php?q=collection%3Acomputermagazines+AND+mediatype%3Atexts+AND+year%3A%5B1996+TO+2001%5D&fl%5B%5D=identifier&rows=0&output=json"
# the OCR text of one item
curl -L "https://archive.org/download/boardwatch-1997-09/boardwatch-1997-09_djvu.txt"
```

Corpus sizes in window, measured today:

| collection | in-window items |
|---|--:|
| `magazine_rack` | 34,279 |
| `internetarchivebooks` | 632,683 |
| `computermagazines` | 4,029 |
| `boardwatch` | 34 |

### The measurements

New script `scripts/probe_texts_corpus.py`. It samples a Solr query, downloads each item's
`_djvu.txt`, extracts registrable domains through the pinned public suffix list, and differences the
result against the store.

```bash
uv run python scripts/probe_texts_corpus.py --query 'boardwatch' --rows 40
uv run python scripts/probe_texts_corpus.py --query 'collection:computermagazines' --rows 40
uv run python scripts/probe_texts_corpus.py --query 'collection:magazine_rack AND language:(eng)' --rows 40
uv run python scripts/probe_texts_corpus.py --query 'subject:(internet) AND language:(eng)' --rows 60
```

| query | items | full text reachable | pairs extracted | net-new pairs | net-new per reachable item | mean EE weight |
|---|--:|--:|--:|--:|--:|--:|
| `boardwatch` | 34 | 27 | 1,973 | **216** | 8.0 | **0.6716** |
| `collection:computermagazines` | 40 | 11 | 713 | **116** | 10.5 | **0.6323** |
| `collection:magazine_rack` | 40 | 18 | 85 | 7 | 0.4 | 0.6432 |
| `subject:(internet)` books | 60 | 3 | 5 | 2 | 0.7 | 0.9054 |

Boardwatch year distribution of net-new pairs: 1996 54, 1997 60, 1998 102. `computermagazines`:
1997 11, 1998 62, 2001 43.

### What the numbers actually say

**The corpus is not the variable that matters; the subject matter is.** The same script, the same
extractor and the same store gave 10.5 net-new pairs per item on computer magazines and 0.4 on the
general magazine rack, a 26-fold difference. `magazine_rack` in window is Amiga user-group zines,
laboratory newsletters and hobbyist bulletins, which print almost no URLs. So the recommendation is
**not** "archive.org texts". It is specifically the computer and internet trade press.

**Lending restriction, not OCR, is the binding constraint on books.** Of 60 sampled in-window books
matching `subject:(internet)`, **57 had no downloadable full text at all.** The 632,683-item
`internetarchivebooks` collection is therefore mostly unusable however good the idea is, and the
Internet Yellow Pages editions I most wanted are in exactly that restricted set. This kills the
richest-sounding part of the original lead, and it is the single most useful negative finding of the
session.

**OCR noise is real but bounded and, importantly, one-directional.** The extractor is deliberately
narrow, matching only the TLDs the metric rewards, and every match is canonicalised through the PSL.
Of Boardwatch's 216 net-new pairs, 84 are on domains the store already attests in an annual file and
123 are names never seen anywhere, not even in the candidate pool. That ratio is the same problem
Usenet has and it takes the same answer, which is the corroboration split, not a claim of precision.

### Extrapolation and confidence

Base rates: 8.0 to 10.5 net-new pairs per reachable item; reachability 27.5% (11 of 40) on
`computermagazines`, 79% on the small Boardwatch set.

For `computermagazines`: 4,029 items x 27.5% reachable x 10.5 pairs = 11,600 pairs before any
saturation. Halving that for overlap decay as the trade press repeats the same advertisers issue
after issue gives **5,000 to 12,000 net-new pairs**, at a mean weight of about 0.63, so **3,200 to
7,600 equivalent-English**.

**Confidence: medium.** The per-item rate is measured on 38 items and I trust it. The two things I
did not measure are the ones that could move the total by a factor of two in either direction:
overlap decay across a corpus that reprints the same advertisers monthly, and whether the 27.5%
reachability on my sample is representative or an artefact of which items answered inside the
timeout. **What would change my mind:** a 200-item run showing unique-domain accumulation flattening
after the first few hundred items, which would put this below the 5,000 floor and make it a
corroboration source rather than a growth source.

### Concrete next step

There is no parser yet. It needs to:

1. Enumerate `collection:computermagazines` plus `collection:boardwatch` for `year:[1996 TO 2001]`
   through `advancedsearch.php`, and journal one JSON record per item as every other collector does.
2. Fetch `<identifier>_djvu.txt`, **following redirects**, since `archive.org/download` answers 302 to
   a data node and a naive fetch records a zero-byte success. Treat a body under about 2 KB as "no
   text", which is what a restricted item returns.
3. Emit `dated_directory` with the item identifier as the evidence value and
   `https://archive.org/details/<identifier>` as the evidence URL, so a reviewer can open the exact
   scanned issue behind any year. The item's `year` field is the year, with no inference.
4. Apply the same corroboration split as Usenet and Tucows: attested-elsewhere domains carry the issue
   date, names appearing only in OCR go to the candidate pool. Given OCR, this is not optional.
5. **Canonicalisation trap, and it is a real one.** OCR breaks hostnames across line ends and reads
   `rn` as `m` and `l` as `1`. A permissive regex over that output fabricates domains from sentence
   punctuation, so the pattern is anchored to a known TLD list rather than to a generic dot rule, and
   every match goes through `ark.canonical.to_registrable` rather than through hand-written splitting.

---

## 4. What I did not finish, ranked

Presented as unmeasured, because they are.

1. **Web rings.** The right shape and named in the phase-2 feedback. I wrote
   `scripts/probe_webrings.py` and ran it. `nav.webring.yahoo.com/*` returned **zero in-window
   captures**, which is a genuine finding: Yahoo! acquired WebRing in 1998 and that host postdates
   the useful period under its earlier name. Two attempts against `webring.org` and `www.webring.org`
   then failed at the transport layer while `archive.org` answered 200 in the same minute, and I
   stopped rather than retry, because two of this project's collection engines are on
   `web.archive.org` right now and the Internet Archive has refused this project three times. The
   probe script is committed and ready; it needs a quiet window, not more code.
2. **Portal and search-engine directory pages at breadth.** `page_directory` works and returned 5,220
   domains from a handful of pages. Yahoo!, Excite, Lycos, Infoseek and LookSmart category trees were
   captured repeatedly and each capture is a dated artifact. The parser pattern exists. This is
   probably the surest of the unfinished three, and it is blocked on the same thing: it is entirely a
   `web.archive.org` workload, and there is no room for it today.
3. **"Cool site of the day" and award lists.** Same shape as NCSA "What's New", which yielded 4,916
   domains. Also entirely an Internet Archive workload.

The honest summary of items 1 to 3 is that they are all the same bet, archived HTML on
`web.archive.org`, and I could not responsibly place it while the engines are running. That is a
scheduling constraint rather than a judgement about the sources, and it should be the first work of
the next session once the gap run finishes on 9 August.

---

## 5. Negative results

Each with the number that killed it. These belong in `docs/sources.md` so nobody repeats them.

| Source | Verdict and the number |
|---|---|
| archive.org **books** (`internetarchivebooks`, `subject:(internet)`) | **57 of 60 sampled in-window items have no downloadable full text.** Lending restriction, not OCR, is the constraint. The Internet Yellow Pages editions are in the restricted set. 2 net-new pairs from a 60-item sample |
| archive.org **`magazine_rack`** in general | 34,279 in-window items but **0.4 net-new pairs per reachable item**, against 10.5 for the computer trade press. In-window holdings are hobbyist zines and newsletters that print almost no URLs. Scope the source to computing titles or it is not worth the bandwidth |
| Boardwatch **ISP Directory** issues | The magazine issues have `_djvu.txt`; the separately catalogued directory volumes do not. `boardwatch-directory-of-internet-service-providers-july-august-1997_djvu.txt` returns a 146-byte stub. The single most ISP-dense artifact in the family is the one without text |
| `nav.webring.yahoo.com` | **Zero in-window captures** for the whole host prefix. Wrong hostname for the period |
| `biz.*` Usenet hierarchy | Already exhausted: zero unprocessed `.mbox.zip` archives remain in the catalogue |

---

## 6. What was downloaded, and where

All under `data/raw/`, which is git-ignored, so nothing here can be committed by accident.

| Path | Contents | Size |
|---|---|--:|
| `data/raw/usenet_probe/` | 11 `.mbox.zip` group archives, deliberately outside `data/raw/usenet/` so `ingest_new_usenet.sh` cannot sweep them into the store before they are judged | 2.47 GB |
| `data/raw/texts/cache/` | gzipped `_djvu.txt` for every item whose full text was reachable, so the measurement replays offline with no further requests | small |
| `data/raw/texts/*_items.json` | per-item results for each probe: identifier, year, whether text was reachable, domains found | small |
| `data/logs/probe_*.log`, `data/logs/measure_usenet_probe*.log` | the raw output of every measurement quoted above | small |

Ingestion of source 1 can start immediately: the archives are on disk and `src/ark/usenet.py` parses
them unchanged. Move them into `data/raw/usenet/` and run `scripts/ingest_new_usenet.sh`, having first
resolved the `uk.misc` anomaly in section 2.

## 7. Conduct

Everything in this session went to `archive.org/download` and `archive.org/advancedsearch.php`,
which are different services from the `web.archive.org` CDX and replay endpoints the two collection
engines are using. The only exception was the web-ring probe, which is capped at a handful of
captures with a delay between them and which I abandoned after two transport failures rather than
retrying into a service that may have been signalling. Every request carried an honest User-Agent
naming the project and a contact address, and `scripts/probe_texts_corpus.py` honours `Retry-After`
and backs off on 429, 503 and 504. The store was opened `read_only=True` throughout.
