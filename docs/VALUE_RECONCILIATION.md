# Value Reconciliation — the shared value contract

Every dollar or hour in a report is a **value component**: a versioned record
with evidence, provenance, and an overlap key.

## Component schema

| Field | Meaning |
|---|---|
| `component_id` | Stable ID (used in review decisions) |
| `origin` | `manual`, `direct_research`, `inherited_well`, or `job_board_model` |
| `work_surface` | The work being valued (e.g. `event_r1`, `open_role_capacity`) |
| `signal_id` | Registry signal for compelling events, when applicable |
| `units` / `unit_label` | Observable counts (never summed across unlike labels) |
| `saved_hours_annual` | Saved capacity, annualized |
| `hard_cost_usd` | Attributable hard cost |
| `calculation_basis` | The formula and anchors, spelled out |
| `evidence` | Verbatim quotes with URL, role (Q/C/RT), label, retrieval time, hash |
| `confidence` | High / Medium / Low (+ qualifiers) |
| `overlap_key` | Deterministic: `{work_surface}:{signal_id or *}` |

## The three sections of every report

1. **Inherited compelling-event value** — entered at intake (V1) or imported
   from the well (V2). Preserved verbatim: never recalculated, never
   overwritten by the job-board model.
2. **Job-board capacity value** — the deterministic scenario model over open
   postings (conservative / base / upside).
3. **Reconciled account value** — the combined total, only where the overlap
   reconciliation supports it.

## Overlap rules

| Case | Report shows | Combined total |
|---|---|---|
| Same `overlap_key` on both sides | Both components (duplicate visible) | Inherited counted **once**; the new duplicate suppressed with a recorded decision |
| Same `work_surface`, different keys | Both components, flagged | **No combined claim** until a human resolves the overlap |
| Distinct work surfaces | Both | Sum |
| Hard cost vs saved labor | Always labeled separately | Never merged without a demonstrably non-overlapping basis |

Combined totals are blocked (visible, with the reason) whenever any unresolved
overlap exists. Every suppression or exclusion records the component IDs and
the reason in `reconciliation.json`.

## Unit and money rules

- Unlike units are never summed (applications ≠ databases ≠ checkouts).
- Time converts to money only with an explicit compensation basis
  (`hours_to_money`), which is why the workbook carries the pay-provenance
  sheets.
- The job-board model is one component (`open_role_capacity`) because its
  posting-level allocation is bullet-proportional, not a measured time study —
  it must never be silently merged with per-unit event arithmetic.

## Worked examples

**Distinct:** inherited Oracle-license savings (hard cost, R1) + job-board
capacity value (saved hours) → combined total shows both, labeled separately.

**Duplicate:** the well imported an R1 displaced-work component; the event
research independently matched R1 with the same units → the research copy is
shown but suppressed from the sum.

**Unresolved:** inherited "engineering capacity freed" (R1, vague surface)
and a job-board model that includes engineering hours → same work surface,
no confirmed key match → combined total blocked until you resolve it.
