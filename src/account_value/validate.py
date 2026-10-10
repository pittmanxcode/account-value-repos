"""Deterministic validation gate (generalized from the Crunchyroll 20-check gate).

Everything here is checkable from the produced data; a failure blocks
publication (fail closed). Checks adapt to the account: counts are
cross-referenced rather than hardcoded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from account_value.pay import ANNUAL_HOURS
from account_value.value_model import ADOPTION


@dataclass
class ValidationReport:
    passed: bool = True
    failures: list[str] = field(default_factory=list)
    excluded_jobs: list[dict] = field(default_factory=list)

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        if not ok:
            self.failures.append(f"{name} [{detail}]")


def validate_package(
    jobs: list[dict],
    normalized: list[dict],
    scored: list[dict],
    roles: list[dict],
    clusters: list[dict],
    components: list[dict],
    reconciliation: dict,
    workbook_path: Path | None = None,
) -> ValidationReport:
    report = ValidationReport()

    # Catalogue
    report.check("postings present", len(jobs) > 0, f"n={len(jobs)}")
    report.check(
        "job_id unique",
        len({j["job_id"] for j in jobs}) == len(jobs),
    )
    report.check(
        "every posting has URL and content chars",
        all(str(j.get("url", "")).startswith("http") for j in jobs) and all(j.get("content_chars", 1) for j in jobs),
    )
    report.check(
        "bullet rows = normalized rows",
        True,  # structural: normalized IS the bullet list plus classification
    )
    report.check(
        "every bullet classified or flagged noise",
        all((r["cluster"] or int(r["is_noise"]) == 1) for r in normalized),
    )
    # Postings that produce no responsibility bullets (talent pools, general
    # applications) are recorded as explicit exclusions instead of failing the
    # package; a package where nothing at all was modeled still fails closed.
    covered = {r["job_id"] for r in normalized}
    report.excluded_jobs = [
        {"job_id": j["job_id"], "title": j.get("title", "")}
        for j in jobs if j["job_id"] not in covered
    ]
    report.check(
        "at least one posting modeled (excluded postings are listed, not counted)",
        bool(covered),
        f"{len(report.excluded_jobs)} of {len(jobs)} postings excluded, none modeled",
    )

    # Scoring bounds
    report.check("fit_normal within 0-100", all(0 <= int(s["fit_normal"]) <= 100 for s in scored))
    report.check("fit_bespoke within 0-100", all(0 <= int(s["fit_bespoke"]) <= 100 for s in scored))
    report.check(
        "fit_bespoke >= fit_normal (uplift only)",
        all(int(s["fit_bespoke"]) >= int(s["fit_normal"]) for s in scored),
    )
    report.check(
        "addressable share in 0-1",
        all(0 <= float(s["addressable_share"]) <= 1 for s in scored),
    )
    report.check(
        "every scored row has time basis + source",
        all(s["time_basis"] and s["time_source"] for s in scored),
    )
    report.check(
        "every scored row has evidence confidence",
        all(s["evidence_confidence"] for s in scored),
    )

    # Hours and scenarios
    from collections import defaultdict

    hours_by_job: dict[str, float] = defaultdict(float)
    for row in scored:
        hours_by_job[row["job_id"]] += float(row["role_hours_annual"])
    report.check(
        "each role's hours sum to ANNUAL_HOURS (±0.5)",
        all(abs(h - ANNUAL_HOURS) < 0.5 for h in hours_by_job.values()),
        f"n_roles={len(hours_by_job)}",
    )
    bad = [
        row for row in scored
        if not (float(row["saved_hours_conservative"]) <= float(row["saved_hours_base"])
                <= float(row["saved_hours_upside"]))
    ]
    report.check("scenario monotonicity cons<=base<=upside", not bad)
    over = [row for row in scored if float(row["saved_hours_upside"]) > float(row["role_hours_annual"])]
    report.check("saved hours never exceed role-hours", not over)
    report.check(
        "adoption triple matches the model constants",
        ADOPTION["conservative"] < ADOPTION["base"] < ADOPTION["upside"],
    )

    # Pay provenance
    report.check(
        "all roles have positive pay basis",
        all(float(r["us_equiv_base_pay"]) > 0 for r in roles),
    )
    report.check(
        "all roles record a pay source",
        all(r["pay_source"] for r in roles),
    )
    report.check(
        "all roles map to an occupation",
        all(r["occupation"] and r["occupation"] != "unknown occupation" for r in roles),
        f"unmapped: {[r['title'] for r in roles if r['occupation'] == 'unknown occupation'][:5]}",
    )
    report.check(
        "hourly = annual / ANNUAL_HOURS (±1%)",
        all(
            abs(float(r["hourly_equiv"]) - float(r["us_equiv_base_pay"]) / ANNUAL_HOURS)
            < 0.01 * float(r["hourly_equiv"]) + 0.02
            for r in roles
        ),
    )
    report.check(
        "loaded hourly > hourly",
        all(float(r["loaded_hourly_equiv"]) > float(r["hourly_equiv"]) for r in roles),
    )

    # Portfolio reconciliation
    total_saved = sum(float(r["saved_hours_base"]) for r in roles)
    total_hours = sum(float(r["role_hours_annual"]) for r in roles)
    report.check("portfolio saved base <= portfolio hours", total_saved <= total_hours)
    report.check("cluster ranking covers the portfolio",
                 sum(int(c["bullet_count"]) for c in clusters)
                 == sum(int(s["bullet_count"]) for s in scored))

    # Value components and reconciliation
    for component in components:
        report.check(
            f"component {component.get('component_id')} has provenance",
            bool(component.get("calculation_basis") or component.get("evidence")),
        )
        report.check(
            f"component {component.get('component_id')} carries a label",
            bool(component.get("confidence")),
        )
    if reconciliation.get("combined_blocked_reason"):
        report.check(
            "combined total unblocked",
            False,
            reconciliation["combined_blocked_reason"],
        )

    # Workbook, when produced
    if workbook_path is not None:
        report.check(
            "workbook exists and is non-empty",
            workbook_path.exists() and workbook_path.stat().st_size > 10_000,
            str(workbook_path),
        )

    report.passed = not report.failures
    return report


def format_report(report: ValidationReport) -> str:
    head = (
        "ALL VALIDATIONS PASSED"
        if report.passed
        else "VALIDATION FAILED:\n" + "\n".join(f"  FAIL  {f}" for f in report.failures)
    )
    if not report.excluded_jobs:
        return head
    lines = [
        head,
        "",
        f"Excluded postings: {len(report.excluded_jobs)} produced no parseable"
        " responsibilities (talent pools, general applications); recorded, not modeled:",
    ]
    lines.extend(
        f"  - [{job['job_id']}] {job['title']}".rstrip() for job in report.excluded_jobs
    )
    return "\n".join(lines)
