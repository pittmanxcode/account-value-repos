"""Versioned value components (the shared value contract).

Every dollar or hour in a report is a component: an inherited compelling
event, a directly researched event, or a job-board model output. Components
from upstream (manual entry or the well) are copied unchanged — this module's
round-trip is byte-stable except for explicit field additions.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal

ORIGINS = frozenset({"manual", "direct_research", "inherited_well", "job_board_model"})
CONFIDENCE_BANDS = frozenset({"High", "Medium", "Low", "Low-Medium", "Medium-High", "unknown"})


@dataclass(frozen=True)
class EvidenceRef:
    """One verbatim, hash-addressed piece of evidence behind a component."""

    url: str
    verbatim_quote: str
    source_role: str  # Q | C | RT
    label: str  # CD | TP | EST | observed | ...
    retrieval_time: str
    content_hash: str


@dataclass
class ValueComponent:
    component_id: str
    origin: str  # one of ORIGINS
    description: str
    work_surface: str  # e.g. "java_upgrade", "ap_reconciliation"
    # Counts (never summed across incompatible unit labels):
    units: Decimal | None = None
    unit_label: str | None = None
    # Value lines (either or both; None means not established):
    saved_hours_annual: Decimal | None = None
    hard_cost_usd: Decimal | None = None
    # Basis and provenance:
    period: str = "annual"
    calculation_basis: str = ""
    signal_id: str | None = None
    evidence: list[EvidenceRef] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    confidence: str = "unknown"
    model_version: str = ""
    overlap_key: str = ""

    def __post_init__(self) -> None:
        if self.origin not in ORIGINS:
            raise ValueError(f"unknown origin: {self.origin!r}")
        if not self.overlap_key:
            self.overlap_key = default_overlap_key(self.work_surface, self.signal_id)
        for name in ("units", "saved_hours_annual", "hard_cost_usd"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, Decimal):
                setattr(self, name, Decimal(str(value)))

    def to_dict(self) -> dict:
        payload = asdict(self)
        for name in ("units", "saved_hours_annual", "hard_cost_usd"):
            if payload[name] is not None:
                payload[name] = str(payload[name])
        return payload

    @classmethod
    def from_dict(cls, payload: dict) -> ValueComponent:
        data = dict(payload)
        evidence = [EvidenceRef(**e) for e in data.pop("evidence", [])]
        component = cls(**data, evidence=evidence)  # type: ignore[arg-type]
        return component


def default_overlap_key(work_surface: str, signal_id: str | None) -> str:
    """Deterministic key: same work surface + signal = same value, counted once."""
    surface = re.sub(r"[^a-z0-9]+", "_", work_surface.strip().lower()).strip("_")
    return f"{surface}:{signal_id or '*'}"


def component_fingerprint(component: ValueComponent) -> str:
    payload = json.dumps(component.to_dict(), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def hours_to_money(saved_hours_annual: Decimal, hourly_usd: Decimal) -> Decimal:
    """Time converts to money only with an explicit compensation basis."""
    if saved_hours_annual is None or hourly_usd is None:
        raise ValueError("time-to-money requires both hours and an hourly basis")
    return (saved_hours_annual * hourly_usd).quantize(Decimal("1"))
