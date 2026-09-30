"""Lever public postings collector (api.lever.co/v0/postings, no auth)."""

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

API = "https://api.lever.co/v0/postings/{token}?mode=json"


def collect(token: str, raw_dir: Path, fetch=None) -> CollectionResult:
    fetcher = fetch or (lambda url: httpx.get(url, timeout=60, follow_redirects=True))
    url = API.format(token=token)
    response = fetcher(url)
    if response.status_code == 404:
        raise CollectorError(f"lever org {token!r} not found (404)")
    response.raise_for_status()
    payload = response.json()
    jobs, bullets = [], []
    for posting in payload:
        raw_html = posting.get("descriptionPlain", "") or posting.get("description", "")
        text = html_to_text(raw_html) if "<" in raw_html else raw_html
        categories = posting.get("categories", {})
        jobs.append(JobPosting(
            job_id=posting.get("id", ""),
            title=posting.get("text", "").strip(),
            department=categories.get("department", ""),
            location=categories.get("location", ""),
            first_published=str(posting.get("createdAt", "")),
            url=posting.get("applyUrl", "") or posting.get("hostedUrl", ""),
        ))
        # Lever text is plain; extract_bullets' virtual-heading detection
        # finds responsibility sections without markup.
        for seq, (section, bullet) in enumerate(extract_bullets(text), 1):
            bullets.append(Bullet(
                job_id=jobs[-1].job_id, title=jobs[-1].title,
                department=jobs[-1].department, resp_seq=seq,
                section=section, verbatim_responsibility=bullet,
            ))
    snapshot, digest = save_snapshot(raw_dir, "lever_postings.json", response.text)
    return CollectionResult(
        ats="lever",
        snapshot_path=snapshot,
        snapshot_hash=digest,
        jobs=jobs,
        bullets=bullets,
        advertised_count=None,  # Lever exposes no board-level count
        notes=[f"source: {url} at {datetime.now(UTC).isoformat(timespec='seconds')}"],
    )
