"""Overlap reconciliation: combined totals without double counting.

Rules (spec: shared value contract):
- Same overlap_key in inherited and new sets -> confirmed duplicate. Shown in
  both sections, counted once (the inherited component wins the sum).
- Same work_surface but different keys -> unresolved possible overlap. Both
  stay visible; the combined total is blocked until a human resolves it.
- Distinct work surfaces sum.
- Hard costs and saved-labor capacity are always labeled separately; the
  combined monetary line sums only non-overlapping parts of each.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from account_value.components import ValueComponent


@dataclass
class ReconciliationDecision:
    component_id: str
    outcome: str  # "counted" | "duplicate_suppressed" | "unresolved_overlap"
    reason: str
    paired_with: str | None = None


@dataclass
class ReconciliationResult:
    counted: list[ValueComponent]
    decisions: list[ReconciliationDecision]
    combined_saved_hours_annual: Decimal | None = None
    combined_hard_cost_usd: Decimal | None = None
    combined_blocked_reason: str | None = None

    @property
    def has_unresolved(self) -> bool:
        return any(d.outcome == "unresolved_overlap" for d in self.decisions)


def reconcile(
    inherited: list[ValueComponent], new: list[ValueComponent]
) -> ReconciliationResult:
    inherited_keys = {c.overlap_key: c for c in inherited}

    counted: list[ValueComponent] = []
    decisions: list[ReconciliationDecision] = []
    for component in inherited:
        counted.append(component)
        decisions.append(
            ReconciliationDecision(component.component_id, "counted", "inherited component retained")
        )
    for component in new:
        if component.overlap_key in inherited_keys:
            decisions.append(
                ReconciliationDecision(
                    component.component_id,
                    "duplicate_suppressed",
                    "same work surface and signal as an inherited component; counted once",
                    paired_with=inherited_keys[component.overlap_key].component_id,
                )
            )
            continue
        if any(
            other.work_surface == component.work_surface
            for other in inherited
            if other.overlap_key != component.overlap_key
        ) and component.overlap_key not in inherited_keys:
            # Same surface, different key on the inherited side: possible
            # overlap that only a human can confirm or refute.
            decisions.append(
                ReconciliationDecision(
                    component.component_id,
                    "unresolved_overlap",
                    "shares a work surface with inherited value but no confirmed match",
                )
            )
            continue
        counted.append(component)
        decisions.append(
            ReconciliationDecision(component.component_id, "counted", "distinct work surface")
        )

    result = ReconciliationResult(counted=counted, decisions=decisions)
    hours = [c.saved_hours_annual for c in counted if c.saved_hours_annual is not None]
    costs = [c.hard_cost_usd for c in counted if c.hard_cost_usd is not None]
    result.combined_saved_hours_annual = sum(hours, Decimal("0")) if hours else None
    result.combined_hard_cost_usd = sum(costs, Decimal("0")) if costs else None
    if result.has_unresolved:
        result.combined_saved_hours_annual = None
        result.combined_hard_cost_usd = None
        result.combined_blocked_reason = (
            "unresolved overlap: components share a work surface without a confirmed"
            " match; resolve or mark distinct before claiming a combined total"
        )
    return result
