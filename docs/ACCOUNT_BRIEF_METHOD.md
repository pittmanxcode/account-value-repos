# Account brief method — v1

**Owner:** Michael Pittman · **Effective:** 2026-10-09 · **Derived from:** the Valon discovery
thread of Oct 8, 2026 (`~/Downloads/valon-thread-transcript.md`) and the Factory discovery study
sheet v2 (`docs/reference/factory-discovery-study-sheet-v2.pdf`).

This file governs how an **account brief** (`accounts/<slug>/<slug>_account-brief.md`) gets written. The
workbook gives a dollar figure. The brief gives the story behind it, in words Michael can say to a
senior engineering executive at that company and check himself.

The brief is a reasoning-and-research pass, not a code step. Code assembles the inputs
(`account-value brief-context <slug>` → `brief-context.md`). Claude, with web search, does the rest
following `.claude/skills/account-brief/SKILL.md`. Every brief is judged against this document.

---

## 1. What Michael actually asked for

These are his requests from the Valon thread, in order. The brief exists to answer them for every
account, before he has to ask.

1. **Pain, implication, and the right discovery questions to make Factory a tier-one priority this
   quarter.** Use the insurance-salesperson chain as the model: a few facts, linked, until the
   purchase becomes a critical need. Identify the ICP from the study sheet, then use the postings to
   quantify and implicate the pain of *not* choosing Factory this quarter.
2. **Explain it so he can retell it.** This is research ahead of cold outreach. He needs enough
   background on the company, its industry, and the SDLC to hold the conversation in his own words,
   with quantified pain, PBOs (positive business outcomes), and negative consequences. He must be
   able to double-check every claim.
3. **Count the whole workload.** The forcing project (a migration, a deadline) doesn't make KTLO,
   incidents, and feature work go away. All of that time belongs in the pain, consequences, and
   PBOs.
4. **Who cares about this, and why.**
5. **A two-part write-up.** Part one: quantified pains, likely deal size, PBOs, consequences,
   potential contacts. Part two: executive summary and 3–5 discovery questions that implicate pain
   and attach the problem Factory solves to the biggest business issue.

Two things from that thread were **situational, not standing**, and are not part of the brief:
the outreach email, and the note to "ask what coding tools they use" (a reaction to one
unverified claim). Nothing competitive goes in the brief.

## 2. The corrections, and why each happened

| Where | What went wrong | The rule it produced |
|---|---|---|
| Turn 1 | Written as a call script for someone fluent in the domain | Background first. Define every term. One idea at a time. Michael has to be able to retell it. |
| Turn 3 | Treated the migration as the whole pain | The pain is the total load on one team: features, client work, the forcing project, KTLO, incidents. Say why they get worse together, and why hiring doesn't close the gap quickly. |
| Turn 6 | Stated "their engineers already use Claude Code" as fact, from a third-party tag count | Nothing is stated that wasn't seen at its source. Third-party aggregators are leads, not facts. If it can't be labelled, it's out. |
| Turn 8 | Proposed positioning Factory against their coding tool | No competitive positioning, ever. |

## 3. The research sequence that worked

In order, stopping early when a step comes back empty:

1. **The postings, verbatim.** `brief-context.md` has them. Read all of them, not the figures list.
   Look for: scale statements (volume, growth, loans/users/transactions), named customers, named
   systems and stacks, dated projects, team sizes, what a role is hired to fix.
2. **The company in the news, last 12 months.** Funding (amount, date, valuation, investors),
   named customer wins with dates, product launches, leadership changes. Prefer the company's own
   release or a trade publication; note the date.
3. **The forcing event.** A dated commitment the engineering team has to land: a customer
   boarding, a migration with an end-of-support date, a regulatory deadline, a launch tied to a
   contract. If none is found, say so. A brief without a dated event is a weaker brief, not an
   invented one.
4. **Why lateness costs them.** The regulation, SLA, contract term, or customer that makes a slip
   expensive. Check the primary source (the CFR section, the filing, the release). In regulated
   industries this is usually the strongest link in the chain.
5. **Who absorbs the cost.** Investors who are also customers, a board that just funded a scale
   story, a regulator, a flagship client.
6. **The study sheet.** Only now: which entries the evidence actually supports, with the precedent
   letter and the caveats carried over. Entries without evidence from steps 1–5 are not in the brief.
7. **Verification pass.** Every number re-read at its source. Anything that was only seen on an
   aggregator or in a search snippet gets downgraded to "unknown" or cut.

## 4. The quality bar

A brief is acceptable when all of these hold:

- **The chain is explicit.** Event → date → load on the team → who absorbs the cost → what breaks.
  Each link carries a label.
- **Every number is labelled**: `company-disclosed` (the company or its customer said it, with
  the source), `third-party` (an outside site, named), `pipeline` (this repo's estimate, with the
  caveat), `inference` (reasoning, said so), `unknown` (no source; the formula that would size it).
- **Unknowns stay unknown.** They are written as the thing to learn, with the formula, never
  filled in.
- **Quantified pains are pains, not metrics.** (Michael, Oct 10, after Oscar Health: "members,
  2.9M @46% YoY is not actually pain.") Every row must read as a cost, risk, or deadline that a
  named role at the account is carrying, and the number sizes that burden. Test each row: "who
  bears what, and what does it cost them if it isn't handled?" If the row only describes the
  company (membership, revenue, valuation, headcount), it is context: it belongs in the chain or
  in a one-line "Context figures" note under the table, not in the pains table. Columns are
  **Pain (who bears what) · Size · Label**. "46% membership growth on a platform team five SRE
  hires short, during open enrollment" is a pain; "2.96M members, +46%" is not.
- **The whole workload is counted**, not just the forcing project.
- **Michael can check it.** Each source has a step he can follow (open this page, search for
  this phrase).
- **It is short and scannable.** Michael's review of the Valon v1 (Oct 9, 2026): "a bit verbose,
  and could be written to be digested easier." Limits from that review, revised the same day after
  the Fivetran example: the brief is under 1,200 words, not counting the Sources table, the
  Droids table (the proof-point quotes are worth their length), or the Quantified pains table
  (its "who bears what" rows are sentences by design; exempted Oct 10 after DigitalOcean); "In one paragraph" is four
  sentences at most; Background is four bullets; "The chain" is prose, not a table, because the
  links need explaining, not listing; a fact appears once, where it carries the most weight;
  caveats go in the row or sentence they qualify.
- **Discovery questions are built from facts in this brief**, each one naming the fact, checking
  the pain exists before sizing it, then getting the consequence in their words, with what to do on
  a "no". If no fact is strong enough, the section says so.
- **The self-check block passes** (section 6).

## 5. Brief structure

```
# <Company> account brief
<date> · sources checked <date>

## In one paragraph            — the chain, for a VP of Engineering
## Background                   — who they are, who their customers are, 4–6 concepts in plain words
## The chain                    — prose: event → date → load → who absorbs the cost → what breaks,
                                  each link labelled inline; two paragraphs at most
## The workload stack           — the five kinds of work; why they worsen together; why hiring is slow
## Quantified pains             — table: pain (who bears what) · size · label; pains only, see §4;
                                  context figures in one line below the table
## Likely deal size             — arithmetic on public price; inputs still needed; "not a quote"
## Positive business outcomes
## Consequences if nothing changes
## Who cares and why            — roles only: what they're held to · why it hits them · part in a deal
## Discovery questions          — 3–5, fact-anchored, or "none strong enough yet"
## What Droids do and don't do here — per bucket: why it fits, and the proof-point quote itself
                                  (Michael, Oct 9: no entry numbers or bare company names; the
                                  factor and the quote he can say on a call, with its caveat inline)
## Sources and how to check     — each source with the check step
## Self-check
```

## 6. Self-check

Printed at the end of every brief, each line answered yes/no with a one-line reason:

- Every number carries a label.
- Every row in Quantified pains names who bears what; no row merely describes the company.
- Nothing is stated that wasn't seen at its source.
- The forcing event is dated, or marked unknown.
- The full workload stack is counted.
- Each discovery question names the fact it is built on.
- No competitive positioning. No outreach copy.
- The pipeline's hours figure is presented as a starting estimate with its caveat.

## 7. Writing rules

From Michael's standing preferences: skeptical over encouraging; no cheerleading; half the length;
define jargon; one concept at a time; label every number; never fill gaps with invented figures;
never "kill"/"dead" (use cut, drop, retire); roles, not names, for contacts.

## Changelog

| Version | Date | Change |
|---|---|---|
| v1 | 2026-10-09 | First version, from the Valon thread and study sheet v2. |
