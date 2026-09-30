"""Account value repositories: one pipeline, two intake loops.

V1 (manual account intake): a person names the account; identity resolution,
compelling-event research, job-board analysis, value reconciliation, workbook
generation, validation, and review-PR publication all run automatically.

V2 (well intake): the buyer-readiness well supplies ranked, pre-qualified
accounts and any value it already computed. Implemented and tested, but
publication stays disabled until the well passes its readiness gate.

Shared invariants (spec: value contract):
- Inherited or researched compelling-event value is preserved exactly; the
  job-board model never overwrites it.
- Combined totals require an overlap reconciliation; confirmed duplicates
  count once, unresolved overlaps block a combined headline.
- Every number carries a label; every unknown says "unknown, where looked".
"""

from __future__ import annotations

MODEL_VERSION = "account-value 0.1.0"
TAXONOMY_VERSION = "clusters-v1"
