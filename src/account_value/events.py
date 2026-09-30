"""Compelling-event research against a versioned signal registry.

Signals are matched deterministically against collected posting text (job
posts are a qualifying source per operating rules v1 §1). A matched deadline
signal with an effort anchor and observable units produces a displaced-work
component; everything else records an honest "unknown, where looked".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator

from account_value.components import EvidenceRef, ValueComponent
from account_value.value_model import ADOPTION

DEV_DAY_USD = 800
FACTORY_SHARE_DEFAULT = 0.50


class DeadlineSignal(BaseModel):
    id: str
    name: str
    trigger: str
    trigger_date: str
    hard_cost_anchor: str | None
    hard_cost_label: str | None
    effort_anchor_hours_per_unit: int | None
    effort_unit: str | None
    match_patterns: str

    @field_validator("match_patterns")
    @classmethod
    def _valid_regex(cls, v: str) -> str:
        re.compile(v)
        return v


class CatalogSignal(BaseModel):
    id: str
    name: str
    value_type: str
    match_patterns: str


class Registry(BaseModel):
    schema_version: int
    deadline_signals: list[DeadlineSignal]
    catalog_signals: list[CatalogSignal]


def load_registry(path: Path | None = None) -> Registry:
    candidates = [
        path,
        Path("registry/signals.yaml"),
        Path(__file__).resolve().parents[2] / "registry" / "signals.yaml",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            raw = yaml.safe_load(candidate.read_text(encoding="utf-8"))
            registry = Registry.model_validate(raw)
            _cross_check(registry)
            return registry
    raise FileNotFoundError("signal registry not found (registry/signals.yaml)")


def _cross_check(registry: Registry) -> None:
    ids = [s.id for s in registry.deadline_signals] + [s.id for s in registry.catalog_signals]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate signal ids in registry")
    for signal in registry.deadline_signals:
        if signal.hard_cost_anchor is not None and signal.hard_cost_label is None:
            raise ValueError(f"{signal.id}: hard-cost anchor present but unlabeled")


@dataclass
class EventResearchResult:
    components: list[ValueComponent]
    open_unknowns: list[str]
    matched_signals: list[str]


def research_events(
    registry: Registry,
    postings_text: list[tuple[str, str]],  # (title, verbatim bullet text)
    unit_label_hint: str | None = None,
) -> EventResearchResult:
    """Match registry signals against posting text; derive value where defensible."""
    components: list[ValueComponent] = []
    unknowns: list[str] = []
    matched: list[str] = []

    for signal in registry.deadline_signals:
        pattern = re.compile(signal.match_patterns, re.I)
        hits = [(title, text) for title, text in postings_text if pattern.search(text) or pattern.search(title)]
        if not hits:
            continue
        matched.append(signal.id)
        quote_title, quote_text = hits[0]
        evidence = [EvidenceRef(
            url="",  # provenance carried by the collection snapshot hash
            verbatim_quote=quote_text[:300],
            source_role="Q",
            label="observed (job posting)",
            retrieval_time="",
            content_hash="",
        )]
        # Units: postings are observable only when the signal's unit maps to
        # a posting-equivalent (application). Anything else stays unknown.
        units = len(hits) if signal.effort_unit in ("application",) else None
        if signal.effort_anchor_hours_per_unit and units:
            hours = signal.effort_anchor_hours_per_unit * units
            saved = round(
                hours * FACTORY_SHARE_DEFAULT * ADOPTION["base"]
            )
            components.append(ValueComponent(
                component_id=f"event-{signal.id.lower()}-displaced-work",
                origin="direct_research",
                description=(
                    f"{signal.name}: {units} {signal.effort_unit}(s) x "
                    f"{signal.effort_anchor_hours_per_unit}h conservative anchor "
                    f"(compelling event: {signal.trigger})"
                ),
                work_surface=f"event_{signal.id.lower()}",
                units=units,
                unit_label=signal.effort_unit,
                saved_hours_annual=saved,
                period="annual",
                calculation_basis=(
                    f"units({units}) x effort({signal.effort_anchor_hours_per_unit}h, "
                    "TP/EST conservative end) x factory_share(0.50) x adoption(base 0.75)"
                ),
                signal_id=signal.id,
                evidence=evidence,
                assumptions=["$800/loaded dev-day basis", "share limited to edit + test repair"],
                confidence="Medium",
                model_version="account-value 0.1.0",
            ))
        else:
            if not signal.effort_anchor_hours_per_unit:
                unknowns.append(
                    f"{signal.id}: no public effort benchmark — displaced-work arm is "
                    "unknown, where looked (registry anchors, HeroDevs/OpenRewrite comparisons)"
                )
            if units is None:
                unknowns.append(
                    f"{signal.id}: unit type {signal.effort_unit!r} not observable from "
                    "postings — unknown, where looked (public artifacts, trust centers)"
                )

    for signal in registry.catalog_signals:
        pattern = re.compile(signal.match_patterns, re.I)
        if any(pattern.search(text) or pattern.search(title) for title, text in postings_text):
            matched.append(signal.id)
            if signal.value_type == "indirect":
                unknowns.append(
                    f"{signal.id} ({signal.name}): indirect signal — context only, "
                    "never a value line on its own"
                )
    del unit_label_hint
    return EventResearchResult(
        components=components, open_unknowns=unknowns, matched_signals=matched
    )
