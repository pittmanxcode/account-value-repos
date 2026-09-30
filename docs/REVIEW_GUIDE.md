# Review Guide — packages, PRs, and what merge approves

## Where to look

Each account or batch lands as one **draft PR** in
`pittmanxcode/account-value-repos`, branch `automation/account-<slug>` (V1) or
`automation/value-batch-<date>-<hash>` (V2).

The PR description links everything you need. Priority order for a review:

1. **Validation report** (`validation-report.txt`) — must read ALL PASSED.
2. **The workbook** (`outputs/<Company> × Factory Value.xlsx`) — start at the
   Executive Summary: inherited value, job-board scenarios, overlap decisions,
   combined total (or the reason it is blocked).
3. **REPORT.md** — the prose version with top roles and open unknowns.
4. **reconciliation.json** — every overlap decision with component IDs.
5. **Spot-check evidence** — any claim in the workbook traces to a verbatim
   quote in the Responsibility Catalogue or component evidence.

## Decisions you can make in review

- **Approve everything** → merge the PR.
- **Approve most** → remove the package directory of any account you reject
  (a suggestion comment or commit), then merge. Removed accounts are not
  approved; they can be regenerated in a later batch.
- **Reject all** → close the PR. Nothing was on main, so nothing was approved.

## What merge approves

Merging publishes the record to `handoff/contact-search.v1.jsonl` semantics:
an account record on the default branch is **approved** for the future
autonomous contact-search system. The handoff record carries the compelling
events, inherited and job-board value, reconciliation status, and the merged
commit provenance.

Merge does **not** trigger anything yet: no contact search, no outreach, no
CRM write. That system is a later build and will consume only approved
records on the default branch.

## Reruns

An account can be regenerated at any time:

```bash
account-value run --request requests/<slug>.yaml
```

The publication is idempotent: same branch, same PR updated, no force-push,
no duplicate PRs. Materially unchanged accounts are skipped (stable
fingerprints), so a rerun after edits only republishes what changed.
