# V1 — Manual Account Input Loop

You supply the account; the system supplies the analysis. The only manual step
is typing the company name and confirming the identity the wizard resolves.

## Prerequisites

1. `make setup` (Python 3.12, Node, npm).
2. `account-value doctor` — all checks pass. Publication additionally
   requires `ACCOUNT_VALUE_GITHUB_TOKEN` in the environment (a token with
   write access to `pittmanxcode/account-value-repos`).

## Run an account

### Interactive wizard (fewest mistakes)

```bash
account-value run
```

The wizard asks for the company name, resolves the official domain and
careers site from public sources, and shows a confirmation screen before any
research starts.

### Hybrid: flags for what you already know

```bash
account-value run "Acme Corp" --domain acme.com
account-value run "Acme Corp" --domain acme.com --careers-url https://acme.com/careers
```

Flags prefill and skip those questions. Anything still missing is prompted.

### Identity ambiguity

If the deterministic probes find several plausible domains, the wizard lists
them with the resolved site titles and asks you to pick one. If none respond,
it fails with guidance to supply `--domain` or `--careers-url` and writes a
failure report — nothing is published.

### Inherited compelling-event value (optional)

If you already know a compelling event and its value, pass a JSON file:

```json
[
  {
    "component_id": "oracle-java-estate",
    "description": "Oracle JDK licensing savings on the Java estate",
    "work_surface": "event_r1",
    "signal_id": "R1",
    "hard_cost_usd": 40000,
    "confidence": "Medium"
  }
]
```

```bash
account-value run "Acme Corp" --domain acme.com --inherited events.json
```

Inherited value is preserved verbatim and reconciled against the job-board
analysis (see [VALUE_RECONCILIATION.md](VALUE_RECONCILIATION.md)). If you
don't have any, skip it — the compelling-event research stage looks for
evidence automatically.

## What runs automatically

1. Identity: official domain, careers page, ATS discovery (Greenhouse, Lever,
   Ashby probed by public board API).
2. Collection: the full posting inventory with verbatim responsibilities,
   saved as an immutable raw snapshot; posting counts reconciled.
3. Compelling-event research: posting text is matched against the versioned
   signal registry (`registry/signals.yaml`); anchored signals with
   observable units produce defensible value; everything else is recorded as
   "unknown, where looked".
4. Scenario model: responsibilities classified against the taxonomy, pay
   mapped with provenance (posted ranges first, else BLS OEWS medians),
   conservative/base/upside saved hours and salary-equivalent value.
5. Reconciliation: inherited/event value vs job-board value, overlap-checked.
6. Validation: the deterministic gate must pass before publication.
7. Publication: a branch `automation/account-<slug>` with the package and a
   draft PR titled "Account value: <company>".

## Outputs

```
accounts/<slug>/
├── README.md, REPORT.md
├── outputs/<Company> × Factory Value.xlsx   (10 sheets)
├── data/raw/                                  (immutable snapshots)
├── data/processed/                            (jobs, responsibilities, scoring)
├── account-value.json                         (provenance, fingerprints, versions)
├── reconciliation.json                        (overlap decisions, combined totals)
└── validation-report.txt
```

## Reruns and failures

Rerun an account from its saved request (no retyping):

```bash
account-value run --request requests/<slug>.yaml
```

Any failure writes `failures/<slug>-<timestamp>.md` and publishes nothing.
Fix the cause and rerun; publication is idempotent (reusing the same branch
and PR).

## Review

Open the draft PR, review the workbook (see
[REVIEW_GUIDE.md](REVIEW_GUIDE.md)), and merge when satisfied. Merging
approves the account for the future contact-search handoff. Nothing is ever
auto-merged, and no contact research happens in this phase.

## Example session

```
$ account-value run
Company name: Crunchyroll

Resolving identity from public sources (deterministic probes)…

--- Confirm account request ---
  Company:     Crunchyroll
  Domain:      crunchyroll.com
  Careers URL: https://www.crunchyroll.com/about/jobs
Run the analysis with this identity? [Y/n]: y

request saved: requests/crunchyroll.yaml (rerun with: account-value run --request requests/crunchyroll.yaml)
…pipeline stages…
published: branch automation/account-crunchyroll -> https://github.com/pittmanxcode/account-value-repos/pull/42
```
