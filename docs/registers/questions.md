# Questions put to the reviewer, with his answers when they come. `just ship` copies every open row past its remind-on into the mail draft, one line each.

Status is `open`, `answered` or `withdrawn`. An answered row states its answer in the row.
An asked-on of `draft` means the row has not been sent: approve the wording or delete it before the ship.
Export-ignored: the page does not travel in the delivery.

| asked-on | question | status | remind-on |
|---|---|---|---|
| draft | Which release starts the scoring clock t_i, and is elapsed time counted in whole days or fractional? Your 2026-08-20 rule names the latest benchmark package, but S_6 = 6.88 and S_7 = 6.302372 both fit a clock started at the 2026-08-21 11:19 release with elapsed time rounded up to whole days (t_7 = 12 for a submission sent 2026-09-02 05:50). | withdrawn | phase-8 mail |
| 2026-09-04 | Your 0903 update redefines t_i as max(1, receipt_date_i - task_assignment_date_member) in whole calendar days. **You then scored round 8 as S = 10 x (18.769714 / 33) = 5.687792, and we cannot reproduce the 33**: the benchmark interval gives t = 1 and the assignment interval t = 45 counting from 2026-07-21, the earliest date our records support. A divisor of 33 implies an origin of 2026-08-02. Which date is t_i counted from, and does the revision re-score the awarded rounds? | withdrawn | next mail |
