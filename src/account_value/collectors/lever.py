"""Lever public postings collector (api.lever.co/v0/postings, no auth)."""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape as html_escape
from pathlib import Path

import httpx

from account_value.collectors.base import (
    CollectionResult,
    CollectorError,
    save_snapshot,
)
from account_value.parse import extract_bullets, extract_posted_pay_detail, html_to_text
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
        # Many Lever boards keep the real content in structured `lists` (e.g.
        # "Responsibilities:" with the full HTML body) rather than the free-form
        # description. Render each list as a heading followed by its content so
        # the responsibility-section parser can see those postings at all.
        for item in posting.get("lists") or []:
            heading = html_escape((item.get("text") or "").strip())
            content = item.get("content") or ""
            if heading and content:
                raw_html += f"\n<h3>{heading}</h3>\n{content}"
        text = html_to_text(raw_html) if "<" in raw_html else raw_html
        categories = posting.get("categories", {})
        # Lever boards usually print the pay range in the closing `additional`
        # block, outside the description and lists; read pay from all of it.
        pay = extract_posted_pay_detail(
            raw_html + "\n" + (posting.get("additionalPlain") or posting.get("additional") or "")
        )
        jobs.append(JobPosting(
            job_id=posting.get("id", ""),
            title=posting.get("text", "").strip(),
            department=categories.get("department", ""),
            location=categories.get("location", ""),
            first_published=str(posting.get("createdAt", "")),
            url=posting.get("applyUrl", "") or posting.get("hostedUrl", ""),
            pay_min_posted=pay.min_usd, pay_max_posted=pay.max_usd, pay_mid_posted=pay.mid_usd,
            pay_note=pay.note,
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
