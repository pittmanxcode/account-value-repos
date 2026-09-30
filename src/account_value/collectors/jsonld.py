"""JSON-LD career-page collector (schema.org JobPosting) with an HTML list fallback.

Many companies without an ATS expose structured or semi-structured postings on
their own careers pages. This collector fetches the page, extracts embedded
JSON-LD JobPosting items, and falls back to plain section parsing of the page
text. Pages are untrusted data: their text is parsed, never executed or
followed as instructions.
"""

from __future__ import annotations

import json
import re
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


def _extract_jsonld(raw_html: str) -> list[dict]:
    items: list[dict] = []
    for match in re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        raw_html, re.S | re.I,
    ):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            graph = candidate.get("@graph")
            if graph:
                candidates.extend(g for g in graph if isinstance(g, dict))
            if candidate.get("@type") in ("JobPosting", ["JobPosting"]):
                items.append(candidate)
    return items


def _responsibilities_from_jsonld(item: dict) -> list[str]:
    text = item.get("responsibilities") or ""
    if not text:
        return []
    cleaned = re.sub(r"<[^>]+>", "\n", text)
    return [ln.strip() for ln in cleaned.split("\n") if len(ln.strip()) > 25]


def collect(careers_url: str, raw_dir: Path, fetch=None) -> CollectionResult:
    fetcher = fetch or (lambda url: httpx.get(url, timeout=60, follow_redirects=True))
    response = fetcher(careers_url)
    response.raise_for_status()
    raw_html = response.text
    items = _extract_jsonld(raw_html)
    jobs, bullets = [], []
    for item in items:
        title = str(item.get("title") or item.get("name") or "").strip()
        if not title:
            continue
        job_id = str(item.get("identifier") or item.get("url") or title)
        location_field = item.get("jobLocation") or {}
        if isinstance(location_field, list):
            location_field = location_field[0] if location_field else {}
        location = ""
        if isinstance(location_field, dict):
            address = location_field.get("address") or {}
            if isinstance(address, dict):
                location = ", ".join(
                    str(address.get(k, "")) for k in ("addressLocality", "addressRegion")
                ).strip(", ")
        jobs.append(JobPosting(
            job_id=job_id, title=title, department=str(item.get("employmentUnit", "")) or "",
            location=location, url=str(item.get("url") or careers_url),
        ))
        for seq, resp_text in enumerate(_responsibilities_from_jsonld(item), 1):
            bullets.append(Bullet(
                job_id=job_id, title=title, department="", resp_seq=seq,
                section="responsibilities", verbatim_responsibility=resp_text,
            ))
    if not jobs:
        # HTML fallback: parse the page text for responsibility sections.
        text = html_to_text(raw_html)
        page_bullets = extract_bullets(text)
        if page_bullets:
            jobs.append(JobPosting(
                job_id="careers-page", title="Careers page postings", department="",
                location="", url=careers_url,
            ))
            for seq, (section, bullet) in enumerate(page_bullets, 1):
                bullets.append(Bullet(
                    job_id="careers-page", title="Careers page postings",
                    department="", resp_seq=seq, section=section,
                    verbatim_responsibility=bullet,
                ))
    if not jobs:
        raise CollectorError(
            f"no JSON-LD JobPosting items and no parseable sections at {careers_url}"
        )
    snapshot, digest = save_snapshot(raw_dir, "careers_page.html", raw_html)
    return CollectionResult(
        ats="jsonld",
        snapshot_path=snapshot,
        snapshot_hash=digest,
        jobs=jobs,
        bullets=bullets,
        advertised_count=None,
        notes=[f"source: {careers_url} at {datetime.now(UTC).isoformat(timespec='seconds')}"],
    )
