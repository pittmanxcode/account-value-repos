"""Identity resolution: a typed company name becomes verified identity.

Deterministic probes first (candidate domains, common careers paths, ATS
board-token guesses). When the deterministic layer is ambiguous, the CLI
wizard presents the sourced candidates for human confirmation — the only
manual step in V1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx


class IdentityError(RuntimeError):
    pass


class AmbiguousIdentity(IdentityError):
    def __init__(self, message: str, candidates: list[Identity]):
        super().__init__(message)
        self.candidates = candidates


@dataclass
class Identity:
    legal_name: str
    canonical_domain: str
    careers_url: str = ""
    ats: str = ""
    ats_token: str = ""
    evidence: list[dict] = field(default_factory=list)
    verified: bool = False

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _slug_tokens(name: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", name.lower())
    words = [w for w in words if w not in {"inc", "llc", "ltd", "corp", "corporation",
                                           "company", "co", "the", "group", "holdings"}]
    return words or re.findall(r"[a-z0-9]+", name.lower())


def _domain_candidates(name: str) -> list[str]:
    words = _slug_tokens(name)
    joined = "".join(words)
    dashed = "-".join(words)
    cands = [f"{joined}.com", f"{dashed}.com", f"{joined}.io", f"{joined}.co"]
    if words:
        cands.append(f"{words[0]}.com")
    return list(dict.fromkeys(cands))


_CAREERS_PATHS = ["", "/careers", "/careers/", "/jobs", "/about/jobs", "/company/careers"]

# Probe order for ATS discovery: (ats, url_template, token_hint)
_ATS_PROBES = [
    ("greenhouse", "https://boards-api.greenhouse.io/v1/boards/{token}/jobs", "joined"),
    ("lever", "https://api.lever.co/v0/postings/{token}?mode=json", "joined"),
    ("ashby", "https://postings-api.ashbyhq.com/{token}", "joined"),
]


def verify_domain(domain: str, fetch=None) -> Identity | None:
    """HTTPS probe: the domain is live if it returns any HTTP response.

    A 403 (bot wall) still proves the domain exists; content corroboration
    (title matching the name) only happens when the body is readable.
    """
    fetcher = fetch or (lambda url: httpx.get(url, timeout=20, follow_redirects=True))
    url = f"https://{domain}"
    try:
        response = fetcher(url)
    except Exception:  # noqa: BLE001 - a failed probe is not an error, just a miss
        return None
    body = getattr(response, "text", "") or ""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
    title = html_unescape(title_match.group(1)) if title_match else ""
    bot_blocked = getattr(response, "status_code", 0) in (401, 403, 429)
    evidence = [{
        "url": url,
        "verbatim_quote": title.strip()[:300]
        or f"HTTP {getattr(response, 'status_code', '?')} (live domain)",
        "source_role": "Q",
        "label": "bot-blocked, domain live" if bot_blocked else "observed",
        "retrieval_time": _now(),
        "content_hash": "",
    }]
    return Identity(
        legal_name=title.strip() or domain,
        canonical_domain=domain,
        careers_url=url,
        evidence=evidence,
        verified=True,
    )


def html_unescape(text: str) -> str:
    import html as _html

    return _html.unescape(re.sub(r"\s+", " ", text)).strip()


def discover_careers(identity: Identity, fetch=None) -> Identity:
    """Probe common careers paths and public ATS boards."""
    fetcher = fetch or (lambda url: httpx.get(url, timeout=20, follow_redirects=True))
    domain = identity.canonical_domain
    for path in _CAREERS_PATHS:
        url = f"https://{domain}{path}"
        try:
            response = fetcher(url)
            if response.status_code == 200 and len(response.text) > 200:
                identity.careers_url = url
                identity.evidence.append({
                    "url": url, "verbatim_quote": "careers page reachable",
                    "source_role": "Q", "label": "observed", "retrieval_time": _now(),
                    "content_hash": "",
                })
                break
        except Exception:  # noqa: BLE001
            continue
    tokens = _slug_tokens(identity.legal_name)
    token = "".join(tokens) if tokens else domain.split(".")[0]
    for ats, template, _hint in _ATS_PROBES:
        probe_url = template.format(token=token)
        try:
            response = fetcher(probe_url)
        except Exception:  # noqa: BLE001
            continue
        if response.status_code == 200:
            identity.ats = ats
            identity.ats_token = token
            break
    return identity


def resolve(
    name: str,
    domain: str | None = None,
    careers_url: str | None = None,
    fetch=None,
) -> Identity:
    """Resolve one identity. Raises AmbiguousIdentity with sourced candidates
    when the deterministic probes cannot decide."""
    fetcher = fetch or (lambda url: httpx.get(url, timeout=20, follow_redirects=True))
    if domain:
        verified = verify_domain(domain, fetch=fetcher)
        if verified is None:
            raise IdentityError(f"provided domain {domain!r} did not respond over HTTPS")
        name_tokens = {w for w in _slug_tokens(name)}
        title_tokens = set(_slug_tokens(verified.legal_name))
        if name_tokens and title_tokens and not (name_tokens & title_tokens):
            verified.legal_name = name  # title did not corroborate; keep the typed name
        verified.legal_name = verified.legal_name or name
        if careers_url:
            verified.careers_url = careers_url
        return discover_careers(verified, fetch=fetcher)

    resolved: list[Identity] = []
    for candidate in _domain_candidates(name):
        verified = verify_domain(candidate, fetch=fetcher)
        if verified is None:
            continue
        name_tokens = set(_slug_tokens(name))
        title_tokens = set(_slug_tokens(verified.legal_name))
        verified.legal_name = name
        if name_tokens & title_tokens:
            resolved = [verified]  # title corroborates the name: decisive
            break
        resolved.append(verified)
    if not resolved:
        raise IdentityError(
            f"no responsive domain for {name!r}; supply --domain or --careers-url"
        )
    if len(resolved) > 1:
        raise AmbiguousIdentity(
            f"multiple candidate domains respond for {name!r}; pick one",
            resolved,
        )
    identity = resolved[0]
    if careers_url:
        identity.careers_url = careers_url
    return discover_careers(identity, fetch=fetcher)
