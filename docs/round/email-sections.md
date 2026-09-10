# Email sections for the current round

**Read by `scripts/round/fill_report.py`, one block per `## ` heading, in the order the template's
stubs appear.** It lives here rather than in the draft because `private/email-draft.md` is
regenerated and prose typed into it is destroyed by the next fill. Export-ignored, so it never
reaches the reviewer.

**There are no sections below, deliberately.** From round 9 the email template carries no stubs:
its prose is written in `private/email.template.md` and its figures are tokens filled from the
store. A block left here would be injected into the first stub a future template adds, and the
round-8 draft was nearly sent with round-6 prose for exactly that reason. Add a `## ` heading here
only in the same change that adds the stub it fills.
