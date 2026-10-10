# Account Value Repos

One automated pipeline that produces review-ready account value packages
(`{Company} × Factory Value.xlsx` plus reports and full provenance), with two
intake loops:

| Loop | What you do | Status |
|---|---|---|
| **V1 — Manual account intake** | Type the company name. Everything after that — identity resolution, compelling-event research, job-board analysis, value reconciliation, workbook, validation, review PR — runs automatically. | **Ready now** |
| **V2 — Buyer-readiness well intake** | The well supplies ranked, pre-qualified accounts and any value it already computed; the pipeline preserves that value and adds job-board analysis. | Implemented and tested; **publication disabled** until the well passes its readiness gate |
| **Account brief** | After a package exists, `account-value brief-context <slug>` gathers the postings and numbers; the `account-brief` Claude Code skill researches the company and writes `accounts/<slug>/<slug>_account-brief.md`: the chain of reasoning, real pains, who cares, fact-anchored discovery questions, and what Droids do and don't do. | **Ready now**; one account at a time, each on an explicit "approved" |

Both loops share the same analysis engine, the same 10-sheet workbook format
modeled on the golden Crunchyroll build, and the same approval contract: a
generated account is approved when its record is merged to the default branch.

## Choose your loop

**"I have a company in mind"** → V1:

```bash
make setup                 # once: venv, package, exceljs under tmp/
account-value doctor       # preflight
account-value run "Acme Corp"
# or with known identity:
account-value run "Acme Corp" --domain acme.com --careers-url https://acme.com/careers
```

You confirm the identity the wizard resolves; everything else is automated.
When validation passes, the package is pushed to a branch and one draft PR is
opened for your review. When it fails, a failure report lands in `failures/`
and nothing is published.

**"The well should feed it"** → V2 (read-only for now):

```bash
account-value well doctor   # readiness gate against the well's export
account-value well plan     # what a batch would process, once ready and enabled
account-value well run      # blocked: well_enabled: false in config.yaml
```

**"The package exists, I need the story"** → the account brief:

```bash
account-value brief-context valon          # writes accounts/valon/brief-context.md
# then, in Claude Code at the repo root:
/account-brief valon                        # research + reasoning, writes accounts/valon/valon_account-brief.md
```

The brief is judged against [docs/ACCOUNT_BRIEF_METHOD.md](docs/ACCOUNT_BRIEF_METHOD.md).
Files are named `<slug>_account-brief.md` so they don't collide when copied into one
Google Drive folder next to `<Company> × Factory Value.xlsx`.

**Collectors.** Greenhouse, Lever and Ashby boards are read through their public APIs;
Workday sites through the public JSON the careers page itself loads. The prebuilt
collector for the configured ATS (or JSON-LD on the careers page) always runs first;
the Workday reader is tried only when that fails and the careers URL is a Workday host.
The path used is recorded in the package's collection notes.

## Learn more

- [docs/RUNBOOK.md](docs/RUNBOOK.md) — fresh machine to finished brief, step by step
- [docs/ACCOUNT_BRIEF_METHOD.md](docs/ACCOUNT_BRIEF_METHOD.md) — what a brief must contain and why
- [docs/MANUAL_ACCOUNT_INPUT.md](docs/MANUAL_ACCOUNT_INPUT.md) — V1 walkthrough
- [docs/AUTOMATED_WELL_INPUT.md](docs/AUTOMATED_WELL_INPUT.md) — V2 contract and enablement checklist
- [docs/VALUE_RECONCILIATION.md](docs/VALUE_RECONCILIATION.md) — how inherited and job-board value combine
- [docs/REVIEW_GUIDE.md](docs/REVIEW_GUIDE.md) — reviewing a package PR; what merge approves
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — credentials, logs, idempotency, recovery

## What "value" means here

Every number is a **value component** with evidence, provenance, and an
overlap key:

- **Inherited compelling-event value** (typed at intake or imported from the
  well) is preserved verbatim — never recalculated, never overwritten.
- **Job-board capacity value** comes from parsing the company's open postings
  and scoring them against the Factory-fit taxonomy (three scenarios:
  conservative/base/upside).
- **Combined totals** require overlap reconciliation: confirmed duplicates
  count once, distinct work surfaces sum, and unresolved overlaps block a
  combined headline rather than silently double counting.

## The golden example

The original Crunchyroll build lives unchanged under
`examples/crunchyroll/` — it is the regression fixture: the generalized
pipeline must reproduce its established headline totals within rounding
tolerance. Run its original pipeline with:

```bash
cd examples/crunchyroll && python3 scripts/01_parse_postings.py && \
python3 scripts/02_build_value_model.py && python3 scripts/03_validate.py
```

## Development

```bash
make setup PYTHON=python3   # .venv + editable install + exceljs under tmp/ (3.12+; 3.14 works)
make test                   # pytest
make lint                   # ruff
```
