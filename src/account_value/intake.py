"""Hybrid CLI intake wizard for V1 (manual account intake).

Flags prefill and skip questions; anything missing is prompted interactively.
The confirmed request is saved as an editable YAML manifest before research
begins, so every run is auditable and rerunnable. The wizard never asks for
value components or modeling assumptions — you supply the account; the
system supplies the analysis.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from account_value.components import ValueComponent
from account_value.identity import AmbiguousIdentity, Identity, resolve
from account_value.pipeline import AccountRequest, slugify

REQUESTS_DIR = Path("requests")


def _interactive() -> bool:
    import sys

    return sys.stdin is not None and sys.stdin.isatty()


def _ask(prompt: str, default: str = "") -> str:
    if not _interactive():
        return default  # non-interactive run: accept defaults
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default


def _ask_yes_no(prompt: str, default: bool = False) -> bool:
    if not _interactive():
        return default  # non-interactive run: accept defaults
    suffix = " [Y/n]" if default else " [y/N]"
    answer = input(f"{prompt}{suffix}: ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def build_request(
    name: str | None = None,
    domain: str | None = None,
    careers_url: str | None = None,
    fetch=None,
) -> AccountRequest:
    """Hybrid intake: flags prefill, prompts fill the gaps, wizard confirms."""
    name = name or _ask("Company name")
    domain = domain or ""
    careers_url = careers_url or ""

    identity: Identity | None = None
    if not domain or not careers_url:
        print("\nResolving identity from public sources (deterministic probes)…")
        try:
            identity = resolve(name, domain=domain or None,
                               careers_url=careers_url or None, fetch=fetch)
        except AmbiguousIdentity as ambiguity:
            print(f"\n{ambiguity}")
            for index, candidate in enumerate(ambiguity.candidates, 1):
                print(f"  {index}. {candidate.canonical_domain} — site title: {candidate.legal_name!r}")
            choice = _ask("Pick the correct domain (number, or blank to type one)")
            if choice.isdigit() and 1 <= int(choice) <= len(ambiguity.candidates):
                identity = ambiguity.candidates[int(choice) - 1]
            else:
                domain = domain or _ask("Domain")
                identity = resolve(name, domain=domain, fetch=fetch)
        if identity:
            if not domain:
                domain = identity.canonical_domain
            if not careers_url:
                careers_url = identity.careers_url
            if identity.ats and not _ask_yes_no(
                f"Found a {identity.ats} board for {identity.canonical_domain}; use it?", True
            ):
                identity.ats, identity.ats_token = "", ""

    print("\n--- Confirm account request ---")
    print(f"  Company:     {name}")
    print(f"  Domain:      {domain or '(resolve automatically)'}")
    print(f"  Careers URL: {careers_url or '(discover automatically)'}")
    if not _ask_yes_no("Run the analysis with this identity?", True):
        raise SystemExit("cancelled at confirmation; nothing was run")

    request = AccountRequest(
        company_name=name,
        company_slug=slugify(name),
        domain=domain,
        careers_url=careers_url,
        ats=(identity.ats if identity else ""),
        ats_token=(identity.ats_token if identity else ""),
        origin="manual",
    )
    save_request(request)
    return request


def save_request(request: AccountRequest, path: Path | None = None) -> Path:
    path = path or (REQUESTS_DIR / f"{request.company_slug}.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(request.to_dict(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"request saved: {path} (rerun with: account-value run --request {path})")
    return path


def load_request(path: Path) -> AccountRequest:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    request = AccountRequest.from_dict(payload)
    request.company_slug = slugify(request.company_name)
    return request


def inherited_from_flags(component_rows: list[dict]) -> list[ValueComponent]:
    """CLI --inherited flag: JSON rows for pre-known compelling-event value."""
    components = []
    for index, row in enumerate(component_rows, 1):
        components.append(ValueComponent(
            component_id=row.get("component_id", f"manual-{index}"),
            origin="manual",
            description=row.get("description", "manually supplied compelling event"),
            work_surface=row.get("work_surface", f"manual_{index}"),
            saved_hours_annual=row.get("saved_hours_annual"),
            hard_cost_usd=row.get("hard_cost_usd"),
            signal_id=row.get("signal_id"),
            confidence=row.get("confidence", "unknown"),
            model_version="manual",
            overlap_key=row.get("overlap_key", ""),
        ))
    return components


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
