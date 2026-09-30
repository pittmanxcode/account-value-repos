"""Ashby public posting API collector (postings-api.ashbyhq.com, no auth)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx

from account_value.collectors.base import (
    CollectionResult,
    CollectorError,
    save_snapshot,
)
from account_value.parse import extract_bullets, html_to_text
from account_value.value_model import Bullet, JobPosting

API = "https://postings-api.ashbyhq.com/{token}"


def collect(token: str, raw_dir: Path, fetch=None) -> CollectionResult:
    fetcher = fetch or (lambda url: httpx.get(url, timeout=60, follow_redirects=True))
    url = API.format(token=token)
    response = fetcher(url)
    if response.status_code == 404:
        raise CollectorError(f"ashby org {token!r} not found (404)")
    response.raise_for_status()
    payload = response.json()
    jobs, bullets = [], []
    for posting in payload.get("jobs", []):
        raw_html = posting.get("descriptionHtml", "") or posting.get("descriptionPlain", "")
        text = html_to_text(raw_html)
        jobs.append(JobPosting(
            job_id=posting.get("id", ""),
            title=posting.get("title", "").strip(),
            department=posting.get("department", "") or posting.get("team", ""),
            location=posting.get("location", "") or posting.get("office", ""),
            url=posting.get("jobUrl", "") or posting.get("applyUrl", ""),
        ))
        for seq, (section, bullet) in enumerate(extract_bullets(text), 1):
            bullets.append(Bullet(
                job_id=jobs[-1].job_id, title=jobs[-1].title,
                department=jobs[-1].department, resp_seq=seq,
                section=section, verbatim_responsibility=bullet,
            ))
    snapshot, digest = save_snapshot(raw_dir, "ashby_postings.json", response.text)
    return CollectionResult(
        ats="ashby",
        snapshot_path=snapshot,
        snapshot_hash=digest,
        jobs=jobs,
        bullets=bullets,
        advertised_count=None,
        notes=[f"source: {url} at {datetime.now(UTC).isoformat(timespec='seconds')}"],
    )
