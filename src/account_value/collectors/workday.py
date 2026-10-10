"""Workday: the public JSON endpoints behind every myworkdayjobs.com careers site.

The careers page itself loads its listings from
``/wday/cxs/{tenant}/{site}/jobs`` (POST, paged by 20) and each posting from
``/wday/cxs/{tenant}/{site}{externalPath}`` (GET). Both are unauthenticated and
read-only; this collector uses them the same way the page does, with a small
delay between posting fetches, and records the list total as the advertised
count so the reconciliation gate still applies.

Policy change 2026-10-10, approved by Michael: the earlier version of this
module refused Workday outright. That refusal cited no terms; the endpoint is
public and first-party, the same class of source as Greenhouse or Ashby.

Token: the careers URL (``https://turo.wd12.myworkdayjobs.com/Turo_careers``)
or ``tenant.wdN/site``. A bare site name is not enough to build the host.
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from account_value.collectors.base import CollectionResult, CollectorError, save_snapshot
from account_value.parse import extract_bullets, extract_posted_pay, html_to_text
from account_value.value_model import Bullet, JobPosting

PAGE_SIZE = 20
DETAIL_DELAY_SECONDS = 0.15
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "account-value/0.1 (+careers research; read-only)",
}
_URL = re.compile(
    r"^(?:https?://)?(?P<tenant>[a-z0-9-]+)\.(?P<wd>wd\d+)\.myworkdayjobs\.com"
    r"/(?:[a-z]{2}-[A-Z]{2}/)?(?P<site>[^/?#]+)",
    re.I,
)
_SHORT = re.compile(r"^(?P<tenant>[a-z0-9-]+)\.(?P<wd>wd\d+)/(?P<site>[^/?#]+)$", re.I)


def parse_token(token: str) -> tuple[str, str, str]:
    """Return (base_url, tenant, site) from a careers URL or ``tenant.wdN/site``."""
    m = _URL.match(token.strip()) or _SHORT.match(token.strip())
    if not m:
        raise CollectorError(
            f"workday token {token!r} must be the careers URL "
            "(https://<tenant>.wd<N>.myworkdayjobs.com/<site>) or <tenant>.wd<N>/<site>"
        )
    tenant, wd, site = m.group("tenant"), m.group("wd"), m.group("site")
    return f"https://{tenant}.{wd}.myworkdayjobs.com", tenant, site


def _default_fetch(client: httpx.Client):
    def fetch(url: str, *, method: str = "GET", json_body: dict | None = None):
        return client.request(method, url, json=json_body)

    return fetch


def collect(token: str, raw_dir: Path, fetch=None) -> CollectionResult:
    base, tenant, site = parse_token(token)
    api = f"{base}/wday/cxs/{tenant}/{site}"
    client = None
    if fetch is None:
        client = httpx.Client(timeout=60, headers=HEADERS, follow_redirects=True)
        fetch = _default_fetch(client)
    try:
        return _collect(api, base, site, raw_dir, fetch, polite=client is not None)
    finally:
        if client is not None:
            client.close()


def _collect(api: str, base: str, site: str, raw_dir: Path, fetch, polite: bool) -> CollectionResult:
    summaries: list[dict] = []
    total: int | None = None
    offset = 0
    while True:
        body = {"appliedFacets": {}, "limit": PAGE_SIZE, "offset": offset, "searchText": ""}
        response = fetch(f"{api}/jobs", method="POST", json_body=body)
        if response.status_code == 404:
            raise CollectorError(f"workday site {site!r} not found at {api}/jobs (404)")
        response.raise_for_status()
        page = response.json()
        if total is None:
            total = int(page.get("total") or 0)
        batch = page.get("jobPostings") or []
        summaries.extend(batch)
        offset += PAGE_SIZE
        if not batch or offset >= total:
            break

    jobs, bullets, details = [], [], []
    for summary in summaries:
        path = summary.get("externalPath") or ""
        if not path:
            continue
        response = fetch(f"{api}{path}")
        response.raise_for_status()
        info = (response.json() or {}).get("jobPostingInfo") or {}
        details.append(info)
        raw_html = info.get("jobDescription") or ""
        text = html_to_text(raw_html)
        pay_min, pay_max, pay_mid = extract_posted_pay(raw_html)
        job = JobPosting(
            job_id=str(info.get("jobReqId") or info.get("id") or path),
            title=(info.get("title") or summary.get("title") or "").strip(),
            department="",  # Workday's public payload carries no department
            location=info.get("location") or summary.get("locationsText") or "",
            first_published=(info.get("startDate") or "")[:10],
            url=info.get("externalUrl") or f"{base}/{site}{path}",
            pay_min_posted=pay_min, pay_max_posted=pay_max, pay_mid_posted=pay_mid,
        )
        jobs.append(job)
        for seq, (section, bullet) in enumerate(extract_bullets(text), 1):
            bullets.append(Bullet(
                job_id=job.job_id, title=job.title, department=job.department,
                resp_seq=seq, section=section, verbatim_responsibility=bullet,
            ))
        if polite:
            time.sleep(DETAIL_DELAY_SECONDS)

    retrieved = datetime.now(UTC).isoformat(timespec="seconds")
    payload = json.dumps(
        {"source": f"{api}/jobs", "retrieved_at": retrieved, "total": total, "jobs": details},
        ensure_ascii=False,
    )
    snapshot, digest = save_snapshot(raw_dir, "workday_postings.json", payload)
    return CollectionResult(
        ats="workday",
        snapshot_path=snapshot,
        snapshot_hash=digest,
        jobs=jobs,
        bullets=bullets,
        advertised_count=total,
        notes=[f"source: Workday public JSON {api}/jobs at {retrieved}; "
               f"{len(details)} postings fetched one by one"],
    )
