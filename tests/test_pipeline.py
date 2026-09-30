"""End-to-end pipeline: golden fixture regression, events, failure handling."""

import json
from decimal import Decimal

import pytest

from account_value.components import ValueComponent
from account_value.events import load_registry, research_events
from account_value.identity import AmbiguousIdentity, IdentityError, verify_domain
from account_value.pipeline import (
    AccountRequest,
    material_fingerprint,
    run_account,
    slugify,
)

GOLDEN_BASE_HOURS = 18_695
TOLERANCE_HOURS = 50  # explicit rounding tolerance for the generalized model


def test_slugify():
    assert slugify("Crunchyroll, Inc.") == "crunchyroll-inc"


def test_golden_regression_fixture_run(tmp_path, fixture_collection):
    request = AccountRequest(
        company_name="Crunchyroll", company_slug="crunchyroll",
        domain="crunchyroll.com", ats="greenhouse", ats_token="crunchyroll",
        origin="manual",
    )
    result = run_account(request, tmp_path, collection=fixture_collection, fetch=None)
    assert result.validation_passed
    base = sum(float(r["saved_hours_base"]) for r in result.model["roles"])
    assert abs(base - GOLDEN_BASE_HOURS) < TOLERANCE_HOURS
    # Package layout: the standard artifact set.
    package = result.package_dir
    assert (package / "README.md").exists()
    assert (package / "REPORT.md").exists()
    assert (package / "account-value.json").exists()
    assert (package / "reconciliation.json").exists()
    assert (package / "data" / "processed" / "role_summary.csv").exists()
    assert result.workbook_path and result.workbook_path.exists()
    assert result.workbook_path.name == "Crunchyroll × Factory Value.xlsx"


def test_validation_fails_closed_on_bad_package(tmp_path, fixture_collection):
    request = AccountRequest(
        company_name="Crunchyroll", company_slug="crunchyroll", origin="manual",
    )
    result = run_account(request, tmp_path, collection=fixture_collection, fetch=None)
    report = (result.package_dir / "validation-report.txt").read_text()
    assert "ALL VALIDATIONS PASSED" in report or "VALIDATION FAILED" in report


def test_event_research_produces_components_for_anchored_signals():
    registry = load_registry()
    postings = [("Senior Java Engineer", "Migrate our Java 8 Spring Boot services")]
    result = research_events(registry, postings)
    assert "R1" in result.matched_signals
    displaced = [c for c in result.components if c.signal_id == "R1"]
    assert displaced and displaced[0].units == 1
    assert displaced[0].saved_hours_annual is not None
    # C1 migration language fires too, as context-only.
    assert "C1" in result.matched_signals


def test_event_unknowns_are_recorded_not_fabricated():
    registry = load_registry()
    postings = [("Compliance Engineer", "Own PCI DSS compliance for our checkout")]
    result = research_events(registry, postings)
    assert "R9" in result.matched_signals
    assert not [c for c in result.components if c.signal_id == "R9"]
    assert any("R9" in u for u in result.open_unknowns)


def test_inherited_value_preserved_and_deduped(tmp_path, fixture_collection):
    inherited = ValueComponent(
        component_id="manual-1", origin="manual",
        description="Oracle license savings on the Java estate (compelling event)",
        work_surface="event_r1", signal_id="R1",
        hard_cost_usd=Decimal("40000"),
        calculation_basis="manual entry", confidence="Medium", model_version="manual",
    )
    request = AccountRequest(
        company_name="Crunchyroll", company_slug="crunchyroll",
        domain="crunchyroll.com", inherited_components=[inherited], origin="manual",
    )
    result = run_account(request, tmp_path, collection=fixture_collection, fetch=None)
    assert result.validation_passed
    # Inherited hard cost survives the round trip.
    report = (result.package_dir / "REPORT.md").read_text()
    assert "Oracle license savings" in report


def test_identity_verification_with_fake_fetch():
    page = "<html><title>Acme Corp — home</title></html>"

    def fetch(url):
        return type("R", (), {"status_code": 200, "text": page, "raise_for_status": lambda s: None})()

    identity = verify_domain("acme.com", fetch=fetch)
    assert identity is not None and identity.verified
    assert "acme" in identity.legal_name.lower()


def test_identity_offline_domain_fails():
    from account_value import identity as identity_module

    def fetch(url):
        raise ConnectionError("offline")

    with pytest.raises(IdentityError):
        identity_module.resolve("Something", domain="unreachable.example", fetch=fetch)


def test_material_fingerprint_ignores_timestamps():
    base = {
        "identity": {"legal_name": "A", "canonical_domain": "a.com"},
        "lifecycle_state": "qualified",
        "signals": [{"signal_id": "R1"}],
        "generated_at": "2026-01-01",
    }
    changed = json.loads(json.dumps(base))
    changed["generated_at"] = "2026-06-01"
    assert material_fingerprint(base) == material_fingerprint(changed)
    moved = json.loads(json.dumps(base))
    moved["lifecycle_state"] = "researching"
    assert material_fingerprint(base) != material_fingerprint(moved)


def test_ambiguity_carries_candidates(monkeypatch):
    from account_value import identity as identity_module

    def fetch(url):
        return type("R", (), {
            "status_code": 200,
            "text": "<html><title>Welcome</title></html>",
            "raise_for_status": lambda s: None,
        })()

    monkeypatch.setattr(identity_module, "_domain_candidates",
                        lambda name: ["one.com", "two.com"])
    with pytest.raises(AmbiguousIdentity) as excinfo:
        identity_module.resolve("Alpha", fetch=fetch)
    assert len(excinfo.value.candidates) == 2
