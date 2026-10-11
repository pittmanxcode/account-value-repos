"""Workbook spec generation + ExcelJS conversion.

Builds the standard 10-sheet `{Company} × Factory Value.xlsx` from the
processed model, with the Executive Summary expanded to separate inherited
compelling-event value, job-board capacity value, overlap decisions, and the
supported combined total. Conversion runs Node + ExcelJS (installed under
tmp/), reading a validated JSON spec.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from account_value.pay import ANNUAL_HOURS, LOADED_FACTOR

HDR = {"bold": True, "fill": "#1F2937", "color": "#FFFFFF", "align": "left"}
MONEY = "$#,##0"
ROOT = Path(__file__).resolve().parents[2]

SHEET_ORDER = [
    "Executive Summary", "Ranked Responsibilities", "Bespoke Opportunities",
    "Role Summary", "Jobs", "Responsibility Catalogue", "Compensation",
    "Time Benchmarks", "Sources", "Methodology",
]

EXPLAIN = {
    "Executive Summary": "This page gives the headline: inherited compelling-event value, job-board capacity value, overlap decisions, and the supported combined total.",
    "Ranked Responsibilities": "This page ranks every type of responsibility (cluster) by how well Factory fits it and how many portfolio hours it could save each year.",
    "Bespoke Opportunities": "This page lists only the work where a specific custom integration (named build) would raise Factory's fit beyond the normal setup.",
    "Role Summary": "This page ranks every analyzed posting from best to least fit for Factory, with pay basis and saved hours per role.",
    "Jobs": "This page is the raw posting catalogue: every job captured from the account's board, with its URL and any posted pay range.",
    "Responsibility Catalogue": "This page lists every verbatim responsibility statement extracted from the postings, each mapped to a normalized cluster (noise rows flagged).",
    "Compensation": "This page shows the US-equivalent pay basis used for each occupation and seniority combination, including the loaded-cost view.",
    "Time Benchmarks": "This page lists every time-use and productivity benchmark behind the model, with its source, so the scenario math can be checked.",
    "Sources": "This page cites every data source with its URL and what it was used for.",
    "Methodology": "This page condenses the scoring rubric and value-model method; full detail lives in the account's methodology files.",
}


def _hdr_row(cols: list[str]) -> list[dict]:
    return [{"value": c, **HDR} for c in cols]


def build_spec(
    company: str,
    model: dict[str, list[dict]],
    jobs: list[dict],
    inherited_components: list[dict],
    jobboard_components: list[dict],
    reconciliation: dict,
    snapshot_date: str,
    wage_table_source: str,
    open_unknowns: list[str],
) -> dict:
    roles = model["roles"]
    rank = model["clusters"]
    normalized = model["normalized"]

    total_hours = sum(float(r["role_hours_annual"]) for r in roles) or 1.0
    scenario_totals = {
        s: sum(float(r[f"saved_hours_{s}"]) for r in roles)
        for s in ("conservative", "base", "upside")
    }
    base_value = sum(float(r["saved_value_base"]) for r in roles)

    exec_rows: list[list] = [[f"{company} × Factory Value", ""]]
    exec_rows.append(["Snapshot", snapshot_date])
    exec_rows.append([
        "Basis",
        "Normal Factory setup with human review · US-equivalent pay · "
        f"{ANNUAL_HOURS:,} h/FTE-year · one FTE per open posting",
    ])

    # Inherited compelling-event value (verbatim, preserved from intake/well).
    exec_rows += [[""], [_hdr_row(["Inherited compelling-event value"])[0]]]
    if inherited_components:
        exec_rows.append(_hdr_row(["Component", "Event / signal", "Units", "Saved h/yr", "Hard cost", "Confidence"]))
        for component in inherited_components:
            exec_rows.append([
                component["description"][:120],
                component.get("signal_id") or component.get("work_surface", ""),
                float(component["units"]) if component.get("units") else "",
                float(component["saved_hours_annual"]) if component.get("saved_hours_annual") else "",
                {"value": float(component["hard_cost_usd"]), "numFmt": MONEY} if component.get("hard_cost_usd") else "",
                component.get("confidence", ""),
            ])
    else:
        exec_rows.append(["(no inherited compelling-event value supplied)", ""])

    # Job-board capacity value.
    exec_rows += [[""], [_hdr_row(["Job-board capacity value (this analysis)"])[0]]]
    exec_rows.append(_hdr_row(["Scenario", "Saved hours/yr", "Saved role-days", "FTE equiv.", "% capacity freed", "Salary-equiv value", f"Loaded (×{LOADED_FACTOR:.2f})"]))
    for scenario, label in (("conservative", "Conservative"), ("base", "Base"), ("upside", "Upside")):
        hours = scenario_totals[scenario]
        exec_rows.append([
            label, round(hours), round(hours / 8), round(hours / ANNUAL_HOURS, 1),
            round(100 * hours / total_hours, 1),
            {"value": round(base_value * hours / scenario_totals["base"]) if scenario_totals["base"] else 0, "numFmt": MONEY},
            {"value": round(base_value * hours / scenario_totals["base"] * LOADED_FACTOR) if scenario_totals["base"] else 0, "numFmt": MONEY},
        ])

    # Reconciliation / combined total.
    exec_rows += [[""], [_hdr_row(["Reconciled account value"])[0]]]
    if reconciliation.get("combined_blocked_reason"):
        exec_rows.append(["Combined total", f"NOT CLAIMED — {reconciliation['combined_blocked_reason']}"])
    else:
        combined_hours = reconciliation.get("combined_saved_hours_annual")
        combined_cost = reconciliation.get("combined_hard_cost_usd")
        exec_rows.append([
            "Combined saved hours/yr (inherited + job-board, overlap-checked)",
            float(combined_hours) if combined_hours is not None else "not established",
        ])
        exec_rows.append([
            "Combined hard-cost value",
            {"value": float(combined_cost), "numFmt": MONEY} if combined_cost is not None else "unknown, where looked",
        ])
    for decision in reconciliation.get("decisions", []):
        exec_rows.append([
            f"overlap: {decision['component_id']}",
            f"{decision['outcome']} — {decision['reason']}",
        ])
    for unknown in open_unknowns:
        exec_rows.append(["Open unknown", unknown])

    exec_rows += [[""], ["Method", "See Methodology sheet and the account's methodology files"]]

    # Ranked Responsibilities.
    rk = [_hdr_row(["Cluster", "Fit (normal)", "Fit (bespoke)", "Bespoke build", "Addressable share",
                    "Time basis", "Evidence confidence", "Portfolio hours", "Saved h (base)", "Bullets"])]
    for row in rank:
        rk.append([row["cluster_label"], int(row["fit_normal"]), int(row["fit_bespoke"]),
                   row["bespoke_build"], float(row["addressable_share"]), row["time_basis"],
                   row["evidence_confidence"], float(row["portfolio_hours"]),
                   float(row["portfolio_saved_hours_base"]), int(row["bullet_count"])])

    # Bespoke Opportunities.
    bs = [_hdr_row(["Cluster", "Fit (normal)", "Fit (bespoke)", "Required build", "Time basis"])]
    for row in sorted(rank, key=lambda r: int(r["fit_bespoke"]) - int(r["fit_normal"]), reverse=True):
        if int(row["fit_bespoke"]) > int(row["fit_normal"]):
            bs.append([row["cluster_label"], int(row["fit_normal"]), int(row["fit_bespoke"]),
                       row["bespoke_build"], row["time_basis"]])

    # Role Summary.
    rs = [_hdr_row(["Title", "Department", "Location", "Occupation (SOC)", "Seniority", "Pay source",
                    "US-equiv base pay", "Hourly equiv", "Saved h (cons)", "Saved h (base)",
                    "Saved h (upside)", "% freed (base)"])]
    for row in sorted(roles, key=lambda r: -float(r["saved_hours_base"])):
        rs.append([row["title"], row["department"], row["location"],
                   f"{row['occupation']} ({row['occupation_soc']})" if row["occupation_soc"] else row["occupation"],
                   row["seniority"], row["pay_source"],
                   {"value": int(row["us_equiv_base_pay"]), "numFmt": MONEY},
                   {"value": float(row["hourly_equiv"]), "numFmt": "$#,##0.00"},
                   float(row["saved_hours_conservative"]), float(row["saved_hours_base"]),
                   float(row["saved_hours_upside"]), float(row["pct_capacity_freed_base"])])

    # Jobs.
    jb = [_hdr_row(["Job ID", "Title", "Department", "Location", "Published", "URL", "Posted pay range"])]
    for job in jobs:
        jb.append([job["job_id"], job["title"], job["department"], job["location"],
                   job.get("first_published", ""), job.get("url", ""),
                   f"${job['pay_min_posted']}-${job['pay_max_posted']}" if job.get("pay_min_posted") else ""])

    # Responsibility Catalogue.
    rc = [_hdr_row(["Job ID", "Title", "Department", "Section", "Verbatim responsibility",
                    "Cluster", "Noise flag"])]
    for row in normalized:
        rc.append([row["job_id"], row["title"], row["department"], row["section"],
                   row["verbatim_responsibility"], row["cluster"], row["is_noise"]])

    # Compensation.
    from collections import Counter

    combo = Counter((r["occupation"], r["occupation_soc"], r["seniority"]) for r in roles)
    cm = [_hdr_row(["Occupation (SOC)", "Seniority", "US-equiv base pay", "Hourly equiv",
                    f"Loaded hourly (×{LOADED_FACTOR:.2f})", "Roles"])]
    for (occ, soc, level), count in sorted(combo.items(), key=lambda kv: -kv[1]):
        sample = next(r for r in roles if r["occupation"] == occ and r["seniority"] == level)
        cm.append([f"{occ} ({soc})" if soc else occ, level,
                   {"value": int(sample["us_equiv_base_pay"]), "numFmt": MONEY},
                   {"value": float(sample["hourly_equiv"]), "numFmt": "$#,##0.00"},
                   {"value": float(sample["loaded_hourly_equiv"]), "numFmt": "$#,##0.00"}, count])

    # Time Benchmarks / Sources / Methodology.
    tb = [
        _hdr_row(["Benchmark", "Value", "Used for", "Source"]),
        ["Productive hours per FTE-year", ANNUAL_HOURS, "Annual hour normalization", "Assumption (40 h × 48 weeks), editable"],
        ["Gen-AI software engineering uplift", "20-45% by activity", "Scenario acceleration anchor", "McKinsey 2023; Bain 2025"],
        ["Frequent AI users saving 4+ h/week", "20.5% of users", "Realized savings plausibility", "ITIF 2025"],
        ["Fully loaded cost factor", LOADED_FACTOR, "Loaded-cost view", "Standard benefits/payroll-tax loading assumption"],
        ["Adoption rates", "50% / 75% / 90%", "Conservative / base / upside", "Decision assumption, editable"],
        ["Wage data", "BLS OEWS May 2025 medians", "US-equivalent pay", wage_table_source],
    ]
    so = [
        _hdr_row(["#", "Source", "URL / location", "Use"]),
        [1, "Careers board snapshot", "data/raw/ (snapshot hash in account-value.json)", "Posting inventory and verbatim responsibilities"],
        [2, "BLS OEWS May 2025 national medians", "https://www.bls.gov/news.release/ocwage.t01.htm", "Occupation wage benchmarks (via O*NET)"],
        [3, "Evidence records", "component evidence + snapshot hashes", "Compelling events and identity"],
    ]
    me = [
        _hdr_row(["Topic", "Detail"]),
        ["Fit rubric weights", "Digital executability 25 · Factory workflow match 25 · Input/system access 15 · Output verifiability 15 · Professional quality with human review 15 · Risk/governance 5"],
        ["Normal setup", "Repo/document access, approved connectors, terminal/browser tools, Missions, automations, human approval"],
        ["Bespoke score", "Adds a named, concrete integration build with human checkpoint; never treated as already available"],
        ["Pay basis", "Posted ranges first (HTML block or posting text; non-USD converted at the dated rates in registry/fx_rates.yaml, noted per row), else BLS OEWS May 2025 median × seniority factor"],
        ["Hours", f"{ANNUAL_HOURS:,} per FTE-year; allocated across clusters in proportion to responsibility bullets"],
        ["Saved hours formula", "role_hours × addressable_share × net_time_reduction × adoption × fit_confidence"],
        ["Inherited value", "Preserved verbatim from intake/the well; combined totals require overlap reconciliation"],
        ["Aggregation caveat", "One FTE per open posting; totals are open-req equivalents, not company-wide payroll savings"],
    ]

    sheets = []
    sheet_rows = {
        "Executive Summary": exec_rows,
        "Ranked Responsibilities": rk,
        "Bespoke Opportunities": bs,
        "Role Summary": rs,
        "Jobs": jb,
        "Responsibility Catalogue": rc,
        "Compensation": cm,
        "Time Benchmarks": tb,
        "Sources": so,
        "Methodology": me,
    }
    widths = {
        "Executive Summary": [46, 20, 14, 14, 16, 18, 18],
        "Ranked Responsibilities": [42, 12, 13, 46, 14, 30, 15, 14, 14, 9],
        "Bespoke Opportunities": [42, 12, 13, 62, 30],
        "Role Summary": [46, 26, 30, 40, 10, 30, 14, 12, 14, 14, 14, 12],
        "Jobs": [10, 50, 28, 34, 12, 60, 24],
        "Responsibility Catalogue": [10, 42, 26, 24, 100, 22, 10],
        "Compensation": [44, 10, 15, 12, 16, 8],
        "Time Benchmarks": [34, 20, 34, 48],
        "Sources": [5, 40, 70, 40],
        "Methodology": [22, 120],
    }
    for name in SHEET_ORDER:
        rows = sheet_rows[name]
        if name != "Executive Summary":
            rows = [[EXPLAIN[name]], [""]] + rows
        sheets.append({
            "name": name,
            "rows": rows,
            "columns": [{"width": w} for w in widths[name]],
            "freezeRows": 0 if name == "Executive Summary" else 1,
        })
    return {"sheets": sheets}


def convert(spec_path: Path, out_path: Path, project_root: Path | None = None) -> Path:
    """Convert a JSON spec to xlsx via Node + ExcelJS (module path under tmp/)."""
    root = project_root or ROOT
    script = Path(__file__).parent / "wb_convert.js"
    result = subprocess.run(
        [shutil.which("node") or "node", str(script), str(spec_path), str(out_path)],
        cwd=root, capture_output=True, text=True, timeout=120,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(Path.home())},
    )
    if result.returncode != 0:
        raise RuntimeError(f"workbook conversion failed: {result.stderr[-500:]}")
    return out_path


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
