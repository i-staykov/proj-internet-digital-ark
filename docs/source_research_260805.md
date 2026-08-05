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

### Small groups are eight times more efficient per byte, which was not expected

A third tranche tested breadth rather than depth: the **smallest** unworked archives in `uk.*`,
`aus.*` and `can.*`, taken in ascending size order.

```bash
uv run python scripts/probe_usenet_groups.py --from-file /tmp/probe3a.txt --out data/raw/usenet_probe3
uv run python scripts/measure_usenet_yield.py data/raw/usenet_probe3/*.mbox.zip
```

```
parse stats: messages 298,129  out_of_window 137,142  unreadable_date 2,742
             messages_with_domains 152,454  records 191,681
extracted 24,354 pairs over 17,750 domains
net-new pairs  : 6,454
net-new domains: 4,036
  1996 61   1997 449   1998 763   1999 1,352   2000 1,934   2001 1,895
net-new pairs on domains some other source attests: 3,688
net-new pairs on names appearing only here        : 2,766
equivalent-English of net-new pairs: 4647.2579 (mean weight 0.7201)
typo upper bound: 1,327 of 4,000 (33.2%) within one edit of a held name
```

**116 archives, 174 MB, 6,454 net-new pairs at mean weight 0.7201.** Against the earlier tranche:

| tranche | archives | bytes | net-new pairs | pairs per MB | out of window |
|---|--:|--:|--:|--:|--:|
| large groups (probes 1 and 2) | 28 | 4.5 GB | 20,159 | 4.5 | **76%** |
| smallest groups (probe 3) | 116 | 174 MB | 6,454 | **37.1** | **46%** |

**Small groups are roughly eight times more efficient per byte**, and the mechanism is in the last
column: a small archive belongs to a group that died early, and a group that died early is one whose
traffic falls inside the window. The large archives are large precisely because they ran on into the
2000s, which is where three quarters of their bytes go.

This inverts the assumption behind both earlier selection rules. Round two's 100 MB cap was framed as
deferring the big groups until there was evidence, treating small ones as a compromise. They are not
a compromise, they are the better material. **Run the download queue ascending by size and keep
going.**

The two tranches were measured independently against the store, so the totals must not simply be
added: some pairs are common to both. The union was not computed and is somewhat under 26,613.

### The in-window screen, and why the obvious version of it fails

`scripts/screen_usenet_archives.py` implements the coverage gate, and building it exposed a defect in
the idea as I had stated it.

The obvious screen reads the **head** of each mbox and drops the group if the dates start after 2001.
It does not work. Measured: `uk.finance`, which yields thousands of in-window pairs, reads as
**2011-2013** over its first 2,000 messages. **The Giganews exports are not in chronological order**,
so a contiguous sample is a sample of one arbitrary period rather than of the group.

Striding across the whole archive fixes it, and the corrected screen separates the two populations
cleanly on groups whose yield is already known independently:

```
in-window %  sampled         span  group          measured yield
       0.0%    6,526    2002-2013  uk.transport   0 net-new pairs
      41.7%    5,790    1995-2013  uk.finance     thousands
       0.0%    6,202    2004-2013  uk.misc        1 record
```

Being honest about what this buys: striding still requires the archive to be downloaded and
decompressed, so it prunes the **ingest** queue rather than the download queue. Given the size
finding above that matters less than it first looked, because ascending-size ordering is a good
enough download heuristic on its own.

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

### Extrapolation, now measured rather than assumed

The first version of this report gave a band of 50,000 to 150,000 pairs and admitted that the entire
factor-of-three width was one unmeasured quantity: **the decay**. Each group added overlaps the ones
before it, so multiplying a per-group rate by the number of remaining groups is wrong by whatever the
saturation curve does. I then measured it, which is the most useful thing done in this session.

`scripts/measure_usenet_decay.py` parses archives in a fixed order into one accumulating set and, at
each batch, reports the pairs that are net-new against **both the store and every earlier batch**. 17
further groups were downloaded for this (`uk.transport`, `uk.legal`, `aus.invest`, `can.taxes` and
others), giving 28 in total.

```bash
uv run python scripts/probe_usenet_groups.py --from-file /tmp/probe2.txt --out data/raw/usenet_probe2
uv run python scripts/measure_usenet_decay.py --batch 4 \
    data/raw/usenet_probe/*.mbox.zip data/raw/usenet_probe2/*.mbox.zip
```

```
store holds 8,812,701 assigned pairs

 groups   cumulative new   marginal   marginal EE  per group
      4            3,956      3,956        2839.7        989
      8            9,498      5,542        3727.9       1386
     12           12,552      3,054        2259.4        764
     16           13,807      1,255         982.3        314
     20           17,971      4,164        2848.6       1041
     24           20,159      2,188        1608.3        547
     28           20,159          0           0.0          0

28 groups, 20,159 net-new pairs
equivalent-English 14266.2922 (mean weight 0.7077)
parse stats: messages 5,283,482  out_of_window 4,023,027  unreadable_date 37,626
             messages_with_domains 1,176,476  records 1,532,312
```

**28 groups, 20,159 net-new pairs, 14,266 equivalent-English at a mean weight of 0.7077.** That
clears the 5,000-pair floor by four times on material physically on disk, before any extrapolation.

**The curve is close to linear, which was not the expected answer.** Fitting the cumulative column to
`N(g) = a * g^b` on the points at 4 and 24 groups gives **b = 0.909**. An exponent that near 1 means
saturation has barely begun over 28 groups: the store holds 8.8M assigned pairs and these groups
still keep finding names it does not have. Projecting that fit:

| groups worked | projected net-new pairs | projected EE at 0.7077 |
|--:|--:|--:|
| 100 | 72,000 | 51,000 |
| 200 | **138,000** | **98,000** |
| 761 (all of `uk.*`, `aus.*`, `can.*`) | 466,000 | 330,000 |

My earlier band was not wrong, but it was wrong-shaped: the truth sits at its **upper** end, and the
reason is that this material does not overlap the archive-derived baseline the way another crawl
would.

**The marginal column is lumpy, and the lumpiness is the finding rather than noise.** It runs 989,
1386, 764, 314, 1041, 547, 0 pairs per group. That is not a decay curve with scatter on it, it is a
bimodal population. A group whose Giganews archive covers 1996-2001 yields around a thousand pairs,
and a group whose archive begins in 2003 yields nothing at all. The final batch of four
(`uk.rec.sheds`, `uk.tech.digital-tv`, `uk.telecom.mobile`, `uk.transport`) contributed **exactly
zero**, which is the same phenomenon as `uk.misc` below. Across all 28 archives, **4,023,027 of
5,283,482 messages are out of window**, so 76% of the bytes fetched buy years nobody is asking about.

**This changes the recommended selection rule, and it is the actionable conclusion.** Do not select
groups by name or by size. **Select on whether the archive covers the window**, which costs almost
nothing to test: read the first few thousand messages, look at the `Date` headers, abandon the group
if they start after 2001. That turns a 76%-waste download queue into a targeted one.

**Confidence: high, and materially higher than an hour ago.** 20,159 pairs is measured on bytes on
disk, not extrapolated. The projection to 200 groups rests on a seven-point fit, which is thin, but
the exponent would have to fall from 0.909 to below 0.6 before the 200-group figure dropped under
50,000. **What would change my mind:** the store is being written to continuously by two collection
engines, so the same group measured next week will find fewer net-new pairs than it does today. That
effect is real, is not in this fit, and argues for working this source sooner rather than later.

### Concrete next step

The parser already exists and needs no change. `src/ark/usenet.py` parses these archives correctly,
including the Giganews `YYYY/MM/DD` date rewrite, and `scripts/split_usenet.py` applies the
corroboration split.

1. Widen the selection in `scripts/fetch_usenet_groups.py`. The token filter is no longer the right
   instrument, and neither is size. **Gate on in-window coverage**: read the first few thousand
   messages of an archive and abandon the group if the `Date` headers start after 2001. 76% of the
   messages fetched in this probe were out of window, and that waste is concentrated in whole groups
   rather than spread evenly, so the test is nearly free and removes most of it.
2. Within the groups that pass, take `uk.*`, `aus.*` and `can.*` first (761 groups, 21.3 GB): they
   are English-weighted and small enough to finish, and `.uk` is worth 0.9813 against 0.6321 for
   `.com`, which is why the measured mean weight here is 0.7077.
3. Emit the same two evidence types as before and for the same reason: `usenet_announce`
   (`dated_directory`) where the domain already appears in `domain_year`, `usenet_mention`
   (`link_target`) otherwise. **Do not relax this.** The typo upper bound measured here is 36.8% and
   40.0%, in line with the 35.4% seen previously, so the transcription risk is unchanged.
4. Raise the per-group size cap. Five of the eighteen groups in the first batch and two of the twenty
   in the second were skipped for exceeding 200 MB, and `soc.culture.british` at 496 MB is exactly
   the kind of large English group the old 100 MB cap was designed to defer. The cap existed to buy
   breadth before there was evidence; there is evidence now.

### Two traps I hit, recorded so the next person does not

- **`uk.misc` parses to one record from 172.9 MB, and it is not a defect.** I flagged this as a
  probable parser bug and then measured it: 248,074 messages, of which **243,662 are out of window
  and 4,411 carry an unreadable date**, leaving exactly one in-window message with a domain in it.
  The Giganews archive for that group is almost entirely 2003 onward. This is the `alt.www.webmaster`
  finding again in a new hierarchy, and it is the most important operational caveat on this source:
  **archive size does not predict in-window content, and a large group can be worth nothing.** The
  parser's separate counters for `out_of_window` and `unreadable_date` are what made the difference
  between a ten-minute diagnosis and an afternoon, and they should stay.
- **archive.org returned HTTP 500 for `can.forsale.mbox.zip`** on two separate attempts an hour
  apart, while every other request in the same minutes returned 200. Item-specific rather than
  transient, but a bulk fetcher should still treat it as retryable rather than as an empty group.

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

1. **Web rings. Now settled, and the answer is no as a bulk source.** This took three passes and each
   one was wrong in a different way, which is worth recording in full because the failure modes are
   general.

   The first pass queried `www.webring.org/*` with `matchType=prefix`, got **zero captures**, and
   nearly wrote the family off. That was wrong: WebRing served member lists as query strings off the
   site root, so there is no path prefix to match. **A wrong CDX match type is indistinguishable from
   an absent source**, and that is the transferable lesson. Under `matchType=domain` there are
   in-window captures for `webring.org` from **19961019** and `webring.com` from **19981212**.

   The second pass fetched ten `;list` captures and got one domain each, which looked like archived
   CGI stubs. Also wrong. Sorting the CDX by `length` and taking the largest gives real pages: 
   `http://www.webring.com/cgi-bin/webring?ring=railring&list` at 20000422003921 is **14,154 bytes**
   of genuine ring content, with member titles and full descriptions.

   The third pass is the one that settles it. That page lists **20 member sites, and contains 2
   member URLs.** Every member is linked through a redirector,
   `go.webring.org/go?ring=railring;id=878;go`, and the visible text carries the site's *title and
   description* but no address at all. There are **zero bare URLs in the rendered text**.

   So the member domains are not in the artifact. Recovering them means resolving one Wayback
   redirect per member, which is one Internet Archive request per domain, against a source whose
   pages hold about 20 members each. **Verdict: reject as a bulk source.** It is not worthless, since
   the redirect route would work and the population is exactly the English hobbyist long tail a DNS
   survey misses, but it is an IA-request-per-domain source competing for the same budget as the gap
   engine, which already runs at a 96% hit rate. That comparison is what decides it, not the source
   in isolation.
2. **Portal and search-engine directory pages at breadth.** `page_directory` works and returned 5,220
   domains from a handful of pages. Yahoo!, Excite, Lycos, Infoseek and LookSmart category trees were
   captured repeatedly and each capture is a dated artifact. The parser pattern exists. This is now
   the **most promising unfinished item**, and unlike web rings those pages linked their entries
   directly rather than through a redirector. It is blocked only on `web.archive.org` capacity.
3. **"Cool site of the day" and award lists.** Same shape as NCSA "What's New", which yielded 4,916
   domains. Also entirely an Internet Archive workload.

Items 2 and 3 are the same bet, archived HTML on `web.archive.org`, and I could not responsibly place
it while both engines are running. That is a scheduling constraint rather than a judgement, and it
should be the first work of the next session once the gap run finishes on 9 August.

---

## 5. Negative results

Each with the number that killed it. These belong in `docs/sources.md` so nobody repeats them.

| Source | Verdict and the number |
|---|---|
| archive.org **books**, three collections tested (2026-08-05) | The idea is sound and the payload is not there. `subject:(internet)`: **57 of 60 sampled in-window items publish no downloadable `_djvu.txt`**, 2 net-new pairs. `collection:folkscanomy_computer`, chosen specifically because it is *not* lending-restricted: **36 of 40 unreachable anyway, 2 net-new pairs from 40 items.** So the constraint is not only lending restriction, it is that in-window book scans mostly carry no OCR text layer at all. The Internet Yellow Pages editions are unreachable either way. **The book half of this lead is closed** |
| archive.org **`magazine_rack`** at large (2026-08-05) | 34,279 in-window items but **0.4 net-new pairs per reachable item**, against 10.5 for the computing trade press measured the same way on the same day. In-window holdings are Amiga user-group zines and laboratory newsletters that print almost no URLs. The periodical route is only worth taking scoped to computing and internet titles |
| Boardwatch **ISP Directory** volumes (2026-08-05) | The monthly magazine issues carry `_djvu.txt`; the separately catalogued directory volumes do not. `boardwatch-directory-of-internet-service-providers-july-august-1997_djvu.txt` returns a 146-byte stub. The most ISP-dense artifact of the family is the one without machine-readable text |
| `nav.webring.yahoo.com` (2026-08-05) | **Zero in-window captures** for the entire host prefix. Wrong hostname for the period: query `webring.org` and `webring.com`, which both have in-window captures |
| DMOZ / ODP mirrors on Zenodo (2026-08-05) | 12 hits, all 2018-2020 research derivatives of late DMOZ dumps (Webis Abstractive Snippet Corpus and similar). Out of window, and description text rather than dated listings. The ODP rejection stands |
| Bibliotheca Alexandrina Internet Archive mirror (2026-08-05) | `web.archive.bibalex.org` and `web.archive.org.bibalex.org` both fail to resolve. Only the institutional landing page answers. This was the most promising non-IA route to early captures and it no longer exists |
| `data.webarchive.org.uk` (2026-08-05) | Does not resolve. Third distinct host tried for the UKWA bulk CDX, after the 159-byte stub and the 403 DOI. Still no route in |
| `biz.*` Usenet hierarchy (2026-08-05) | Exhausted: no unprocessed `.mbox.zip` archives remain in the 19,233-group catalogue |
| Late-starting Usenet groups (2026-08-05) | Not a source rejection but a selection rule, and it costs more than any of the above. **4,023,027 of 5,283,482 messages across 28 probed archives are out of window**, and the waste is concentrated in whole groups: four of the 28 (`uk.rec.sheds`, `uk.tech.digital-tv`, `uk.telecom.mobile`, `uk.transport`) contributed **exactly zero** net-new pairs between them, and `uk.misc` gave one record from 172.9 MB. Select on in-window date coverage, not on name or size |

---

## 6. What was downloaded, and where

All under `data/raw/`, which is git-ignored, so nothing here can be committed by accident.

| Path | Contents | Size |
|---|---|--:|
| `data/raw/usenet_probe/`, `usenet_probe2/`, `usenet_probe3/` | **28 large plus 277 small** `.mbox.zip` group archives, deliberately outside `data/raw/usenet/` so `ingest_new_usenet.sh` cannot sweep them into the store before they are judged. These hold the measured 20,159 and 6,454 net-new pairs, and the probe-3 download was still running when this was written | 5.1 GB |
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
