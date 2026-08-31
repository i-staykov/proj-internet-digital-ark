# Output-unit check: registered domains or hostnames

Ivaylo Staykov, 31 August 2026. Companion to the email of the same date.

## The question

Rule 8 of the task brief says:

> "By default, the final domain files should use registered domains as the output unit
> rather than full hostnames or user paths on hosting platforms. Unless otherwise
> explicitly required, output should therefore favor registered domains rather than
> `www.example.com`, `foo.example.com`, or specific user paths on platforms such as
> GeoCities or Tripod."

I have implemented that as a hard rule. The benchmark database does not follow it. This
archive measures the size of that difference on your own files, so the question can be
settled as arithmetic.

**The question is only this: which unit do you want from me?** I am not asking for a
change to the metric, the weights or the scoring.

## The standard, as I have implemented it

A record conforms if it is a **registered domain**: exactly one label plus a public
suffix. `example.com`, `example.co.uk` and `example.com.br` conform. `www.example.com`,
`foo.example.com` and `member.tripod.com` do not, because each carries a label to the
left of the registered domain.

`registrable_unit.py` in this archive is that rule, standalone, stdlib only. In my
pipeline the same function is the single funnel every domain from every source passes
through before it can reach the database, so a hostname is reduced to its registered
domain and, that name being already held, the record is then dropped.

Two implementation notes, because both change the answer:

- Only the **ICANN section** of the Public Suffix List is used. The PRIVATE section is
  ignored deliberately: a name a hosting company delegates to its customer is not a
  registered domain, and that is the population in question.
- Nine retired ccTLDs of the 1996-2001 web are added by hand (`yu`, `an`, `bu`, `cs`,
  `dd`, `gb`, `tp`, `um`, `zr` and their second levels), because the current list no
  longer carries them and without them a name such as `ac.yu` would be reported as
  unparseable rather than judged.

The standalone program was checked against the implementation actually used in my
pipeline over **8,921,251 records** drawn from `merged260830`, `merged260727` and my own
output: **zero disagreements**.

## Results

Equivalent-English is computed with the weights in `q2_tld_top_langs.json`, copied
unchanged from `equivalent_english_domain_calculator` in the 31 August task package.

| Dataset | Records | Not a registered domain | Share | Equivalent-English |
|---|---|---|---|---|
| Your original benchmark, `merged260727` | 9,654,487 | 1,452,961 | 15.05% | 826,259.68 |
| Increment `merged260810` to `merged260815` | 4,068,061 | 9,997 | 0.25% | 895.75 |
| Increment `merged260827-2` to `merged260830` | 646,538 | 426,279 | 65.93% | 204,438.53 |
| **My submission of 2026-08-09** | 946,266 | **0** | 0.00% | 0.00 |
| **My submission of 2026-08-17** | 2,838,715 | **0** | 0.00% | 0.00 |
| **My submission of 2026-08-26** | 1,929,655 | **0** | 0.00% | 0.00 |
| **My next additions, not yet submitted** | 285,340 | **0** | 0.00% | 0.00 |
| Current benchmark, `merged260830` | 27,880,397 | 2,121,500 | 7.61% | 1,129,420.30 |

Three readings, and each is in the per-year detail in `results/summary.csv`.

**1. I have applied the rule without exception.** Across four sets, 24 annual files and
**5,999,976 records** submitted or ready to submit, the count of records that are not
registered domains is **zero, in every year**. As a check that these are the files you
received, the 2026-08-17 total of 2,838,715 is the figure quoted back to me in your
phase-5 feedback.

**2. The benchmark has never followed the rule, starting with your own corpus.** The
first package I received, `merged260727`, is 15.05% non-conforming, reaching 24.86% at
1999. That predates any submission of mine, so this is not a contributor artifact.
Today `merged260830` holds 2,121,500 such records worth 1,129,420.30 equivalent-English,
which is 7.77% of its 14,531,454.0269 total.

**3. Contributions other than mine are still adding them, and recently the increment is
mostly made of them.** The 646,538 records the benchmark gained between `merged260827-2`
and `merged260830` are **65.93% non-conforming**: 98.47% at 1999, 97.96% at 2000 and
53.16% at 2001. My last accepted submission had already been merged before
`merged260827-2`, and I have submitted nothing since, so none of that increment is mine.
`results/parents_3_*` lists what those records sit under. The largest are
`bol.com.br` 21,500, `dir.bg` 11,078, `cjb.net` 8,229, `homestead.com` 5,700 and
`tripod.com` 4,999, the last being a platform rule 8 names by name.

The earlier `merged260810` to `merged260815` increment, whose merge statistics you
shipped under the names `umn_drum_0814` and `new0714`, is also non-conforming, at the
much lower rate of 0.25%.

## What is in this archive

```
registrable_unit.py        the standard, standalone, Python 3.9+, no dependencies
public_suffix_list.dat     the list snapshot my pipeline is pinned to
q2_tld_top_langs.json      your weights, copied unchanged from the 31 August package
results/summary.csv        one row per annual file, the table above in per-year detail
results/console_output.txt exactly what the program printed for that run
results/samples_*.txt      40 random examples per file, with the registered domain of each
results/parents_*.txt      the 25 registered domains those records most often sit under
REPRODUCE.md               the commands, against paths in your own packages
```

The archive deliberately contains **no domain lists**. Every input is a file you already
hold, so the whole table can be regenerated on your machine. The examples are drawn by
reservoir sampling with a fixed seed rather than from the head of each file, because
these lists are sorted and their first lines are percent-encoded oddities that
misrepresent the population.

## What I will do with the answer

If hostnames are acceptable, I would deliver them in a separate file per year, for
example `2001_hostnames.txt`, so that the annual master files stay exactly as rule 8
specifies and you can merge or discard the second file at your discretion. If they are
not, I will keep reducing every name to its registered domain as I do now, and I will
not raise it again.
