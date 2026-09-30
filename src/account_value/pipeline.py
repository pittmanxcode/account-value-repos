"""The shared automated pipeline: identity -> events -> jobs -> value -> package.

Both intake loops (V1 typed account name, V2 well import) enter here. Every
step after intake is automated; failures write a local failure report and
publish nothing.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from account_value.collectors import CollectionResult, CollectorError
from account_value.collectors import collect as run_collector
from account_value.components import ValueComponent
from account_value.events import EventResearchResult, research_events
from account_value.identity import Identity
from account_value.reconcile import ReconciliationResult
from account_value.validate import validate_package
from account_value.value_model import (
    Bullet,
    JobPosting,
    build_model,
    job_board_components,
    write_processed,
)


class PipelineError(RuntimeError):
    pass


@dataclass
class AccountRequest:
    company_name: str
    company_slug: str
    domain: str = ""
    careers_url: str = ""
    ats: str = ""
    ats_token: str = ""
    inherited_components: list[ValueComponent] = field(default_factory=list)
    notes: str = ""
    origin: str = "manual"  # manual | buyer_readiness_well
    account_id: str = ""

    def to_dict(self) -> dict:
        return {
            "company_name": self.company_name,
            "company_slug": self.company_slug,
            "domain": self.domain,
            "careers_url": self.careers_url,
            "ats": self.ats,
            "ats_token": self.ats_token,
            "inherited_components": [c.to_dict() for c in self.inherited_components],
            "notes": self.notes,
            "origin": self.origin,
            "account_id": self.account_id,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> AccountRequest:
        data = dict(payload)
        data["inherited_components"] = [
            ValueComponent.from_dict(c) for c in data.get("inherited_components", [])
        ]
        return cls(**data)


@dataclass
class AccountPackageResult:
    request: AccountRequest
    package_dir: Path
    validation_passed: bool
    collection: CollectionResult | None
    events: EventResearchResult
    reconciliation: ReconciliationResult
    model: dict[str, list[dict]]
    jobs: list[JobPosting]
    bullets: list[Bullet]
    workbook_path: Path | None = None


def slugify(name: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "account"


def _fetch_none(url: str):
    raise PipelineError(f"network fetch attempted in offline mode: {url}")


def run_account(
    request: AccountRequest,
    workspace: Path,
    identity: Identity | None = None,
    fetch=None,
    collection: CollectionResult | None = None,
    registry=None,
) -> AccountPackageResult:
    """Run the full automated pipeline for one account.

    identity/collection can be injected (tests, offline fixture runs);
    otherwise they are resolved live. Raises PipelineError on failure.
    """
    from account_value.events import load_registry

    workspace = Path(workspace)
    package_dir = workspace / "accounts" / request.company_slug
    raw_dir = package_dir / "data" / "raw"
    processed_dir = package_dir / "data" / "processed"
    registry = registry or load_registry()

    # 1. Identity (skipped when the caller verified it already, or when the
    #    caller injected a collection — offline fixture and test runs).
    if identity is None and collection is None:
        from account_value.identity import resolve

        identity = resolve(
            request.company_name,
            domain=request.domain or None,
            careers_url=request.careers_url or None,
            fetch=fetch,
        )
    if identity is None:
        from account_value.identity import Identity

        identity = Identity(
            legal_name=request.company_name,
            canonical_domain=request.domain,
            careers_url=request.careers_url,
            ats=request.ats,
            ats_token=request.ats_token,
            verified=bool(request.domain),
        )

    # 2. Job-board collection.
    if collection is None:
        if request.ats and request.ats_token:
            collection = run_collector(request.ats, request.ats_token, raw_dir, fetch=fetch)
        elif request.careers_url or (identity and identity.careers_url):
            url = request.careers_url or identity.careers_url
            if request.ats:
                collection = run_collector(request.ats, request.ats_token or url, raw_dir, fetch=fetch)
            else:
                collection = run_collector("jsonld", url, raw_dir, fetch=fetch)
        else:
            raise CollectorError("no careers source resolved for this account")
    if not collection.reconciled:
        raise CollectorError(
            f"posting count did not reconcile: advertised {collection.advertised_count}, "
            f"parsed {len(collection.jobs)}"
        )

    jobs, bullets = collection.jobs, collection.bullets
    if not jobs:
        raise CollectorError("collector returned zero postings — nothing to analyze")

    # 3. Compelling-event research against the registry.
    postings_text = [(b.title, b.verbatim_responsibility) for b in bullets] + [
        (j.title, j.title) for j in jobs
    ]
    events = research_events(registry, postings_text)

    # 4. Scenario value model (deterministic).
    title_overrides = _load_overrides(workspace)
    model = build_model(jobs, bullets, title_overrides, request.company_name)

    # 5. Reconciliation: inherited + event value (first), then the job-board
    #    model as one component.
    jobboard = job_board_components(model, Decimal("0"))
    pre_reconciled = _reconcile_pair(request.inherited_components, events.components)
    reconciliation = _reconcile_pair(
        pre_reconciled.counted, jobboard, extra_decisions=pre_reconciled.decisions
    )

    # 6. Validation gate.
    validation = _validate(
        package_dir, collection, model, events, reconciliation
    )

    # 7. Package + workbook.
    snapshot_date = datetime.now(UTC).strftime("%B %d, %Y")
    write_processed(processed_dir, model)
    from account_value.package import write_package

    workbook_path = _write_workbook(
        package_dir, request.company_name, model, collection, events,
        request.inherited_components, jobboard, reconciliation, snapshot_date,
    )
    write_package(
        package_dir,
        request.to_dict(),
        identity.to_dict(),
        {
            "ats": collection.ats,
            "snapshot": str(collection.snapshot_path.name),
            "snapshot_hash": collection.snapshot_hash,
            "posting_count": len(collection.jobs),
            "advertised_count": collection.advertised_count,
            "reconciled": collection.reconciled,
            "notes": collection.notes,
        },
        {
            "matched_signals": events.matched_signals,
            "open_unknowns": events.open_unknowns,
            "components": [c.to_dict() for c in events.components],
        },
        model,
        {
            "decisions": [d.__dict__ for d in reconciliation.decisions],
            "combined_saved_hours_annual": (
                str(reconciliation.combined_saved_hours_annual)
                if reconciliation.combined_saved_hours_annual is not None else None
            ),
            "combined_hard_cost_usd": (
                str(reconciliation.combined_hard_cost_usd)
                if reconciliation.combined_hard_cost_usd is not None else None
            ),
            "combined_blocked_reason": reconciliation.combined_blocked_reason,
        },
        validation,
        snapshot_date,
    )
    _write_reconciliation(package_dir, request, reconciliation)

    return AccountPackageResult(
        request=request,
        package_dir=package_dir,
        validation_passed=validation,
        collection=collection,
        events=events,
        reconciliation=reconciliation,
        model=model,
        jobs=jobs,
        bullets=bullets,
        workbook_path=workbook_path,
    )


def _load_overrides(workspace: Path) -> dict[str, tuple[str, str]]:
    from account_value.pay import load_title_overrides

    override = (
        Path("examples/crunchyroll/pay_title_map.yaml")
        if (Path("examples/crunchyroll/pay_title_map.yaml").exists())
        else None
    )
    return load_title_overrides(override) if override else {}


def _reconcile_pair(
    inherited: list[ValueComponent],
    new: list[ValueComponent],
    extra_decisions=None,
):
    from account_value.reconcile import reconcile

    result = reconcile(inherited, new)
    if extra_decisions:
        result.decisions = extra_decisions + result.decisions
        if result.has_unresolved:
            result.combined_saved_hours_annual = None
            result.combined_hard_cost_usd = None
            result.combined_blocked_reason = "unresolved overlap present (see decisions)"
    return result


def _validate(
    package_dir: Path,
    collection: CollectionResult,
    model: dict,
    events: EventResearchResult,
    reconciliation: ReconciliationResult,
) -> bool:
    from account_value.validate import format_report

    jobs_payload = [
        {"job_id": j.job_id, "title": j.title, "url": j.url, "content_chars": 1,
         "pay_min_posted": j.pay_min_posted, "pay_max_posted": j.pay_max_posted}
        for j in collection.jobs
    ]
    report = validate_package(
        jobs=jobs_payload,
        normalized=model["normalized"],
        scored=model["scored"],
        roles=model["roles"],
        clusters=model["clusters"],
        components=[c.to_dict() for c in events.components],
        reconciliation={
            "combined_blocked_reason": reconciliation.combined_blocked_reason,
            "decisions": [d.__dict__ for d in reconciliation.decisions],
        },
    )
    report_path = package_dir / "validation-report.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(format_report(report) + "\n", encoding="utf-8")
    return report.passed


def _write_workbook(
    package_dir, company, model, collection, events,
    inherited, jobboard, reconciliation, snapshot_date,
) -> Path:
    import tempfile

    from account_value.workbook import build_spec, convert

    jobs_payload = [j.__dict__ | {"language": j.language} for j in collection.jobs]
    spec = build_spec(
        company=company,
        model=model,
        jobs=jobs_payload,
        inherited_components=[c.to_dict() for c in inherited],
        jobboard_components=[c.to_dict() for c in jobboard],
        reconciliation={
            "combined_blocked_reason": reconciliation.combined_blocked_reason,
            "combined_saved_hours_annual": (
                int(reconciliation.combined_saved_hours_annual)
                if reconciliation.combined_saved_hours_annual is not None else None
            ),
            "combined_hard_cost_usd": (
                int(reconciliation.combined_hard_cost_usd)
                if reconciliation.combined_hard_cost_usd is not None else None
            ),
            "decisions": [d.__dict__ for d in reconciliation.decisions],
        },
        snapshot_date=snapshot_date,
        wage_table_source="BLS OEWS May 2025 via O*NET (shipped with the package)",
        open_unknowns=events.open_unknowns,
    )
    with tempfile.TemporaryDirectory() as tmp:
        spec_path = Path(tmp) / "spec.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        out_dir = package_dir / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{company} × Factory Value.xlsx"
        convert(spec_path, out_path)
        return out_path


def _write_reconciliation(package_dir, request, reconciliation) -> None:
    path = package_dir / "reconciliation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "decisions": [d.__dict__ for d in reconciliation.decisions],
        "combined_saved_hours_annual": (
            str(reconciliation.combined_saved_hours_annual)
            if reconciliation.combined_saved_hours_annual is not None else None
        ),
        "combined_hard_cost_usd": (
            str(reconciliation.combined_hard_cost_usd)
            if reconciliation.combined_hard_cost_usd is not None else None
        ),
        "combined_blocked_reason": reconciliation.combined_blocked_reason,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def failure_report(workspace: Path, request: AccountRequest, error: Exception) -> Path:
    directory = workspace / "failures"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    path = directory / f"{request.company_slug}-{stamp}.md"
    path.write_text(
        f"# Failure report: {request.company_name}\n\n"
        f"- Time: {stamp}\n- Stage error: {type(error).__name__}: {error}\n\n"
        "Nothing was published. Fix the cause or supply identity flags and rerun:\n\n"
        "    account-value run --request <request file>\n",
        encoding="utf-8",
    )
    return path


def material_fingerprint(payload: dict) -> str:
    """Stable fingerprint over value-bearing fields (timestamps ignored)."""
    relevant = {
        "identity": payload.get("identity", {}),
        "lifecycle_state": payload.get("lifecycle_state"),
        "tier": payload.get("tier"),
        "signals": payload.get("signals", []),
        "estate_units": payload.get("estate_units", []),
        "value_arms": payload.get("value_arms", {}),
        "feasibility": payload.get("feasibility"),
    }
    return hashlib.sha256(json.dumps(relevant, sort_keys=True).encode()).hexdigest()[:16]
