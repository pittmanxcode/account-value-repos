#!/usr/bin/env python3
"""Generate tmp/crunchyroll_value_repository.xlsx.json workbook spec."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "data" / "processed"
OUT = ROOT / "tmp" / "crunchyroll_value_repository.xlsx.json"

HDR = {"bold": True, "fill": "#1F2937", "color": "#FFFFFF", "align": "left"}
MONEY = "$#,##0"
H1 = "{:,}".format

def sheet(name, rows, widths=None, freeze=1):
    return {"name": name, "rows": rows, "columns": [{"width": w} for w in (widths or [])],
            "freezeRows": freeze}

def read(name):
    with (P / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))

roles = read("role_summary.csv")
rank = read("cluster_ranking.csv")
scored = read("scored_responsibilities.csv")
jobs = read("jobs.csv")
norm = read("responsibilities_normalized.csv")

H = 1920 * len(roles)
tots = {s: sum(float(r[f"saved_hours_{s}"]) for r in roles) for s in
        ("conservative", "base", "upside")}
base_val = sum(float(r["saved_value_base"]) for r in roles)
bespoke_base = sum(float(s["saved_hours_base"]) * (int(s["fit_bespoke"]) / int(s["fit_normal"]))
                   for s in scored if int(s["fit_bespoke"]) > int(s["fit_normal"]))

def hdr_row(cols):
    return [{ "value": c, **HDR} for c in cols]

# Plain-text executive summary (no tables, reads as a paragraph).
PLAIN_SUMMARY = [
    "PLAIN-TEXT SUMMARY — Factory, running a normal setup with a human reviewing its work, could take over",
    f"responsibilities worth about {round(tots['base']):,} hours per year across the 77 open roles analyzed. That is",
    f"{100*tots['base']/H:.1f}% of the total capacity those roles represent, roughly the workload of {tots['base']/1920:.1f} full-time",
    "people, and worth about $1.52M in salary-equivalent terms ($1.98M with benefits and overhead loaded in).",
    f"A cautious rollout gets about {round(tots['conservative']):,} hours; a well-adopted one up to {round(tots['upside']):,} hours.",
    "The strongest fits are engineering work (code review, testing, pipelines), analytics and reporting, and",
    "high-volume finance operations like invoice processing. The weakest fits are physical work, relationship",
    "and negotiation-heavy roles, and anything requiring legal, tax, or executive sign-off — there, agents work",
    "best as drafting and research assistants behind a professional reviewer. Integrations built specifically",
    "for internal systems (ERP, helpdesk, translation management) add roughly 12% more. Values use US-equivalent",
    "pay for every location and treat each open posting as one full-time person, so read totals as open-role",
    "opportunity, not company-wide payroll savings.",
]

# One-sentence explainer shown at the top of every page.
EXPLAIN = {
    "Executive Summary": "This page gives the headline: how many hours Factory could free across all analyzed roles, under three scenarios, and which work fits best.",
    "Ranked Responsibilities": "This page ranks every type of responsibility (cluster) by how well Factory fits it and how many portfolio hours it could save each year.",
    "Bespoke Opportunities": "This page lists only the work where a specific custom integration (named build) would raise Factory's fit beyond the normal setup.",
    "Role Summary": "This page ranks all 77 job postings from best to least fit for Factory, with pay basis and saved hours per role.",
    "Jobs": "This page is the raw posting catalogue: every job captured from Crunchyroll's board, with its URL and any posted pay range.",
    "Responsibility Catalogue": "This page lists all 964 verbatim responsibility statements extracted from the postings, each mapped to a normalized cluster (noise rows flagged).",
    "Compensation": "This page shows the US-equivalent pay basis used for each occupation and seniority combination, including the loaded-cost view.",
    "Time Benchmarks": "This page lists every time-use and productivity benchmark behind the model, with its source, so the scenario math can be checked.",
    "Sources": "This page cites every data source with its URL and what it was used for.",
    "Methodology": "This page condenses the scoring rubric and value-model method; the full detail lives in the methodology/ folder of the repository.",
}

# --- Executive Summary -----------------------------------------------------
exec_rows = [
    ["Crunchyroll × Factory Value Repository", ""],
    ["Snapshot", "September 29, 2026 · 77 postings · 964 verbatim responsibilities · 30 clusters"],
    ["Basis", "Normal Factory setup with human review · US-equivalent pay · 1,920 h/FTE-year · one FTE per open posting"],
    [""],
] + [[line] for line in PLAIN_SUMMARY] + [
    [""],
    hdr_row(["Scenario", "Saved hours/yr", "Saved role-days", "FTE equiv.", "% capacity freed", "Salary-equiv value", "Loaded (×1.30)"]),
    ["Conservative", round(tots["conservative"]), round(tots["conservative"]/8), round(tots["conservative"]/1920, 1),
     round(100*tots["conservative"]/H, 1), {"value": round(base_val*tots["conservative"]/tots["base"]), "numFmt": MONEY},
     {"value": round(base_val*tots["conservative"]/tots["base"]*1.3), "numFmt": MONEY}],
    ["Base", round(tots["base"]), round(tots["base"]/8), round(tots["base"]/1920, 1),
     round(100*tots["base"]/H, 1), {"value": round(base_val), "numFmt": MONEY},
     {"value": round(base_val*1.3), "numFmt": MONEY}],
    ["Upside", round(tots["upside"]), round(tots["upside"]/8), round(tots["upside"]/1920, 1),
     round(100*tots["upside"]/H, 1), {"value": round(base_val*tots["upside"]/tots["base"]), "numFmt": MONEY},
     {"value": round(base_val*tots["upside"]/tots["base"]*1.3), "numFmt": MONEY}],
    [""],
    [f"Bespoke-enabled base (named builds only)", f"≈ {round(bespoke_base):,} h (+{100*(bespoke_base/tots['base']-1):.0f}% vs normal-setup base)"],
    [""],
    ["Top clusters by saved hours (base)"],
]
top_rank = sorted(rank, key=lambda r: -float(r["portfolio_saved_hours_base"]))[:10]
exec_rows.append(hdr_row(["Cluster", "Fit (normal)", "Fit (bespoke)", "Portfolio hours", "Saved h (base)"]))
for r in top_rank:
    exec_rows.append([r["cluster_label"], int(r["fit_normal"]), int(r["fit_bespoke"]),
                      float(r["portfolio_hours"]), float(r["portfolio_saved_hours_base"])])
exec_rows += [
    [""],
    ["Method", "See Methodology sheet; full detail in methodology/ and REPORT.md"],
    ["Caveats", "One FTE per open posting; bullet-proportional time allocation; non-US roles valued at hypothetical US-equivalent pay"],
]

# --- Ranked Responsibilities (clusters) -------------------------------------
rk = [hdr_row(["Cluster", "Fit (normal)", "Fit (bespoke)", "Bespoke build", "Addressable share",
               "Time basis", "Evidence confidence", "Portfolio hours", "Saved h (base)", "Bullets"])]
for r in rank:
    rk.append([r["cluster_label"], int(r["fit_normal"]), int(r["fit_bespoke"]), r["bespoke_build"],
               float(r["addressable_share"]), r["time_basis"], r["evidence_confidence"],
               float(r["portfolio_hours"]), float(r["portfolio_saved_hours_base"]), int(r["bullet_count"])])
rk.append([{"value": "TOTAL", "bold": True}, "", "", "", "", "", "",
           {"value": round(sum(float(r["portfolio_hours"]) for r in rank)), "bold": True},
           {"value": round(tots["base"]), "bold": True},
           {"value": sum(int(r["bullet_count"]) for r in rank), "bold": True}])

# --- Bespoke Opportunities --------------------------------------------------
bs = [hdr_row(["Cluster", "Fit (normal)", "Fit (bespoke)", "Required build", "Time basis"])]
for r in sorted(rank, key=lambda r: int(r["fit_bespoke"]) - int(r["fit_normal"]), reverse=True):
    if int(r["fit_bespoke"]) > int(r["fit_normal"]):
        bs.append([r["cluster_label"], int(r["fit_normal"]), int(r["fit_bespoke"]),
                   r["bespoke_build"], r["time_basis"]])

# --- Role Summary ------------------------------------------------------------
rs = [hdr_row(["Title", "Department", "Location", "Occupation (SOC)", "Seniority", "Pay source",
               "US-equiv base pay", "Hourly equiv", "Saved h (cons)", "Saved h (base)",
               "Saved h (upside)", "% freed (base)"])]
for r in sorted(roles, key=lambda r: -float(r["saved_hours_base"])):
    rs.append([r["title"], r["department"], r["location"],
               f"{r['occupation']} ({r['occupation_soc']})", r["seniority"], r["pay_source"],
               {"value": int(r["us_equiv_base_pay"]), "numFmt": MONEY},
               {"value": float(r["hourly_equiv"]), "numFmt": "$#,##0.00"},
               float(r["saved_hours_conservative"]), float(r["saved_hours_base"]),
               float(r["saved_hours_upside"]), float(r["pct_capacity_freed_base"])])

# --- Jobs ---------------------------------------------------------------------
jb = [hdr_row(["Job ID", "Title", "Department", "Location", "Published", "URL",
               "Posted pay range"])]
for j in jobs:
    pr = f"${j['pay_min_posted']}-${j['pay_max_posted']}" if j["pay_min_posted"] else ""
    jb.append([j["job_id"], j["title"], j["department"], j["location"], j["first_published"],
               j["url"], pr])

# --- Responsibility Catalogue (964) ------------------------------------------
rc = [hdr_row(["Job ID", "Title", "Department", "Section", "Verbatim responsibility",
               "Cluster", "Noise flag"])]
for r in norm:
    rc.append([r["job_id"], r["title"], r["department"], r["section"],
               r["verbatim_responsibility"], r["cluster"], r["is_noise"]])

# --- Compensation --------------------------------------------------------------
cm = [hdr_row(["Occupation (SOC)", "Seniority", "US-equiv base pay", "Hourly equiv",
               "Loaded hourly (×1.30)", "Roles"])]
from collections import Counter
combo = Counter((r["occupation"], r["occupation_soc"], r["seniority"]) for r in roles)
for (occ, soc, lvl), n in sorted(combo.items(), key=lambda kv: -kv[1]):
    r0 = next(r for r in roles if r["occupation_soc"] == soc and r["seniority"] == lvl)
    cm.append([f"{occ} ({soc})", lvl, {"value": int(r0["us_equiv_base_pay"]), "numFmt": MONEY},
               {"value": float(r0["hourly_equiv"]), "numFmt": "$#,##0.00"},
               {"value": float(r0["loaded_hourly_equiv"]), "numFmt": "$#,##0.00"}, n])

# --- Time Benchmarks ------------------------------------------------------------
tb = [
    hdr_row(["Benchmark", "Value", "Used for", "Source"]),
    ["Productive hours per FTE-year", 1920, "Annual hour normalization", "Assumption (40 h × 48 weeks), editable"],
    ["Developers: coding per day", "3.2 h", "Software development time basis", "pandev-metrics 2026 IDE telemetry"],
    ["Developers: debugging per day", "1.8 h", "Software development time basis", "pandev-metrics 2026 IDE telemetry"],
    ["Developers: meetings per day", "2.5 h", "Collaboration/generalist basis", "pandev-metrics 2026 IDE telemetry"],
    ["Gen-AI software engineering uplift", "20-45% by activity", "Scenario acceleration anchor", "McKinsey 2023; Bain 2025"],
    ["Frequent AI users saving 4+ h/week", "20.5% of users", "Realized savings plausibility", "ITIF 2025"],
    ["Fully loaded cost factor", 1.30, "Loaded-cost view", "Standard benefits/payroll-tax loading assumption"],
    ["Adoption rates", "50% / 75% / 90%", "Conservative / base / upside", "Decision assumption, editable"],
    ["Wage data", "BLS OEWS May 2025 medians", "US-equivalent pay", "bls.gov (via O*NET), harvested 2026-09-29"],
]

# --- Sources -----------------------------------------------------------------------
so = [
    hdr_row(["#", "Source", "URL / location", "Use"]),
    [1, "Crunchyroll job board", "https://www.crunchyroll.com/about/jobs", "Posting inventory"],
    [2, "Greenhouse public board API (raw snapshot)", "https://boards-api.greenhouse.io/v1/boards/crunchyroll/jobs?content=true", "Full descriptions, verbatim responsibilities"],
    [3, "BLS OEWS May 2025 national medians", "https://www.bls.gov/news.release/ocwage.t01.htm", "Occupation wage benchmarks"],
    [4, "O*NET OnLine wage harvest", "data/raw/onet_wages_2025.txt", "BLS wage data via O*NET for 30 SOC codes"],
    [5, "pandev-metrics 2026", "https://pandev-metrics.com/docs/blog/how-much-developers-actually-code", "Developer time-use telemetry"],
    [6, "McKinsey (2023) gen-AI economic potential", "https://www.mckinsey.com/capabilities/tech-and-ai/our-insights/the-economic-potential-of-generative-ai-the-next-productivity-frontier", "Scenario acceleration anchors"],
    [7, "Bain (2025) gen-AI in software development", "https://www.bain.com/insights/from-pilots-to-payoff-generative-ai-in-software-development/", "Acceleration with process change"],
    [8, "ITIF (2025) AI time-savings survey", "https://itif.org/publications/2025/05/09/frequent-generative-ai-users-report-significant-time-savings/", "Realized savings evidence"],
    [9, "O*NET work activities", "https://www.onetonline.org/", "Cluster time-basis structure"],
    [10, "Factory documentation", "https://docs.factory.ai/llms.txt", "Normal-setup capability boundary"],
]

# --- Methodology -----------------------------------------------------------------------
me = [
    hdr_row(["Topic", "Detail"]),
    ["Fit rubric weights", "Digital executability 25 · Factory workflow match 25 · Input/system access 15 · Output verifiability 15 · Professional quality with human review 15 · Risk/governance 5"],
    ["Normal setup", "Repo/document access, approved connectors, terminal/browser tools, Missions, automations, human approval"],
    ["Bespoke score", "Adds a named, concrete integration build with human checkpoint; never treated as already available"],
    ["Hard penalties", "Unavailable systems, physical work, relationship ownership, executive judgment, negotiation, people management, taste-led decisions, legal/security/tax sign-off"],
    ["Pay basis", "US-equivalent per approved decision: posted US ranges first, else BLS OEWS May 2025 median × seniority factor (entry .80 / mid .90 / senior 1.10 / lead 1.25 / staff 1.50 / mgr 1.35 / dir 1.60 / exec 2.00)"],
    ["Loaded cost", "Base × 1.30 (benefits, payroll taxes, overhead)"],
    ["Hours", "1,920 per FTE-year; allocated across clusters in proportion to responsibility bullets"],
    ["Saved hours formula", "role_hours × addressable_share × net_time_reduction × adoption × fit_confidence"],
    ["Bespoke reporting", "Reported separately from baseline; uplift only where a named build exists"],
    ["Aggregation caveat", "One FTE per open posting; totals are open-req equivalents, not company-wide payroll savings"],
]

spec = {"sheets": []}
for _name, _rows, _w, _f in [
    ("Executive Summary", exec_rows, [38, 16, 15, 12, 14, 16, 16], 0),
    ("Ranked Responsibilities", rk, [42, 12, 13, 46, 14, 30, 15, 14, 14, 9], 1),
    ("Bespoke Opportunities", bs, [42, 12, 13, 62, 30], 1),
    ("Role Summary", rs, [46, 26, 30, 40, 10, 30, 14, 12, 14, 14, 14, 12], 1),
    ("Jobs", jb, [10, 50, 28, 34, 12, 60, 24], 1),
    ("Responsibility Catalogue", rc, [10, 42, 26, 24, 100, 22, 10], 1),
    ("Compensation", cm, [44, 10, 15, 12, 16, 8], 1),
    ("Time Benchmarks", tb, [34, 20, 34, 48], 1),
    ("Sources", so, [5, 40, 70, 40], 1),
    ("Methodology", me, [22, 120], 1),
]:
    rows = [[EXPLAIN[_name]], [""]] + _rows if _name != "Executive Summary" else _rows
    spec["sheets"].append(sheet(_name, rows, _w, _f))

OUT.write_text(json.dumps(spec, ensure_ascii=False))
print(f"spec written: {OUT} ({OUT.stat().st_size} bytes, {len(spec['sheets'])} sheets)")
