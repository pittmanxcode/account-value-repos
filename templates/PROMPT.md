# Reusable Account Value-Repository Prompt System

Run this end-to-end for any company. Replace every `{{PLACEHOLDER}}` before
running. Copy this template folder, the `scripts/` directory, and
`methodology/` into a new repository named
`/repos/{{company_slug}}-value-repository/`.

---

## THE PROMPT

I'd like you to build a value repository for {{COMPANY_NAME}} as an account.

Search through every available job description available at
{{CAREERS_URL}}, make a catalogue of the various responsibilities in each of
the job descriptions.

Once that is finished and you have the catalogue, parse through that catalogue
and assign a confidence score for how well Factory could run a mission or
project to complete these responsibilities at the level of an experienced
professional.

Once you've finished that, build a report of the responsibilities that
Factory is best fit for, and research the average time spent (with a given
basis — i.e., per service, or per job) and an estimate of overall role hours
or role-days spent on that type of work.

Collect the average pay for these roles, organize a list of the
responsibilities by role and role-hours, from best fit for Factory to least
fit.

Give me an overall summary of estimated potential hours saved and/or
productivity gains from boosting the effectiveness of given roles/operators.

---

## PHASE 0 — Setup decisions (ask the user before building)

Ask these four questions, offering the listed options:

1. **Deliverable** — Repository + Excel workbook | Repository only |
   Executive report only
2. **Compensation basis** — Local-market pay + USD | US-equivalent pay |
   Posted pay only
3. **Value presentation** — Conservative / base / upside scenarios |
   Base estimate only | Hours only, no dollar value
4. **Factory deployment boundary** — Normal setup + human review |
   Bespoke integrations + human review | Out-of-box only

Record the answers as locked assumptions in `methodology/pay_and_time.md`.
(Reference answers used for the Crunchyroll build: Repository + Excel
workbook; US-equivalent pay; three scenarios; normal setup with human review,
plus bespoke noted where possible.)

## PHASE 1 — Collection

1. Find the company's applicant tracking system. For Greenhouse customers
   the public board API is:
   `https://boards-api.greenhouse.io/v1/boards/{{board_token}}/jobs?content=true`
   (returns all postings with full descriptions as JSON, no auth). Adapt the
   same approach for Workday/Lever/Ashby if needed.
2. Fetch the careers page the user provided; reconcile the posting count
   against the API count and document any discrepancy.
3. Save the raw snapshot to `data/raw/` (never edit it afterward).
4. Parse into `data/processed/jobs.csv` (job_id, title, department, location,
   dates, URL, posted pay range if present) and
   `data/processed/responsibilities.csv` (one verbatim bullet per row with
   section context). Handle: heading variants ("Key Areas of Responsibility",
   "What You'll Do" with sub-headings), plain-line pseudo-headings, non-English
   postings, and noise lines ("In the role of X, you will report to…").
   Target: zero postings with zero bullets.

## PHASE 2 — Taxonomy and time allocation

1. Normalize bullets into a cluster taxonomy (30-ish clusters for a company
   this size). Tune cluster regexes on a random sample from every department;
   watch plural-word boundary misses (`\baudit\b` does not match "audits" —
   singularize before matching).
2. Allocate each role's annual hours across its clusters in proportion to
   bullet counts (documented proxy, not a time study).
3. Productive hours per FTE-year: {{ANNUAL_HOURS}} (default 1,920 = 40 × 48).
   Keep it an editable constant.

## PHASE 3 — Fit scoring (rubric)

Score each cluster 0–100, weighted: digital executability 25, match to
Factory workflows 25, input/system access 15, output verifiability 15,
professional quality with human review 15, risk/governance 5.

Produce two scores per cluster:
- **fit_normal** — ordinary Factory setup: repo/document access, approved
  connectors, terminal/browser tools, Missions, automations, human approval.
- **fit_bespoke** — same plus a *named* integration build (custom connector,
  MCP server, internal API workflow, evaluation harness). Never treat bespoke
  capability as already available; every uplift names its build.

Hard-penalize: unavailable internal systems, physical work, relationship
ownership, executive judgment, negotiation, people management, taste-led
decisions, legal/security/tax sign-off.

Also record per cluster: addressable share (0–1), net time reduction triple
(conservative/base/upside), time basis, benchmark source, evidence confidence,
rationale, recommended workflow, human checkpoint.

## PHASE 4 — Pay

1. Prefer posted pay ranges captured in Phase 1 (US postings).
2. Otherwise map each title to a SOC occupation + seniority level and use
   BLS OEWS medians (via O*NET if bls.gov blocks automation) × seniority
   factor: entry 0.80, mid 0.90, senior 1.10, lead 1.25, staff 1.50,
   manager 1.35, director 1.60, exec 2.00.
3. Apply the Phase 0 decision for non-US locations (US-equivalent default).
4. Fully loaded view = base × {{LOADED_FACTOR}} (default 1.30).
5. Record per-row pay provenance (`pay_source`).

## PHASE 5 — Value model

```
saved_hours = role_hours × addressable_share × net_time_reduction
              × adoption × (fit / 100)
```

- Adoption: conservative {{ADOPT_CONS}}, base {{ADOPT_BASE}}, upside {{ADOPT_UPS}}.
- Net time reduction is applied after human-review overhead.
- Report saved hours, saved days (÷8), FTE equivalent (÷ {{ANNUAL_HOURS}}),
  % capacity freed, salary-equivalent and loaded value.
- Aggregate totals assume one FTE per open posting — label as open-req
  equivalents, not company-wide payroll savings.
- Report bespoke upside separately from the baseline.

## PHASE 6 — Deliverables

- `README.md` — scope, navigation, snapshot date, limitations
- `REPORT.md` — executive findings, top opportunities, role-by-role ranking,
  scenario totals, normal-setup recommendations, bespoke opportunities
- `data/raw/`, `data/processed/` (jobs, responsibilities, normalized,
  scored, role summary, cluster ranking)
- `methodology/` — rubric, pay/time method, sources
- `scripts/` — 01_parse_postings.py, 02_build_value_model.py, 03_validate.py,
  04_make_workbook_spec.py, 05_convert_workbook.js
- `outputs/{{company_slug}}_factory_value_repository.xlsx` — sheets:
  Executive Summary (with plain-text summary), Ranked Responsibilities,
  Bespoke Opportunities, Role Summary, Jobs, Responsibility Catalogue,
  Compensation, Time Benchmarks, Sources, Methodology — each opening with a
  plain-text explainer row.

## PHASE 7 — Validation gate (all must pass before delivery)

- Posting count reconciles with the live board
- Unique IDs; source URL for every posting; verbatim evidence for bullets
- Fit scores within 0–100; fit_bespoke ≥ fit_normal
- Each role's hours sum to {{ANNUAL_HOURS}} (±0.5)
- Scenario monotonicity; saved hours ≤ role-hours
- Pay provenance on every row; hourly = annual ÷ {{ANNUAL_HOURS}}
- Workbook reopens with a parser; sheet row counts match source CSVs

## NOTES FROM THE CRUNCHYROLL RUN

- BLS blocks automated retrieval; O*NET republishes the wages and allows it.
- The Cloudflare browser connector failed auth; `agent-browser` (bundled
  Chrome) worked for blocked pages. Install: `agent-browser install
  --with-deps`.
- Expect ~1 in 6 bullets to be noise (culture, EEO, reporting lines); flag,
  don't delete.
- Non-English twin postings: map to the English twin's cluster distribution.
- ExcelJS must be installed under `tmp/`, not the project root.
- Budget roughly: collection 10%, parsing 20%, taxonomy/scoring 35%,
  value model 15%, docs 10%, workbook 10% of the effort.
