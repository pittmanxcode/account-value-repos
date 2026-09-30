"""V2 well adapter: fail-closed gate, verified identity, selection, inheritance."""

import json
from pathlib import Path

import pytest

from account_value.well.adapter import (
    load_export,
    select_candidates,
    to_request,
)


def _write_export(directory: Path, accounts: list[dict], receipt: dict | None = None):
    directory.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(a) for a in accounts) + "\n"
    (directory / "accounts.v1.jsonl").write_text(payload, encoding="utf-8")
    import hashlib

    if receipt is not None:
        (directory / "accounts.v1.jsonl.receipt.json").write_text(
            json.dumps({
                "row_count": len(accounts),
                "content_hash": hashlib.sha256(payload.encode()).hexdigest(),
                **receipt,
            }),
            encoding="utf-8",
        )


def _account(name="Example Corp", domain="example.com", state="qualified", **extra):
    account = {
        "schema_version": "1",
        "identity": {
            "account_id": "uuid-1", "legal_name": name,
            "canonical_domain": domain, "hq_country": "US",
        },
        "lifecycle_state": state,
        "tier": "Tier 1" if state == "qualified" else None,
        "confidence_band": "High" if state == "qualified" else None,
        "signals": [{"signal_id": "R1", "state": "active"}],
        "estate_units": [],
        "value_arms": {},
        "feasibility": None,
        "ranking_snapshot": {"urgency": 0.5, "conservative_value_usd": 100000},
        "generated_at": "2026-09-30T00:00:00+00:00",
    }
    account.update(extra)
    return account


def test_current_real_export_fails_closed():
    """The designed behavior: the well's current export has no receipt sidecar."""
    real = Path(__file__).resolve().parents[1].parent / (
        "factory-buyer-readiness-well/data/exports"
    )
    if not real.exists():
        pytest.skip("well repo not present")
    export = load_export(real)
    assert not export.readiness.ready
    assert any("receipt" in f for f in export.readiness.failures)


def test_missing_receipt_fails_closed(tmp_path):
    _write_export(tmp_path, [_account()])
    export = load_export(tmp_path)
    assert not export.readiness.ready
    assert any("receipt" in f for f in export.readiness.failures)


def test_hash_mismatch_fails_closed(tmp_path):
    _write_export(tmp_path, [_account()], receipt={"content_hash": "deadbeef"})
    export = load_export(tmp_path)
    assert not export.readiness.ready
    assert any("mismatch" in f for f in export.readiness.failures)


def test_valid_export_passes_gate(tmp_path):
    _write_export(tmp_path, [_account()], receipt={})
    export = load_export(tmp_path)
    assert export.readiness.ready, export.readiness.failures


def test_unverified_identity_is_flagged_not_fatal(tmp_path):
    _write_export(tmp_path, [
        _account(domain="usaspending.gov/recipient/acme"),
        _account(name="Real Co", domain="realco.com"),
    ], receipt={})
    export = load_export(tmp_path)
    assert export.readiness.ready
    assert any("not verified" in w for w in export.readiness.warnings)


def test_missing_ranking_snapshot_fails_gate(tmp_path):
    """v1 exports lack ranking_snapshot: the documented gate blocks automation."""
    account = _account()
    del account["ranking_snapshot"]
    _write_export(tmp_path, [account], receipt={})
    export = load_export(tmp_path)
    assert not export.readiness.ready
    assert any("ranking_snapshot" in f for f in export.readiness.failures)


def test_selection_prefers_qualified_and_skips_seen(tmp_path):
    accounts = [
        _account(name="Res Co", domain="res.com", state="researching",
                 ranking_snapshot={"urgency": 0.5, "conservative_value_usd": 100000}),
        _account(name="Qual Co", domain="qual.com", state="qualified",
                 ranking_snapshot={"urgency": 0.5, "conservative_value_usd": 100000}),
    ]
    _write_export(tmp_path, accounts, receipt={})
    export = load_export(tmp_path)
    assert export.readiness.ready, export.readiness.failures
    selected = select_candidates(export, 10, set())
    assert [a["identity"]["legal_name"] for a in selected] == ["Qual Co", "Res Co"]

    from account_value.pipeline import material_fingerprint

    seen = {material_fingerprint(accounts[1])}  # Qual Co already produced
    again = select_candidates(export, 10, seen)
    assert [a["identity"]["legal_name"] for a in again] == ["Res Co"]


def test_to_request_preserves_inherited_components(tmp_path):
    inherited = [{
        "component_id": "w-1", "origin": "inherited_well",
        "description": "R1 displaced work", "work_surface": "event_r1",
        "saved_hours_annual": "1200", "signal_id": "R1",
    }]
    account = _account(inherited_value_components=inherited)
    request = to_request(account)
    assert request.origin == "buyer_readiness_well"
    assert request.inherited_components == inherited
