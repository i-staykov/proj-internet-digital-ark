# Output-unit check

Ivaylo Staykov, 31 August 2026. Companion to the email of the same date.

## The rule being measured

Rule 8 of the brief:

> "By default, the final domain files should use registered domains as the output unit
> rather than full hostnames or user paths on hosting platforms."

A record conforms here if it is one label plus a public suffix, so `example.co.uk`
conforms and `member.tripod.com` does not.

## Results

Equivalent-English uses `q2_tld_top_langs.json`, copied unchanged from the calculator in
the 31 August package. Per-year detail is in `results/summary.csv`.

| Dataset | Records | Not a registered domain | Share | Equivalent-English |
|---|---|---|---|---|
| Your first package, `merged260727` | 9,654,487 | 1,452,961 | 15.05% | 826,259.68 |
| Increment `merged260810` to `merged260815` | 4,068,061 | 9,997 | 0.25% | 895.75 |
| Increment `merged260827-2` to `merged260830` | 646,538 | 426,279 | 65.93% | 204,438.53 |
| My submission of 2026-08-09 | 946,266 | 0 | 0.00% | 0.00 |
| My submission of 2026-08-17 | 2,838,715 | 0 | 0.00% | 0.00 |
| My submission of 2026-08-26 | 1,929,655 | 0 | 0.00% | 0.00 |
| My next additions, not yet sent | 285,340 | 0 | 0.00% | 0.00 |
| Current benchmark, `merged260830` | 27,880,397 | 2,121,500 | 7.61% | 1,129,420.30 |

Across 24 annual files and 5,999,976 records submitted or ready, the count is zero in
every year. As a check that these are the files you received, the 2026-08-17 total of
2,838,715 matches the figure in your phase-5 feedback.

## Method

`registrable_unit.py` is the rule, standalone, Python 3.9 or later, no dependencies,
nothing fetched. Two choices affect the result:

- Only the **ICANN section** of the Public Suffix List is used. The PRIVATE section is
  ignored on purpose, since a name a hosting company delegates to a customer is the
  population in question.
- Nine retired ccTLDs of the window are added by hand (`yu`, `an`, `bu`, `cs`, `dd`,
  `gb`, `tp`, `um`, `zr` and their second levels), which the current list no longer
  carries.

The script was checked against the implementation my pipeline actually uses, over
8,921,251 records from `merged260830`, `merged260727` and my own output: zero
disagreements.

## Contents

```
registrable_unit.py         the rule
public_suffix_list.dat      the snapshot my pipeline is pinned to
q2_tld_top_langs.json       your weights, unchanged
results/summary.csv         one row per annual file
results/console_output.txt  what the run printed
results/samples_*.txt       40 random examples per file, each with its registered domain
results/parents_*.txt       the 25 registered domains those records most often sit under
REPRODUCE.md                the commands
```

No domain lists are included: every input is a file you already hold. Examples are drawn
by reservoir sampling with a fixed seed, not from the head of each file, since these
lists are sorted and their first lines are unrepresentative.
