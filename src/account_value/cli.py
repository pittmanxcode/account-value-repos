"""CLI entry points: `account-value run` (V1) and `account-value well …` (V2)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from account_value import MODEL_VERSION
from account_value.pipeline import failure_report, run_account, slugify


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="account-value",
        description="Account value repositories: one pipeline, two intake loops",
    )
    parser.add_argument("--version", action="version", version=f"account-value {MODEL_VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="V1: name an account; the pipeline does the rest")
    run_cmd.add_argument("name", nargs="?", help="company display name")
    run_cmd.add_argument("--domain", help="known official domain (skips resolution)")
    run_cmd.add_argument("--careers-url", help="known careers page or board URL")
    run_cmd.add_argument("--inherited", help="JSON file with inherited compelling-event components")
    run_cmd.add_argument("--request", dest="request_file", help="rerun from a saved request YAML")
    run_cmd.add_argument("--dry-run", action="store_true",
                         help="run everything locally; skip branch/PR publication")
    run_cmd.add_argument("--workspace", default=".", help="workspace root (default: cwd)")

    well = sub.add_parser("well", help="V2: buyer-readiness well intake (disabled by default)")
    well_sub = well.add_subparsers(dest="well_command", required=True)
    for name in ("doctor", "plan", "run"):
        well_parser = well_sub.add_parser(name)
        well_parser.add_argument("--exports-dir", default=None)
        well_parser.add_argument("--limit", type=int, default=None)

    doctor = sub.add_parser("doctor", help="preflight for this machine")
    doctor.add_argument("--workspace", default=".")

    brief = sub.add_parser(
        "brief-context",
        help="gather a finished package's postings and numbers into brief-context.md",
    )
    brief.add_argument("slug", help="account slug under accounts/")
    brief.add_argument("--workspace", default=".")

    args = parser.parse_args(argv)

    if args.command == "brief-context":
        from account_value.brief_context import write_context

        package_dir = Path(args.workspace) / "accounts" / args.slug
        if not (package_dir / "account-value.json").exists():
            print(f"no package at {package_dir}; run `account-value run` first")
            return 1
        print(write_context(package_dir))
        return 0

    if args.command == "well":
        from account_value.well import commands

        if args.well_command == "doctor":
            return commands.doctor(Path(args.exports_dir) if args.exports_dir else None)
        if args.well_command == "plan":
            return commands.plan(Path(args.exports_dir) if args.exports_dir else None, args.limit)
        return commands.run(Path(args.exports_dir) if args.exports_dir else None, args.limit)

    if args.command == "doctor":
        return _doctor(Path(args.workspace))

    return _run(args)


def _run(args) -> int:
    from account_value.intake import build_request, inherited_from_flags, load_request
    from account_value.pipeline import AccountRequest

    workspace = Path(args.workspace)
    request: AccountRequest | None = None
    try:
        if args.request_file:
            request = load_request(Path(args.request_file))
        else:
            inherited = []
            if args.inherited:
                inherited = inherited_from_flags(
                    json.loads(Path(args.inherited).read_text(encoding="utf-8"))
                )
            request = build_request(args.name, args.domain, args.careers_url)
            request.inherited_components = inherited
            request.company_slug = slugify(request.company_name)
        result = run_account(request, workspace)
        if result.validation_passed:
            if args.dry_run:
                print(f"dry run: package ready at {result.package_dir} (no PR opened)")
                return 0
            from account_value.publish import publish_package

            publish = publish_package(
                package_dir=result.package_dir,
                commit_message=f"account value: {request.company_name} (validated)",
                pr_title=f"Account value: {request.company_name}",
                pr_body=(
                    f"Validated account-value package for **{request.company_name}**\n\n"
                    f"- Identity: {request.domain or '(auto-resolved)'}\n"
                    f"- Postings: {len(result.model['roles'])}\n"
                    f"- Validation: passed (report in the package)\n\n"
                    "Merging approves this account for the future contact-search handoff "
                    "(handoff/contact-search.v1.jsonl). Review the workbook before merging."
                ),
                company_slug=request.company_slug,
            )
            print(f"published: branch {publish.branch} -> {publish.pr_url or '(no PR)'}")
            return 0
        print(
            f"validation FAILED — package kept locally at {result.package_dir}, "
            "nothing published. See validation-report.txt."
        )
        return 1
    except SystemExit:
        raise
    except Exception as error:  # noqa: BLE001 - CLI boundary
        if request is None:
            request = AccountRequest(
                company_name=args.name or "unknown",
                company_slug=slugify(args.name or "unknown"),
            )
        path = failure_report(workspace, request, error)
        print(f"failure: {error}\nfailure report: {path} (nothing published)")
        return 1


def _doctor(workspace: Path) -> int:
    ok = True

    def check(label: str, passed: bool, detail: str = "") -> None:
        nonlocal ok
        if not passed:
            ok = False
        print(f"  {'ok' if passed else 'FAIL'}  {label}" + (f" — {detail}" if detail else ""))

    print(f"account-value {MODEL_VERSION} doctor")
    import shutil

    check("python 3.12", sys.version_info[:2] == (3, 12),
          f"found {sys.version_info.major}.{sys.version_info.minor}")
    check("node available (workbook conversion)", shutil.which("node") is not None)
    exceljs = Path(workspace) / "tmp" / "node_modules" / "exceljs"
    check("exceljs installed under tmp/ (make setup)", exceljs.exists(), str(exceljs))
    registry = Path(workspace) / "registry" / "signals.yaml"
    check("signal registry present", registry.exists(), str(registry))
    token = "ACCOUNT_VALUE_GITHUB_TOKEN" in __import__("os").environ
    check("ACCOUNT_VALUE_GITHUB_TOKEN set (publication)", token,
          "required for PR publication; dry runs work without it")
    print("doctor:", "READY" if ok else "NOT READY — fix the FAIL lines above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
