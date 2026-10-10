# Operations — credentials, logs, idempotency, recovery

## Credentials

- Publication uses **only** `ACCOUNT_VALUE_GITHUB_TOKEN` from the
  environment. It is never written to disk, config, git remotes, or logs.
- It needs write access to `pittmanxcode/account-value-repos` (a classic PAT
  with `repo` scope works; the environment `GH_TOKEN` from the GitHub App
  does not — it lacks write access to this repo).
- Git network commands run with `GIT_CONFIG_GLOBAL=/dev/null`, bypassing
  this machine's global `credential.helper = store` and `insteadOf` URL
  rewrite without modifying them. Tokens reach git through a private askpass
  (`0700`, token via environment only).
- Never paste tokens into chat or files. If one leaks, rotate it at
  github.com/settings/tokens.

## Idempotency

- Branch names are deterministic (`automation/account-<slug>`, V1).
- Re-publication reuses the existing branch and PR; no force-push.
- A validation failure publishes nothing (fail closed) and writes a failure
  report under `failures/`.
- V2 adds material fingerprints: unchanged accounts are skipped entirely.

## Logs and reports

- Pipeline progress prints to stdout; failure reports land in `failures/`.
- Each package carries `validation-report.txt`, `account-value.json`
  (model/taxonomy versions, snapshot hashes), and `reconciliation.json`.
- The golden fixture (`examples/crunchyroll/`) doubles as the regression
  harness: `make fixture` reruns its original pipeline and validation gate.

## Recovery

- **Dirty checkout:** publication builds in an isolated worktree from
  `origin/main`; it never touches your working files.
- **Lost branch:** rerun the command; the branch and PR are recreated from
  the package (which lives locally under `accounts/`).
- **Bad batch merged:** revert the merge commit; the handoff contract only
  recognizes records on the default branch, so a revert un-approves them.

## Secrets handling rules

1. Environment only; never in the repo, config files, or command lines.
2. Never echoed in failure reports (reports quote pipeline errors, which
   never contain the token).
3. Rotate on suspicion; treat anything pasted in chat as burned.

## Collection sources and the fallback chain

- Greenhouse, Lever and Ashby: their public board APIs, as before.
- Workday (policy change, approved 2026-10-10): the public JSON endpoints the
  careers page itself loads (`/wday/cxs/<tenant>/<site>/jobs`, paged by 20,
  then one GET per posting), read-only, with a short delay between posting
  fetches. The earlier collector refused Workday outright; that refusal cited
  no terms, and the endpoint is the same class of first-party source as the
  other three. The list total feeds the reconciliation gate.
- Order: the configured ATS, or JSON-LD on the careers page when none is set,
  always runs first. Fallbacks run only on failure, and only the Workday reader
  exists today (when the careers URL is a `myworkdayjobs.com` host). The path
  taken and every failure along the way are recorded in the package's
  collection notes, so provenance never hides a fallback.
- Not built, needs its own approval: a Nimble-based fetch for sites that block
  all of the above. It would put a third-party service in the pipeline.

## Machine requirements

Python 3.12 or newer (3.14 works; `doctor` still prints a cosmetic FAIL on
its exact-3.12 check), Node + npm (ExcelJS pinned 4.4.0 under `tmp/`), git,
and outbound HTTPS to the target boards and api.github.com. No database, no
daemon; V1 runs are one-shot commands. Account briefs additionally need
Claude Code with web search, run from the repo root.
