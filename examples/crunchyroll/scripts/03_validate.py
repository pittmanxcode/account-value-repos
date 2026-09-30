#!/usr/bin/env python3
"""Validation gate for the Crunchyroll x Factory value repository.

Checks: catalogue completeness, ID uniqueness, score bounds, 1,920-hour
normalization, scenario monotonicity, saved<=role-hours, pay provenance.
Exits non-zero on any failure.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "data" / "processed"
failures = []

def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        failures.append(name)

jobs = list(csv.DictReader((P / "jobs.csv").open(encoding="utf-8")))
resp = list(csv.DictReader((P / "responsibilities.csv").open(encoding="utf-8")))
norm = list(csv.DictReader((P / "responsibilities_normalized.csv").open(encoding="utf-8")))
scored = list(csv.DictReader((P / "scored_responsibilities.csv").open(encoding="utf-8")))
roles = list(csv.DictReader((P / "role_summary.csv").open(encoding="utf-8")))

print("== Catalogue ==")
check("77 postings collected", len(jobs) == 77, f"n={len(jobs)}")
check("job_id unique", len({j['job_id'] for j in jobs}) == len(jobs))
check("every posting has URL and content", all(j["url"].startswith("http") and int(j["content_chars"]) > 0 for j in jobs))
check("bullet rows = normalized rows", len(resp) == len(norm), f"{len(resp)} vs {len(norm)}")
check("every bullet classified or flagged noise",
      all((r["cluster"] or int(r["is_noise"]) == 1) for r in norm))
check("every job appears in normalized bullets",
      {j["job_id"] for j in jobs} <= {r["job_id"] for r in norm})

print("== Scoring bounds ==")
check("fit_normal within 0-100", all(0 <= int(s["fit_normal"]) <= 100 for s in scored))
check("fit_bespoke within 0-100", all(0 <= int(s["fit_bespoke"]) <= 100 for s in scored))
check("fit_bespoke >= fit_normal (uplift only)",
      all(int(s["fit_bespoke"]) >= int(s["fit_normal"]) for s in scored))
check("addressable share in 0-1", all(0 <= float(s["addressable_share"]) <= 1 for s in scored))
check("every scored row has time basis + source",
      all(s["time_basis"] and s["time_source"] for s in scored))
check("every scored row has evidence confidence",
      all(s["evidence_confidence"] for s in scored))

print("== Hours and scenarios ==")
from collections import defaultdict
hours_by_job = defaultdict(float)
for s in scored:
    hours_by_job[s["job_id"]] += float(s["role_hours_annual"])
check("each role's hours sum to 1,920 (±0.5)",
      all(abs(h - 1920) < 0.5 for h in hours_by_job.values()),
      f"n_roles={len(hours_by_job)}")
bad = [s for s in scored
       if not (float(s["saved_hours_conservative"]) <= float(s["saved_hours_base"])
               <= float(s["saved_hours_upside"]))]
check("scenario monotonicity cons<=base<=upside", not bad)
over = [s for s in scored if float(s["saved_hours_upside"]) > float(s["role_hours_annual"])]
check("saved hours never exceed role-hours", not over)

print("== Pay provenance ==")
check("all roles have US-equivalent pay", all(float(r["us_equiv_base_pay"]) > 0 for r in roles))
check("all roles have occupation mapping", all(r["occupation_soc"] and r["occupation"] for r in roles))
check("hourly = annual / 1,920 (±1%)",
      all(abs(float(r["hourly_equiv"]) - float(r["us_equiv_base_pay"]) / 1920) < 0.01 * float(r["hourly_equiv"]) + 0.02
          for r in roles))
check("loaded hourly > hourly", all(float(r["loaded_hourly_equiv"]) > float(r["hourly_equiv"]) for r in roles))

print("== Portfolio reconciliation ==")
tot_saved = sum(float(r["saved_hours_base"]) for r in roles)
tot_h = sum(float(r["role_hours_annual"]) for r in roles)
check("portfolio saved base <= portfolio hours", tot_saved < tot_h, f"{tot_saved:.0f}/{tot_h:.0f}")
check("77 role summary rows", len(roles) == 77, f"n={len(roles)}")

print()
if failures:
    print(f"VALIDATION FAILED: {len(failures)} check(s): {failures}")
    sys.exit(1)
print("ALL VALIDATIONS PASSED")
