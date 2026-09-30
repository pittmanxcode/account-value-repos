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

## Machine requirements

Python 3.12, Node + npm (ExcelJS pinned 4.4.0 under `tmp/`), git, and
outbound HTTPS to the target boards and api.github.com. No database, no
daemon; V1 runs are one-shot commands.
