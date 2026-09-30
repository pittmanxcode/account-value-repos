"""Receipt-verified adapter for the buyer-readiness well export (V2 intake).

Fails closed: a missing receipt, schema mismatch, unverified identity, or
missing ranking/provenance data makes the whole export ineligible. The
current well export is expected to fail this gate — that is the designed
behavior until upstream matures.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from account_value.pipeline import AccountRequest, material_fingerprint, slugify

REQUIRED_MANIFEST_FIELDS = (
    "schema_version", "identity", "lifecycle_state",
    "signals", "estate_units", "value_arms",
)
RANKING_FIELDS = ("ranking_snapshot",)  # v1.1 upstream contract, not yet published


@dataclass
class ReadinessReport:
    ready: bool
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class WellExport:
    accounts: list[dict]
    receipt: dict | None
    content_hash: str
    readiness: ReadinessReport


def _receipt_path(export_path: Path) -> Path:
    return export_path.with_suffix(export_path.suffix + ".receipt.json")


def load_export(exports_dir: Path) -> WellExport:
    exports_dir = Path(exports_dir)
    export_path = exports_dir / "accounts.v1.jsonl"
    failures: list[str] = []
    warnings: list[str] = []

    if not export_path.exists():
        failures.append(f"export missing: {export_path}")
        return WellExport([], None, "", ReadinessReport(False, failures, warnings))

    payload = export_path.read_bytes()
    content_hash = hashlib.sha256(payload).hexdigest()
    receipt: dict | None = None
    receipt_file = _receipt_path(export_path)
    if receipt_file.exists():
        receipt = json.loads(receipt_file.read_text())
        if receipt.get("content_hash") and receipt["content_hash"] != content_hash:
            failures.append("receipt hash mismatch: export is partial or corrupted")
        if receipt.get("row_count") is not None:
            actual_rows = len([line for line in payload.decode().splitlines() if line.strip()])
            if receipt["row_count"] != actual_rows:
                failures.append(
                    f"receipt row_count {receipt['row_count']} != actual {actual_rows}"
                )
    else:
        failures.append(
            "no receipt sidecar (accounts.v1.jsonl.receipt.json): the export cannot be"
            " verified as complete; refusing to consume a partial snapshot"
        )

    accounts = [json.loads(line) for line in payload.decode().splitlines() if line.strip()]
    verified = 0
    qualified = 0
    for account in accounts:
        missing = [f for f in REQUIRED_MANIFEST_FIELDS if f not in account]
        if missing:
            failures.append(f"{_name(account)}: missing required fields {missing}")
            continue
        if _identity_verified(account):
            verified += 1
        else:
            warnings.append(f"{_name(account)}: identity not verified (no canonical company domain)")
        if account.get("lifecycle_state") in ("qualified", "export_ready", "exported"):
            qualified += 1
    for field_name in RANKING_FIELDS:
        if accounts and field_name not in accounts[0]:
            failures.append(
                f"export does not carry {field_name}: the documented ranking contract"
                " (tier, urgency, conservative value, confidence) is not machine-readable"
                " in this snapshot; the well must publish it before automated batches run"
            )

    readiness = ReadinessReport(
        ready=not failures, failures=failures, warnings=warnings
    )
    return WellExport(
        accounts=accounts, receipt=receipt,
        content_hash=content_hash, readiness=readiness,
    )


def _name(account: dict) -> str:
    return account.get("identity", {}).get("legal_name", "<unnamed>")


def _identity_verified(account: dict) -> bool:
    domain = account.get("identity", {}).get("canonical_domain", "") or ""
    # A verified company domain is dot-shaped; registry paths
    # (usaspending.gov/recipient/...) are placeholders, not domains.
    return bool(domain) and "/" not in domain and "." in domain


def to_request(account: dict) -> AccountRequest:
    """Convert an eligible well account into a pipeline request, preserving
    any inherited value components verbatim."""
    identity = account.get("identity", {})
    inherited = account.get("inherited_value_components") or []
    return AccountRequest(
        company_name=identity.get("legal_name", "unnamed"),
        company_slug=slugify(identity.get("legal_name", "unnamed")),
        domain=identity.get("canonical_domain", ""),
        origin="buyer_readiness_well",
        account_id=identity.get("account_id", ""),
        inherited_components=inherited,  # preserved unchanged
        notes=f"imported from well export, state {account.get('lifecycle_state')}",
    )


def select_candidates(export: WellExport, limit: int, seen_fingerprints: set[str]) -> list[dict]:
    """Documented order: qualified first, then verified researching; ranked by
    tier, urgency, conservative value, confidence. Unchanged fingerprints skip."""
    if not export.readiness.ready:
        return []

    def rank_key(account: dict) -> tuple:
        tier = account.get("tier") or ""
        tier_rank = 0 if tier == "Tier 1" else 1 if tier == "Tier 2" else 2
        ranking = account.get("ranking_snapshot") or {}
        urgency = float(ranking.get("urgency", 0.0))
        value = float(ranking.get("conservative_value_usd", 0.0))
        confidence = {"High": 3, "Medium": 2, "Low": 1}.get(
            account.get("confidence_band") or "", 0)
        return (tier_rank, -urgency, -value, -confidence, _name(account))

    eligible = [a for a in export.accounts if _identity_verified(a)]
    eligible.sort(key=rank_key)
    selected = []
    for account in eligible:
        if material_fingerprint(account) in seen_fingerprints:
            continue
        selected.append(account)
        if len(selected) >= limit:
            break
    return selected
