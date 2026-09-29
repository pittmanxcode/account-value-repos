# Crunchyroll × Factory Value Repository

A timestamped, auditable account-value analysis of Crunchyroll's open job
board: what every posting's responsibilities are, how well Factory (Droid,
Missions, automations) could perform them at experienced-professional quality,
and what capacity that would free.

**Snapshot date:** September 29, 2026 · **Postings captured:** 77 of 77
(exact reconciliation with the live board) · **Verbatim responsibilities:**
964 bullets across 30 normalized clusters.

## Headline (base scenario, normal setup, human review)

- **18,695 hours/year** of capacity freed across 77 posting-equivalents
  (12.6% of the 147,840-hour portfolio) ≈ **9.7 FTE** or 2,337 role-days.
- **Conservative / base / upside:** 8,000 / 18,695 / 30,830 hours.
- **Salary-equivalent value (base):** ≈ $1.52M USD ($1.98M fully loaded at
  1.30), using US-equivalent pay for all locations per approved assumption.
  33 US postings use Crunchyroll's posted ranges; the rest use BLS OEWS
  May 2025 medians by occupation and seniority.
- Best-fit work: software development, analytics, QA, accounting operations,
  data engineering. Least-fit: physical supply chain, workplace/facilities,
  partnership and legal sign-off, tax/SOX filing authority.
- Bespoke integrations (named builds only) add roughly **+12%** beyond the
  normal-setup baseline.

## Navigation

| Path | Contents |
|---|---|
| `REPORT.md` | Executive findings, rankings, and recommendations |
| `outputs/crunchyroll_factory_value_repository.xlsx` | Polished workbook (10 sheets) |
| `data/raw/` | Source snapshots (Greenhouse API JSON, O*NET wage harvest) |
| `data/processed/jobs.csv` | Full posting catalogue |
| `data/processed/responsibilities.csv` | 964 verbatim responsibility bullets |
| `data/processed/responsibilities_normalized.csv` | Bullets mapped to taxonomy clusters |
| `data/processed/scored_responsibilities.csv` | Job × cluster fit, hours, pay, scenarios |
| `data/processed/role_summary.csv` | Per-role ranking and value |
| `data/processed/cluster_ranking.csv` | Cluster-level portfolio ranking |
| `methodology/` | Rubric, pay/time method, sources |
| `scripts/` | Repeatable pipeline (01 parse → 02 model → 03 validate → 04 spec → 05 convert) |
| `templates/` | Reusable prompt-system export for rerunning on any account |

## Reproduce

```bash
python3 scripts/01_parse_postings.py     # rebuild catalogue from raw snapshot
python3 scripts/02_build_value_model.py  # rebuild scoring and value model
python3 scripts/03_validate.py           # run the 20-check validation gate
```

Re-collection: `curl "https://boards-api.greenhouse.io/v1/boards/crunchyroll/jobs?content=true" -o data/raw/greenhouse_board_snapshot.json`

## Limitations

- One FTE assumed per open posting; public data does not reveal headcount.
- Time allocation is bullet-proportional, not a measured time study.
- Non-US postings valued at hypothetical US-equivalent pay (per approved
  decision), not local compensation.
- Scenario parameters are documented assumptions anchored to cited
  benchmarks; all are editable constants in `scripts/02_build_value_model.py`.
- The job board is dynamic; figures reflect the September 29, 2026 snapshot.
