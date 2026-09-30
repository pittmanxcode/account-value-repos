"""V2 commands: well doctor / plan / run.

Implemented and tested now; `well run` publication is blocked by config
(well_enabled: false) until the well's own data pipeline matures and someone
explicitly flips the setting.
"""

from pathlib import Path

from account_value.config import load_config
from account_value.well.adapter import load_export, select_candidates, to_request


def doctor(exports_dir: Path | None = None) -> int:

    config = load_config()
    directory = Path(exports_dir or (Path.cwd() / config.well_exports_dir))
    export = load_export(directory)
    print("well adapter doctor")
    print(f"  exports dir: {directory}")
    print(f"  accounts in export: {len(export.accounts)}")
    print(f"  receipt: {'present' if export.receipt else 'MISSING'}")
    for failure in export.readiness.failures[:10]:
        print(f"  FAIL  {failure}")
    if len(export.readiness.failures) > 10:
        print(f"  … and {len(export.readiness.failures) - 10} more")
    for warning in export.readiness.warnings[:5]:
        print(f"  warn  {warning}")
    print("doctor:", "READY" if export.readiness.ready else "NOT READY (V2 stays disabled)")
    return 0 if export.readiness.ready else 1


def plan(exports_dir: Path | None = None, limit: int | None = None) -> int:
    config = load_config()
    directory = Path(exports_dir or (Path.cwd() / config.well_exports_dir))
    export = load_export(directory)
    if not export.readiness.ready:
        print("cannot plan: the well export fails its readiness gate")
        for failure in export.readiness.failures[:10]:
            print(f"  FAIL  {failure}")
        return 1
    candidates = select_candidates(export, limit or config.batch_size, set())
    print(f"selected {len(candidates)} candidate(s):")
    for account in candidates:
        request = to_request(account)
        print(f"  - {request.company_name} ({request.domain})")
    return 0


def run(exports_dir: Path | None = None, limit: int | None = None) -> int:
    config = load_config()
    if not config.well_enabled:
        print(
            "well run: publication is DISABLED by config (well_enabled: false).\n"
            "The buyer-readiness well has not yet produced trustworthy qualified"
            " accounts. Fix upstream, then set well_enabled: true in config.yaml."
        )
        return 1
    print("well run: enabled path not scheduled in this phase (spec: no scheduler)")
    return 1
