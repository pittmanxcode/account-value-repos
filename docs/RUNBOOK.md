# Runbook — from a fresh machine to a finished account brief

Every step is a command you type or a thing you say to Claude Code. Nothing here
publishes, pushes, or spends money without a separate approval.

## 0. One-time setup on a new machine

```bash
git clone https://github.com/pittmanxcode/account-value-repos.git
cd account-value-repos
make setup PYTHON=python3        # needs Python 3.12+ and npm; installs exceljs under tmp/
.venv/bin/account-value doctor   # "python 3.12" FAILs on 3.14; that line is cosmetic, tests pass
```

- `gh auth login` as `pittmanxcode` if you will open PRs (`gh auth switch --user pittmanxcode`
  if another account is active). Publication additionally needs `ACCOUNT_VALUE_GITHUB_TOKEN`
  in the environment; see `docs/OPERATIONS.md`. Dry runs need neither.
- Claude Code, opened at the repo root. The `account-brief` skill is in `.claude/skills/`
  and is picked up automatically. Web search must be available in the session.
- Node on `PATH` or in `~/.local/bin` (the workbook converter looks there).

## 1. Add or check the account's request file

`requests/<slug>.yaml` is the input. It is tracked in git so any machine can rerun it.

```yaml
company_name: Valon
company_slug: valon
domain: valon.ai
careers_url: https://www.valon.ai/careers
ats: ashby            # greenhouse | lever | ashby | workday | '' (JSON-LD on careers_url)
ats_token: valon      # board slug; for workday, the full careers URL
inherited_components: []
```

Finding the board: open a posting on the company's careers page and read the apply URL's
host (`boards.greenhouse.io/<slug>`, `jobs.lever.co/<slug>`, `jobs.ashbyhq.com/<slug>`,
`<tenant>.wd<N>.myworkdayjobs.com/<site>`). Aggregator boards (Built In, Wellfound) show
the same host on their Apply button when the careers page blocks fetches.

## 2. Run the pipeline (dry run)

```bash
.venv/bin/account-value run --request requests/<slug>.yaml --dry-run
```

- Success: `dry run: package ready at accounts/<slug>` and
  `accounts/<slug>/validation-report.txt` starts with `ALL VALIDATIONS PASSED`.
- Failure: a report under `failures/<slug>-<timestamp>.md` says which stage failed.
  Common causes: wrong `ats_token`; a Workday tenant that moved hosts (try the next
  `wd<N>`); a careers page that blocks fetches (set `ats`/`ats_token` explicitly).
- The pipeline tries the configured collector first and falls back to the Workday
  reader only if the careers URL is a Workday host. The notes in
  `accounts/<slug>/account-value.json` say which path ran.

## 3. Gather the brief context

```bash
.venv/bin/account-value brief-context <slug>
```

Writes `accounts/<slug>/brief-context.md`: pipeline numbers, every role with pay source
and saved hours, the engineering-only split, figures quoted in postings, technology
mentions, and every posting verbatim. Large boards produce large files (Reddit: 7,500
lines); that is expected.

## 4. Write the brief

In Claude Code at the repo root, after reviewing step 3's output:

```
/account-brief <slug>
```

The skill reads `docs/ACCOUNT_BRIEF_METHOD.md`, the context file, the study sheet under
`docs/reference/`, and does its own web research. It writes
`accounts/<slug>/<slug>_account-brief.md` and ends with a self-check. Rules it is held to:

- one account per run, started only on an explicit "approved";
- pains are burdens someone at the account carries, never company metrics;
- every number labelled; unknowns stay unknown;
- no outreach copy, no competitive positioning;
- under 1,200 words excluding the Droids and Sources tables.

Review the brief. Send corrections back in the same session; they go into the file, and
anything that is a rule rather than a one-off goes into the method doc.

## 5. Copy to Google Drive

Two files per account, both already named to coexist in one folder:

- `accounts/<slug>/outputs/<Company> × Factory Value.xlsx`
- `accounts/<slug>/<slug>_account-brief.md`

`accounts/` is gitignored on purpose (raw snapshots and workbooks are large and are
published through PRs, not commits). The brief file lives only on the machine that wrote
it until you copy it, so copy it the same day.

## 6. Batch order

When working through many accounts, the standing order is total pipeline saved hours,
descending, with engineering role count as the tiebreak. Compute it with:

```bash
.venv/bin/python - <<'EOF'
import csv; from pathlib import Path
rows=[]
for p in sorted(Path("accounts").iterdir()):
    f=p/"data/processed/role_summary.csv"
    if not f.exists(): continue
    r=list(csv.DictReader(f.open())); e=[x for x in r if x["occupation_soc"].startswith("15-")]
    rows.append((p.name,len(r),round(sum(float(x["saved_hours_base"]) for x in r)),len(e)))
for a in sorted(rows,key=lambda r:(-r[2],-r[3])): print(f"{a[0]:<22}{a[1]:>5} postings {a[2]:>8,} h  {a[3]:>3} eng")
EOF
```

## Known gaps (deferred)

- Workday posted pay is not parsed (BLS fallback); Greenhouse postings that print pay as
  "The base pay for this role is: $X - $Y" are also missed.
- Postings listed once per location inflate the pipeline's hours (DigitalOcean: 122
  engineering rows, 69 distinct titles). The brief flags it; the model doesn't dedupe.
- Some real engineering postings are excluded as "no parseable responsibilities"
  (DigitalOcean product security ×7, Clio ×29). The brief reads them from the raw snapshot.
- A Nimble-based fetch is the next fallback after Workday but is not built; it needs its
  own approval as a new dependency.
