# The equivalent-English domain metric, explained and runnable

**D4 of the submission standard.**

## 1. The runnable code

Two implementations ship, and only one of them decides anything.

| | what it is | what it decides |
|---|---|---|
| `equivalent_english_domain_calculator/equivalent_english_domains.py` | **the reviewer's own program**, vendored unmodified with its model file | **every figure quoted to him** |
| `source/src/ark/english_share.py` | this project's implementation, reading `src/ark/data/tld_english_share.json` | ranking during collection only |

**One command runs from the root of the unpacked archive and needs nothing but python3:**

    python equivalent_english_domain_calculator/equivalent_english_domains.py additions/2001.txt

The other two run from inside `source/`, which is where the project and its lockfile are, so extract
it first. The merge needs only the shipped files; `--verify` additionally needs the evidence store,
which this archive does **not** ship, so rebuild it from the provenance Parquet:

    tar -xzf source/source.tar.gz -C source/ && cd source && uv sync
    uv run python scripts/round/merge_against_baseline.py     # merge, overlap, increment, reconciliation
    uv run ark rebuild ../provenance                    # the store, from the Parquet
    uv run python scripts/round/round_figures.py --verify     # re-scores with HIS program; non-zero exit on disagreement

`--verify` refuses a round on his validator's terms rather than ours.

**Why two implementations and not one.** Collection has to rank two million candidate domains by
expected value, which means calling the weight table in a tight loop rather than shelling out per
file. So the table is vendored for ranking and his program is authoritative for reporting. **They are
verified identical rather than assumed identical**: both derive 1,306 English weights from the same
model, and `tests/test_baseline.py` fails on any TLD where they disagree.

## 2. The fixed TLD weights and the model version

**Model version: `CC-MAIN-2024-10`**, the Common Crawl crawl of that name, distributed by the
reviewer as `q2_tld_top_langs.json` inside his calculator directory. It carries 14,778
(TLD, language, share) rows over **1,330 distinct TLDs**, of which **1,306 have an English row**.

The weight of a TLD is the `perc_of_tld` of its `eng` row, divided by 100. A TLD with no `eng` row
has no weight and contributes zero. Worked examples, read straight from the model:

| TLD | weight | | TLD | weight |
|---|--:|---|---|--:|
| `.au` | 0.9904 | | `.org` | 0.7101 |
| `.gov` | 0.9825 | | `.com` | 0.6321 |
| `.uk` | 0.9813 | | `.net` | 0.4530 |
| `.edu` | 0.9717 | | `.info` | 0.3648 |
| `.us` | 0.9261 | | `.nl` | 0.1629 |
| `.ca` | 0.8365 | | `.de` | 0.1324 |
| | | | `.br` | 0.0934 |

**The table is frozen.** His brief requires the same weights for the baseline and every submission
compared against it, and it must not change unless he reissues it for all comparisons. Practically
this means a `.uk` record is worth 7.4 times a `.de` one, so a large non-English source is a small
source.

## 3. The formula

For one annual file:

    equivalent-English total = sum over TLDs t of ( N_t * w_t )

where `N_t` is the number of unique valid records under TLD `t` and `w_t` is that TLD's English
share. The unit is the **domain-year record**: the same domain contributes once in each annual file
for which year evidence exists, and duplicates within a year are removed before the sum. The totals
add within each part, 1996 to 2001 and 2002 to 2013, and each part takes its own growth rate:

    increment    = post-merge total - baseline total
    growth rate  = increment / baseline total * 100

**The denominator is the PRE-increment baseline**, his convention (`round_figures.py`).

## 4. Normalisation, invalid records and unmatched records

His program does three things to a file before it counts anything, in this order:

1. **Strip and lowercase every line**, then discard empty lines.
2. **Deduplicate**, as a set. So a repeated line inside one annual file is one record.
3. **Test each value against a hostname pattern.** Anything failing it is an `invalid_record`.

The pattern is his:

    (?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\Z

Read left to right: total length 1 to 253; one or more labels each starting and ending
alphanumeric with hyphens allowed inside, each followed by a dot; and a final label of **2 to 63
letters only**.

**Two treatments, both contributing zero, and they are not the same thing.**

- **Invalid records** fail that pattern. Embedded ports, underscore labels, leading dots, bare IP
  addresses. Reported as `invalid_records`.
- **Model-unmatched valid records** are well-formed hostnames whose TLD has no English row in the
  model. Reported as `model_unmatched_valid_records`.

The audit JSON of section 5 carries each year's `baseline_invalid_records` and
`merged_model_unmatched_valid_records`.

**The clause that matters is `[a-z]{2,63}`, letters only.** An internationalised TLD in punycode,
`xn--fiqs8s`, contains digits and hyphens, so it fails his pattern and scores **zero for him**; no
`xn--` TLD was delegated before 2010. The store refuses one at the parser, and the invariant
`no_idn_tld_in_window` (`src/ark/checks.py`) fails the build if one appears.

## 5. The four totals for this round

Produced by `merge_against_baseline.py`, which scores each baseline file and each merged file with
his program and reports the difference. Regenerate with:

    cd source && uv run python scripts/round/merge_against_baseline.py --stamp <YYYYMMDD>

The current figures are in `audit/merge_stats_ark_*.csv` and `audit/merge_audit_ark_*.json` beside
this document, in the column names of his own audit so the two can be diffed directly. The audit
JSON also carries every **reconciliation check**: the per-year identities
`baseline_unique + accepted_new == merged_unique` and
`already_in_baseline + accepted_new == submitted_unique`, that the per-year equivalent-English
increments sum to the headline increment, that `baseline total + increment == post-merge total`, and
that the measured baseline reproduces the record count and equivalent-English total this project has
recorded for the release it is working against.

The last pair compares a freshly measured baseline against `data/baseline.json`, so it fails if the
round was measured against a release he has replaced.
