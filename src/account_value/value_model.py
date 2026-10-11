"""Deterministic scenario value model, ported from the golden Crunchyroll build.

Inputs are parsed jobs + verbatim responsibility bullets; outputs are the
same processed-CSV shapes as the fixture (scored responsibilities, role
summary, cluster ranking). All parameters are labeled editable assumptions.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from account_value import TAXONOMY_VERSION
from account_value.pay import ANNUAL_HOURS, LOADED_FACTOR, pay_basis
from account_value.taxonomy import CLUSTER_BY_KEY, classify, noise_pattern

ADOPTION = {"conservative": 0.50, "base": 0.75, "upside": 0.90}


@dataclass
class JobPosting:
    job_id: str
    title: str
    department: str
    location: str
    language: str = ""
    first_published: str = ""
    url: str = ""
    pay_min_posted: int = 0
    pay_max_posted: int = 0
    pay_mid_posted: int = 0
    pay_note: str = ""  # how the posted pay was read: "html block", "text", "text, CAD at …"


@dataclass
class Bullet:
    job_id: str
    title: str
    department: str
    resp_seq: int
    section: str
    verbatim_responsibility: str


def _rows_to_dicts(rows: list[dict]) -> list[dict]:
    return rows


def build_model(
    jobs: list[JobPosting],
    bullets: list[Bullet],
    title_overrides: dict[str, tuple[str, str]] | None = None,
    company_name: str | None = None,
) -> dict[str, list[dict]]:
    """Run the full scoring model; returns {'normalized', 'scored', 'roles', 'clusters'}."""
    noise = noise_pattern(company_name)
    normalized: list[dict] = []
    by_job: dict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    for bullet in bullets:
        is_noise = bool(noise.search(bullet.verbatim_responsibility))
        cluster = "" if is_noise else classify(bullet.verbatim_responsibility)
        if not is_noise:
            by_job[bullet.job_id][cluster] += 1
        normalized.append({
            "job_id": bullet.job_id, "title": bullet.title,
            "department": bullet.department, "resp_seq": bullet.resp_seq,
            "section": bullet.section,
            "verbatim_responsibility": bullet.verbatim_responsibility,
            "cluster": cluster, "is_noise": int(is_noise),
        })

    # Title twins: non-English postings inherit their English twin's cluster
    # distribution (regex taxonomy is English-language).
    titles: dict[str, list[JobPosting]] = defaultdict(list)
    for job in jobs:
        titles[job.title.strip().lower()].append(job)
    twin = {}
    for group in titles.values():
        en = next((j for j in group if j.language in ("", "en")), None)
        for job in group:
            if job.language not in ("", "en") and en is not None and job.job_id != en.job_id:
                twin[job.job_id] = en.job_id

    scored: list[dict] = []
    role_rows: list[dict] = []
    for job in jobs:
        distribution = dict(by_job[twin[job.job_id]]) if job.job_id in twin else dict(by_job[job.job_id])
        total_bullets = sum(distribution.values()) or 1
        basis = pay_basis(job.title, job.pay_mid_posted or None, title_overrides,
                          posted_note=job.pay_note)
        totals = {"conservative": 0.0, "base": 0.0, "upside": 0.0}
        first_row = len(scored)
        for cluster_key, count in sorted(distribution.items(), key=lambda kv: -kv[1]):
            cluster = CLUSTER_BY_KEY[cluster_key]
            hours = ANNUAL_HOURS * count / total_bullets
            row = {
                "job_id": job.job_id, "title": job.title, "department": job.department,
                "cluster": cluster_key, "cluster_label": cluster.label,
                "bullet_count": count, "bullet_share": round(count / total_bullets, 4),
                "role_hours_annual": round(hours, 1),
                "fit_normal": cluster.fit_n, "fit_bespoke": cluster.fit_b,
                "bespoke_build": cluster.bespoke,
                "addressable_share": cluster.addr,
                "time_basis": cluster.basis, "time_source": cluster.time_src,
                "evidence_confidence": cluster.conf,
                "hourly_usd_equiv": basis.hourly,
            }
            for scenario in ("conservative", "base", "upside"):
                adoption, tred_i = scenario_adoption(scenario)
                saved = hours * cluster.addr * cluster.tred[tred_i] * adoption * (cluster.fit_n / 100)
                row[f"saved_hours_{scenario}"] = round(saved, 1)
                row[f"saved_value_{scenario}"] = round(saved * basis.hourly, 0)
                totals[scenario] += saved
            scored.append(row)
        # Per-row rounding to 0.1 h can drift the role's sum past the ±0.5 h
        # validation gate on roles with many clusters; land the remainder on
        # the smallest cluster so every role sums to exactly ANNUAL_HOURS.
        job_rows = scored[first_row:]
        if job_rows:
            drift = round(ANNUAL_HOURS - sum(r["role_hours_annual"] for r in job_rows), 1)
            if drift:
                job_rows[-1]["role_hours_annual"] = round(job_rows[-1]["role_hours_annual"] + drift, 1)

        role_rows.append({
            "job_id": job.job_id, "title": job.title, "department": job.department,
            "location": job.location, "url": job.url,
            "occupation_soc": basis.soc, "occupation": basis.occupation,
            "seniority": basis.seniority, "us_equiv_base_pay": basis.base_pay,
            "pay_source": basis.pay_source,
            "posted_range": (f"${job.pay_min_posted}-${job.pay_max_posted}"
                             if job.pay_min_posted else ""),
            "hourly_equiv": basis.hourly,
            "loaded_hourly_equiv": basis.loaded_hourly,
            "role_hours_annual": ANNUAL_HOURS,
            "saved_hours_conservative": round(totals["conservative"], 1),
            "saved_hours_base": round(totals["base"], 1),
            "saved_hours_upside": round(totals["upside"], 1),
            "saved_value_base": round(totals["base"] * basis.hourly, 0),
            "pct_capacity_freed_base": round(100 * totals["base"] / ANNUAL_HOURS, 1),
        })

    aggregate: dict[str, dict] = defaultdict(lambda: {"hours": 0.0, "base": 0.0, "bullets": 0})
    for row in scored:
        agg = aggregate[row["cluster"]]
        agg["hours"] += row["role_hours_annual"]
        agg["base"] += row["saved_hours_base"]
        agg["bullets"] += row["bullet_count"]
    ranking = []
    for key, agg in aggregate.items():
        cluster = CLUSTER_BY_KEY[key]
        ranking.append({
            "cluster": key, "cluster_label": cluster.label,
            "fit_normal": cluster.fit_n, "fit_bespoke": cluster.fit_b,
            "bespoke_build": cluster.bespoke,
            "addressable_share": cluster.addr,
            "time_basis": cluster.basis, "time_source": cluster.time_src,
            "evidence_confidence": cluster.conf,
            "rationale": cluster.rationale,
            "recommended_workflow": cluster.workflow,
            "human_checkpoint": cluster.checkpoint,
            "portfolio_hours": round(agg["hours"], 1),
            "portfolio_saved_hours_base": round(agg["base"], 1),
            "bullet_count": agg["bullets"],
        })
    ranking.sort(key=lambda r: -(r["fit_normal"] * 1000 + r["portfolio_saved_hours_base"]))

    return {"normalized": normalized, "scored": scored, "roles": role_rows, "clusters": ranking}


def scenario_adoption(scenario: str) -> tuple[float, int]:
    adoption = ADOPTION[scenario]
    return adoption, {"conservative": 0, "base": 1, "upside": 2}[scenario]


def job_board_components(model: dict[str, list[dict]], hourly_default: Decimal) -> list:
    """Convert the portfolio model into job-board value components.

    The whole job-board model becomes one component keyed to its own work
    surface ("open_role_capacity"), since posting-level time allocation is
    bullet-proportional and does not correspond to the well's per-unit arms.
    """
    from account_value.components import ValueComponent

    total_base_hours = sum(Decimal(str(r["saved_hours_base"])) for r in model["roles"])
    total_hours = sum(Decimal(str(r["role_hours_annual"])) for r in model["roles"])
    pct = float(total_base_hours / total_hours * 100) if total_hours else 0.0
    component = ValueComponent(
        component_id="jobboard-open-role-capacity",
        origin="job_board_model",
        description=(
            f"Open-role capacity value: {total_base_hours:.0f} saved hours/year "
            f"(base scenario) across open postings, {pct:.1f}% of posting-equivalent capacity"
        ),
        work_surface="open_role_capacity",
        saved_hours_annual=total_base_hours,
        period="annual",
        calculation_basis=(
            "role_hours x addressable_share x net_time_reduction x adoption x fit/100, "
            f"taxonomy {TAXONOMY_VERSION}, {ANNUAL_HOURS} h/FTE-year, adoption "
            f"{ADOPTION['conservative']}/{ADOPTION['base']}/{ADOPTION['upside']}, "
            f"loaded factor {LOADED_FACTOR}"
        ),
        assumptions=[
            "one FTE per open posting (open-req equivalent, not company-wide payroll)",
            "bullet-proportional time allocation, not a measured time study",
            "US-equivalent pay for all locations",
        ],
        confidence="Medium",
        model_version=TAXONOMY_VERSION,
        overlap_key="open_role_capacity:*",
    )
    # hourly_default records the compensation basis used downstream when the
    # model's own per-role hourly rates are unavailable.
    del hourly_default
    return [component]


def write_processed(out_dir: Path, model: dict[str, list[dict]]) -> dict[str, Path]:
    """Write the four processed CSVs; returns name -> path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, rows in (
        ("responsibilities_normalized.csv", model["normalized"]),
        ("scored_responsibilities.csv", model["scored"]),
        ("role_summary.csv", model["roles"]),
        ("cluster_ranking.csv", model["clusters"]),
    ):
        path = out_dir / name
        if rows:
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
        else:
            path.write_text("", encoding="utf-8")
        written[name] = path
    return written
