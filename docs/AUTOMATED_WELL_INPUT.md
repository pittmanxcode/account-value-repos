# V2 — Automated Well Input Loop

**Status: implemented and tested, publication DISABLED.** The buyer-readiness
well (`factory-buyer-readiness-well`) does not yet produce trustworthy
qualified accounts, so V2 publication is blocked by config until the upstream
contract is real.

## Commands

```bash
account-value well doctor   # run the readiness gate; exits 1 with reasons
account-value well plan     # the ranked selection a batch would process
account-value well run      # refuses while well_enabled: false
```

## The upstream contract

V2 consumes only `data/exports/accounts.v1.jsonl` from the well, and only
when it can be verified end to end:

1. **Receipt sidecar** (`accounts.v1.jsonl.receipt.json`) with row count and
   SHA-256 matching the snapshot. A partial or mismatched export fails closed.
2. **Verified identity** for each account: a real canonical company domain
   (dot-shaped). Registry-style paths such as
   `usaspending.gov/recipient/...` are placeholders, not domains.
3. **Machine-readable ranking** (`ranking_snapshot`): the documented priority
   order (tier → urgency → conservative value → confidence) must be data, so
   the downstream never invents a second ranking.
4. **Provenance**: active signals, evidence hashes, estate units, and both
   value arms for anything carrying dollars.
5. **Inherited value components** (`inherited_value_components`): the well's
   computed compelling-event value, imported verbatim.

## Selection order (once enabled)

1. Qualified Tier 1 / Tier 2 accounts first.
2. Then verified `researching` accounts with qualifying evidence (backfill).
3. Ranked by tier, urgency, inherited conservative value, confidence.
4. Accounts whose material fingerprint already exists on main or in an open
   batch are skipped.
5. A batch processes candidates until 10 workbooks pass; blocked or failed
   candidates get failure records and are backfilled from lower ranks.
6. A run with nothing new is a successful no-op (report only, no PR).

## Enablement checklist

Work through this when the well is fixed; do not skip steps.

1. `account-value well doctor` exits 0 against the well's live export.
2. `account-value well plan` shows a sensible ranked selection.
3. Set `well_enabled: true` in `config.yaml`.
4. Run `account-value well run` manually once; review the batch PR.
5. Only then consider scheduling (spec: no scheduler in this phase).

## What V2 never does

- It never recalculates or overwrites inherited well value.
- It never reads manual-loop drafts as qualification data.
- It never merges, contacts anyone, or writes to a CRM.
