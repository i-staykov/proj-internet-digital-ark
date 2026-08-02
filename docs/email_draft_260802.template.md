# Draft submission email to Prof. Ding

Ivo to send. Every figure is substituted from the store by `scripts/fill_report.py` at packaging
time, so the email and the archive cannot disagree. Edit the template, not the filled copy.

**To:** Xiaowei Ding
**Cc:** Kay Giesecke
**Subject:** Re: Trial Project

---

Dear Professor Ding,

Thank you for the detailed feedback. This round is restructured around the English-website standard,
and the deliverable is attached.

**Two separate sets, as the standard requires.** English-verified additions and non-verified
additions now ship as disjoint files, so you can merge either without deduplicating them against each
other. A domain enters the English set only when the archived body text of its own site, in that
specific year, was read and was more than half English. Every verdict records the snapshot URLs it
was read from, so any of them can be refetched and rechecked. That replaces the TLD-based estimate
with archived-content evidence.

Against merged260730:

| | pairs |
|---|--:|
| English-verified additions | **[ENGLISH]** |
| Non-verified additions (disjoint) | [UNVERIFIED] |
| Total additions | [TOTAL] |

Every pair that was checked and rejected is listed individually in `disqualified.csv` with its
reason. Pairs the engine has not yet reached are labelled `unchecked` and make no claim either way.

**On the size of the English set.** Verification is bound by how fast the Internet Archive will
answer: measured throughput is [RATE] (domain, year) pairs per hour, of which [SHARE] come back
English. The engine runs continuously, and on that rate the set should reach roughly **[PROJ_LOW] to
[PROJ_HIGH] pairs by Monday midday**. That is arithmetic rather than a promise, and the lower figure
already allows for the Internet Archive throttling this project, which it has done before. I will
send the updated numbers and files on Monday.

That leads to my one question. At this rate, verifying the whole backlog of [TOTAL] additions would
take several weeks of continuous querying. **Would you prefer I keep the engine running to build the
English set as large as possible, or stop at a given date and submit what is verified by then?** I am
happy either way; it mainly decides whether I keep discovering new domains in parallel or put
everything into verification.

I should also mention that I found and fixed several defects in my own verification engine this week,
and discarded every verdict produced before the fixes rather than ship them. A few domains had been
admitted on registrar parking pages, a keyword link farm and, in one case, a webmail login screen.
The report documents each one, because I would rather you see how the method was tested than only
what it produced.

Everything remains reproducible: the archive contains the code, the evidence as a Parquet graph, and
a `verify.sh` that re-checks the results without installing anything.

Thank you also for the kind words about the exams. My last one is on Monday, and I am looking forward
to having proper time for this again afterwards. I would be very glad to hear about the projects you
have in mind, and I remain keen to contribute to the chair as a student assistant.

Best regards,
Ivaylo

---

## Notes for Ivo, not part of the email

- The question at the end is the only thing needing an answer, and any reply to it is useful. It also
  quietly explains why the English set is small, in a way he can verify.
- The paragraph about the engine's own defects is deliberate. He merges these files into a shared
  baseline, so a collaborator who reports his own failures is worth more to him than one who does
  not, and it pre-empts the obvious question about the English count.
- Nothing here asks for an extension and nothing apologises. The numbers do the work.
