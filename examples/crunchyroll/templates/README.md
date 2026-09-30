# Reusable Kit — Rerun for Any Account

This folder is the export of the full prompt system used for the Crunchyroll
build, parameterized so it can be rerun for any company.

## Quickstart for a new account

1. Create a new repo: `/repos/{{company_slug}}-value-repository/` with the
   same folder skeleton (`data/raw`, `data/processed`, `methodology`,
   `scripts`, `outputs`, `tmp`).
2. Open `templates/PROMPT.md`, replace every `{{PLACEHOLDER}}` (company name,
   careers URL, board API, assumptions), and run the prompt top to bottom.
3. Fill `config.example.json` → `config.json` for the account record.
4. Copy the Crunchyroll `scripts/` as the starting point. The analyst-judgment
   parts you must refresh per account:
   - cluster taxonomy regexes (`CLUSTERS` in `02_build_value_model.py`) —
     tune on a department-wide sample of the new account's bullets
   - title → occupation mapping (`TITLE_MAP`) — one row per new-account title
   - the phrasing of the exec summary and page explainers in
     `04_make_workbook_spec.py`
5. Run the pipeline in order and do not deliver until the Phase 7 validation
   gate passes.

## Files

| File | Purpose |
|---|---|
| `PROMPT.md` | The full rerunnable prompt system (phases 0–7) |
| `config.example.json` | Account parameters and locked assumptions |
