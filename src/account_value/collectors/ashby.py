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
from account_value.parse import extract_bullets, extract_posted_pay_detail, html_to_text
from account_value.value_model import Bullet, JobPosting

API = "https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true"


def _posted_salary(posting: dict) -> tuple[int, int, int]:
    """Annual USD salary (min, max, mid) from Ashby's structured compensation; zeros if absent."""
    for comp in (posting.get("compensation") or {}).get("summaryComponents") or []:
        if (comp.get("compensationType") == "Salary" and comp.get("interval") == "1 YEAR"
                and comp.get("currencyCode") == "USD" and comp.get("minValue") and comp.get("maxValue")):
            low, high = int(comp["minValue"]), int(comp["maxValue"])
            return low, high, round((low + high) / 2)
    return 0, 0, 0


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
        pay_min, pay_max, pay_mid = _posted_salary(posting)
        pay_note = "structured compensation" if pay_mid else ""
        if not pay_mid:
            # Many Ashby boards put the band in the description text instead.
            pay = extract_posted_pay_detail(raw_html)
            pay_min, pay_max, pay_mid, pay_note = pay.min_usd, pay.max_usd, pay.mid_usd, pay.note
        jobs.append(JobPosting(
            job_id=posting.get("id", ""),
            title=posting.get("title", "").strip(),
            department=posting.get("department", "") or posting.get("team", ""),
            location=posting.get("location", "") or posting.get("office", ""),
            url=posting.get("jobUrl", "") or posting.get("applyUrl", ""),
            pay_min_posted=pay_min, pay_max_posted=pay_max, pay_mid_posted=pay_mid,
            pay_note=pay_note,
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
