"""Value component contract and overlap reconciliation."""

from decimal import Decimal

import pytest

from account_value.components import ValueComponent, component_fingerprint, hours_to_money
from account_value.reconcile import reconcile


def _component(**kwargs) -> ValueComponent:
    defaults = dict(
        component_id="c1", origin="manual", description="d",
        work_surface="java_upgrade", saved_hours_annual=Decimal("100"),
    )
    defaults.update(kwargs)
    return ValueComponent(**defaults)


def test_round_trip_preserves_every_field():
    component = ValueComponent(
        component_id="x", origin="inherited_well", description="R1 event",
        work_surface="java_upgrade", units=Decimal("12"),
        unit_label="application", saved_hours_annual=Decimal("1200"),
        hard_cost_usd=Decimal("5000"), signal_id="R1",
        calculation_basis="units x effort x share",
        confidence="Medium", model_version="account-value 0.1.0",
        assumptions=["$800/dev-day"],
    )
    restored = ValueComponent.from_dict(component.to_dict())
    assert restored == component
    assert component_fingerprint(component) == component_fingerprint(restored)


def test_unknown_origin_rejected():
    with pytest.raises(ValueError):
        _component(origin="vibes")


def test_default_overlap_key_is_deterministic():
    a = _component(signal_id="R1")
    b = _component(signal_id="R1")
    assert a.overlap_key == b.overlap_key == "java_upgrade:R1"


def test_time_to_money_requires_basis():
    assert hours_to_money(Decimal("10"), Decimal("50")) == Decimal("500")
    with pytest.raises(ValueError):
        hours_to_money(None, Decimal("50"))


def test_distinct_surfaces_sum():
    inherited = [_component(component_id="a", work_surface="java_upgrade")]
    new = [_component(component_id="b", origin="job_board_model", work_surface="open_role_capacity")]
    result = reconcile(inherited, new)
    assert result.combined_saved_hours_annual == Decimal("200")
    assert not result.has_unresolved
    assert all(d.outcome == "counted" for d in result.decisions)


def test_confirmed_duplicate_counts_once():
    inherited = [_component(component_id="a", signal_id="R1")]
    new = [_component(component_id="b", origin="job_board_model", signal_id="R1")]
    result = reconcile(inherited, new)
    assert result.combined_saved_hours_annual == Decimal("100")
    outcomes = {d.component_id: d.outcome for d in result.decisions}
    assert outcomes["a"] == "counted"
    assert outcomes["b"] == "duplicate_suppressed"
    assert not result.has_unresolved


def test_unresolved_overlap_blocks_combined_total():
    inherited = [_component(component_id="a", work_surface="java_upgrade", signal_id="R1")]
    new = [_component(component_id="b", origin="job_board_model", work_surface="java_upgrade")]
    result = reconcile(inherited, new)
    assert result.has_unresolved
    assert result.combined_saved_hours_annual is None
    assert result.combined_blocked_reason
