# Rounds

Ledger of every submission: what was sent, what the reviewer credited, and the ranking score
S_i = 10 x p_i / t_i under his rule of 2026-08-20, where p_i is the percentage he awarded and t_i the
elapsed time from the release of the benchmark package the round was measured against to the receipt
of the submission. Timestamps are in HIS clock (US Pacific), read from his mail headers and from the
quote lines his replies carry; the two known scores fit exactly one reading of t_i, whole days rounded
up from the release stamp (round 6: 5.19 days, t = 6; round 7: 11.77 days, t = 12). Calendar days
give round 6 t = 5 and S = 8.26, which he did not quote. Seeded by hand on 2026-09-02 from the mail
archive; E6.2 appends future rows from the feedback mail. Not shipped.

| round | sent records | sent EE | sent % | credited records | credited EE | awarded p_i | against | released | received | days | t_i | S_i computed | S_i quoted | note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1,429,524 | n/a | n/a | 1,429,524 | n/a | 17.38 | merged260715-2 | 2026-07-21 12:24 | 2026-07-26 18:30 | 5.25 | 6 | 28.966667 | not quoted | record percentage; the EE metric came later |
| 2 | 17,418 pairs | n/a | n/a | n/a | n/a | n/a | merged260727 | n/a | n/a | n/a | n/a | n/a | n/a | never scored; rolled into round 3 |
| 3 | 152,773 | 105,676.0387 | 1.879358 | 151,949 | 91,814.6880 | 1.659986 | merged260730 | 2026-07-31 17:25 | 2026-08-01 19:42 | 1.10 | 2 | 8.299930 | not quoted |  |
| 4 | 946,266 | 603,401.7811 | 10.730988 | 946,266 | 603,401.7811 | 10.730988 | merged260802-2 | 2026-08-03 05:36 | 2026-08-09 07:58 | 6.10 | 7 | 15.329983 | not quoted |  |
| 5 | 2,838,732 | 1,697,225.1735 | 20.333700 | 2,608,322 | 1,566,229.7613 | 14.901054 | merged260817 | 2026-08-15 10:27 | 2026-08-17 03:03 | 1.69 | 2 | 74.505270 | not quoted |  |
| 6 | 1,929,655 | 713,481.4198 | 5.3395 | 1,684,903 | 562,099.5294 | 4.130718 | merged260826 | 2026-08-21 11:19 | 2026-08-26 15:51 | 5.19 | 6 | 6.884530 | 6.88 | matches his figure |
| 7 | 2,541,429 | 1,458,263.2088 | 7.5794 | 2,538,900 | 1,456,458.1029 | 7.562846 | merged260902-2 | 2026-08-21 11:19 | 2026-09-02 05:50 | 11.77 | 12 | 6.302372 | 6.302372 | matches his figure |

Sum of S_i as he quotes them (rounds 6 and 7, 6.88 + 6.302372): **13.184372**; the same two computed
to six places sum to 13.186902. Sum over every round under the same rule, round 1 included on its
record percentage: 140.288752. Rounds 1 to 5 predate the rule and he has
quoted no score for them; their S_i above is what the rule would give and is not a claim on him.

Figures come from the sent mails and his feedback, quoted as numbers only. Round 5 sent figures are
the sent mail's; the comment in `src/ark/baseline.py` says 2,838,715 records and 1,697,224.86 EE, 17
records and 0.31 EE apart, and E3.6 retires that comment. Round 1 sent 1,429,524 records and he awarded
17.38% on records, so its p_i is not commensurable with the others; it is summed on Ivo's instruction of
2026-09-02 and flagged wherever the sum is printed. Whether he confirms the whole-day reading of t_i is
open in `docs/questions.md`.

A round can be accepted in full and still be credited less than it was sent for: he merges against
whatever baseline is current when he reaches the submission, and in round 5 230,393 of ours had already
arrived in his interim `merged260817` through another contributor. `merged260727` to `merged260730` is
+609,145 records from an external contributor (`feedback-external-phase-2/`), not this project's round
2. Round 1's EE (756,559.2864, in `src/ark/baseline.py`) is the difference between his two releases
under the unchanged weight model, computed 2026-08-17, and was never quoted by him.
