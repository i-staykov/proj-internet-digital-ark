# Draft submission email to Prof. Ding

Ivo to send. Every figure below is substituted from the store by `scripts/fill_report.py` at
packaging time, so the email and the archive cannot disagree. Edit the template, not the filled copy.

**To:** Xiaowei Ding
**Cc:** Kay Giesecke
**Subject:** Re: Trial Project

---

Dear Professor Ding,

Thank you for the detailed feedback. I have restructured this round around the English-website
standard, and the deliverable is attached.

**Two separate sets, as the standard requires.** I now ship English-verified additions and
non-verified additions as disjoint files, so you can merge whichever you wish without deduplicating
against each other. A domain enters the English set only when the archived body text of its own site,
in that specific year, was read and was more than half English. Every verdict records the exact
snapshot URLs it was read from, so any one of them can be refetched and rechecked. This replaces the
TLD-based estimate with archived-content evidence, as your section 6 asks.

Current position against merged260730:

| | pairs |
|---|--:|
| English-verified additions | **258** |
| Non-verified additions (disjoint) | 125,459 |
| Total additions | 125,717 |

Every pair that was checked and rejected is listed individually in `disqualified.csv` with the
reason, so no exclusion is left as an assertion. Pairs the engine has not yet reached are labelled
`unchecked` and make no claim either way.

**On the size of the English set, and what it will be.** Verification is bound by how fast the
Internet Archive will answer, not by anything in the pipeline: measured throughput is about 367
(domain, year) pairs per hour, of which 64% come back English. The engine is running
continuously and I expect roughly **7,953 to 11,362 English-verified pairs by Monday
midday**, at which point I will send updated files.

That leads to my one question. At this rate, verifying the whole current backlog of 125,717
additions would take several weeks of continuous querying. **Would you prefer that I keep the engine
running to build the English set as large as possible, or stop at a given date and submit what is
verified by then?** I am happy either way; it mainly affects whether I keep discovering new domains
in parallel or put everything into verification.

I should also mention that I found and fixed several defects in my own verification engine this
week, and discarded every verdict produced before the fixes rather than ship them. A few domains had
been admitted on registrar parking pages, a keyword link farm and, in one case, a webmail login
screen. The report documents each one, because I would rather you see how the method was tested than
only what it produced.

Everything remains reproducible: the archive contains the code, the evidence as a Parquet graph, and
a `verify.sh` that re-checks the results without installing anything.

Thank you also for the kind words about the exams. My last one is on Monday, and I am looking
forward to having proper time for this again afterwards. I would be very glad to hear about the
projects you have in mind, and I remain keen to contribute to the chair as a student assistant.

Best regards,
Ivaylo

---

## Notes for Ivo, not part of the email

- The question at the end is the only thing needing an answer, and it is phrased so any reply is
  useful. It also quietly tells him the English set is small for a reason he can verify.
- The paragraph about our own defects is a deliberate choice. He is a reviewer who merges our files
  into a shared baseline, and a collaborator who reports his own failures is worth more to him than
  one who does not. It also pre-empts the obvious question about why the English count is far below
  the total.
- Nothing here asks for a deadline extension, and nothing apologises. The numbers do the work.
