# Crunchyroll × Factory Value Report

**Snapshot:** September 29, 2026 · 77 open postings · 964 verbatim
responsibilities · 30 normalized clusters · all figures use US-equivalent pay
per approved assumption.

---

## 1. Executive summary

Factory can perform, at experienced-professional quality under a normal setup
with human review, work worth **18,695 hours per year** across Crunchyroll's
77 open-req equivalents — **12.6% of the 147,840-hour portfolio**, equal to
**9.7 FTE** or 2,337 role-days. Three scenarios:

| Scenario | Saved hours/yr | Saved role-days | FTE equivalent | % capacity freed | Salary-equivalent | Fully loaded (×1.3) |
|---|---|---|---|---|---|---|
| Conservative | 7,997 | 1,000 | 4.2 | 5.4% | $652,011 | $847,614 |
| **Base** | **18,695** | **2,337** | **9.7** | **12.6%** | **$1,524,223** | **$1,981,490** |
| Upside | 30,830 | 3,854 | 16.1 | 20.9% | $2,513,637 | $3,267,728 |

Bespoke integrations (only where a named build exists, with human checkpoints)
lift the base scenario to ≈ **20,912 hours (+12%)**.

Pay basis: 33 US postings use Crunchyroll's own posted pay ranges; the other
44 use BLS OEWS May 2025 occupation medians adjusted by seniority
(`pay_source` column in Role Summary).

Productivity gains are not only hours saved: reviewer-attention multiplies
effectiveness. Where Droid drafts and a professional reviews, the operator
spends their freed hours on judgment work — the modeled net reduction already
deducts review overhead.

## 2. Where Factory fits best (normal setup)

Ranked by portfolio saved hours in the base scenario:

| # | Responsibility cluster | Fit | Portfolio hours | Saved h (base) | Basis |
|---|---|---|---|---|---|
| 1 | Software Development & Code Review | 90 | 14,548 | 2,946 | per sprint |
| 2 | Analytics, Reporting & Dashboards | 90 | 11,895 | 2,890 | per reporting cycle |
| 3 | Accounting Operations (AP, reconciliations) | 78 | 10,545 | 1,943 | per monthly period |
| 4 | ML & AI Engineering | 82 | 9,000 | 1,356 | per model lifecycle |
| 5 | Cross-Functional Collaboration (generalist) | 50 | 28,004 | 1,344 | mixed |
| 6 | Security & Identity Engineering | 70 | 13,748 | 1,299 | per sprint |
| 7 | Contracts, Rights & Royalty Administration | 75 | 6,326 | 811 | per contract event |
| 8 | CRM & Lifecycle Marketing Operations | 78 | 4,616 | 756 | per campaign cycle |
| 9 | Training, Enablement & Documentation | 85 | 2,572 | 553 | per program cycle |
| 10 | Test Automation & QA | 92 | 2,095 | 553 | per sprint |

Highest-quality fits (score ≥85): QA/testing, software development,
analytics/BI, data engineering, CI/CD, training and documentation,
CX operations analytics, monitoring — all code- or data-first with
mechanically verifiable outputs.

## 3. Best-fit roles

Top roles by saved hours (base scenario):

| Role | Dept | US-equiv pay | Saved h | % freed |
|---|---|---|---|---|
| Senior Engineer, Insights & Reliability | Eng: Fan Experiences | $149,578 | 395 | 20.6% |
| Software Engineer II, Frontend | Eng: Fan Experiences | $122,382 | 389 | 20.2% |
| CX Operations Analyst | Customer Experience | $70,884 | 370 | 19.3% |
| Lead Finance Data Analyst | Accounting | $150,288 | 356 | 18.5% |
| Senior Software Engineer, Backend/Full Stack | Engineering | $149,578 | 354 | 18.4% |
| Data Engineer III | Eng: Platform | $149,578 | 339 | 17.6% |
| Senior Database Engineer | Eng: Platform | $153,450 | 333 | 17.3% |

Least-fit roles (as expected): the anime co-production producers (4.7%),
Security Analyst ops duties (4.8%), Tax Manager (5.2%), Senior SOX Analyst
(6.0%) — judgment, sign-off, and relationship-bound work.

## 4. Department view (base scenario saved hours)

Engineering: Fan Experiences (2,625) · Engineering: Platform (2,105) ·
Customer Experience (1,657) · Finance (1,218) · CDI (1,064) · Enterprise
Technology (1,045) · Accounting (1,028) · Engineering: Video Platform (803).

## 5. Bespoke integration opportunities

Where a named build materially raises fit (normal → bespoke):

| Cluster | Build | Fit gain |
|---|---|---|
| Localization & Creative Adaptation | TMS connector + style-guide fine-tune | 60 → 80 |
| Legal, Business Affairs & Content Protection | CLM + anti-piracy evidence-pack connectors | 35 → 55 |
| Physical Supply Chain | ERP/supply-chain planning connectors | 25 → 45 |
| Procurement & Sourcing | Source-to-pay platform connector | 45 → 65 |
| Accounting Operations | ERP connector with maker-checker payment controls | 78 → 88 |
| Creative & Product Design | Figma-class design-tool connector | 35 → 60 |

Bespoke work pays best in transaction-heavy finance/accounting systems and in
localization volume; it least changes relationship-owned and physical work.

## 6. Recommendations

1. **Pilot on engineering analytics:** combine code review, test automation,
   and CI/CD automation on one Crunchyroll engineering team; the three
   clusters carry a combined ~5,600 portfolio hours and the verification
   loop (tests, PRs) is already native to Factory.
2. **Second wave — finance and CX:** AP/reconciliation prep and CX ticket
   analytics need an ERP/helpdesk connector (bespoke tier) but hold ~2,700
   combined base-scenario hours.
3. **Use agents for enablement now:** training, SOP and documentation work is
   low-risk, high-visibility (85 fit) and builds trust for later phases.
4. **Do not lead with regulated or relationship work:** tax filings, legal
   sign-off, negotiations, and people management score lowest; introduce
   agents there only as drafting assistance behind professional review.
5. **Treat the 1-FTE-per-posting model as a ceiling anchor:** real value
   scales with actual headcount in these functions, which the public board
   does not reveal.

## 7. Method and caveats

Fit scores follow the weighted rubric in `methodology/rubric.md` (25/25/15/
15/15/5). Hours, pay, and scenarios follow `methodology/pay_and_time.md`.
All parameters are editable constants in `scripts/02_build_value_model.py`;
the full pipeline re-runs end-to-end and passes a 20-check validation gate
(`scripts/03_validate.py`).

Key caveats: one FTE assumed per open posting; time allocation is
bullet-proportional rather than a measured time study; non-US postings are
valued at hypothetical US-equivalent pay; scenario parameters are documented
assumptions anchored to cited benchmarks, not guarantees.
