"""Collector contract: immutable raw snapshots, reconciled posting counts.

Every collector saves the raw source payload to data/raw/ (never edited
afterward) and reconciles the advertised posting count against what it
parsed. A collector that cannot reach or parse a source raises
CollectorError; a source blocked by terms is recorded as terms_blocked,
never circumvented.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from account_value.parse import extract_bullets, extract_posted_pay, html_to_text
from account_value.value_model import Bullet, JobPosting


@dataclass
class CollectionResult:
    ats: str
    snapshot_path: Path
    snapshot_hash: str
    jobs: list[JobPosting]
    bullets: list[Bullet]
    advertised_count: int | None  # count the board itself claims, when knowable
    notes: list[str] = field(default_factory=list)

    @property
    def reconciled(self) -> bool:
        if self.advertised_count is None:
            return True
        return self.advertised_count == len(self.jobs)


class CollectorError(RuntimeError):
    pass


class TermsBlocked(CollectorError):
    """The source disallows automated retrieval; record, never circumvent."""


class UnsupportedCollector(CollectorError):
    pass


def save_snapshot(raw_dir: Path, name: str, payload: str) -> tuple[Path, str]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / name
    path.write_text(payload, encoding="utf-8")
    return path, hashlib.sha256(payload.encode()).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def postings_from_greenhouse_payload(payload: dict) -> tuple[list[JobPosting], list[Bullet]]:
    """Parse a Greenhouse boards-api payload (shared by the greenhouse and
    jsonld fallback collectors)."""
    jobs, bullets = [], []
    for job in payload.get("jobs", []):
        raw_html = job.get("content") or ""
        text = html_to_text(raw_html)
        pay_min, pay_max, pay_mid = extract_posted_pay(raw_html)
        jobs.append(JobPosting(
            job_id=str(job["id"]),
            title=job["title"].strip(),
            department="; ".join(d["name"] for d in job.get("departments", [])),
            location=job.get("location", {}).get("name", ""),
            language=job.get("language", ""),
            first_published=(job.get("first_published") or "")[:10],
            url=job.get("absolute_url", ""),
            pay_min_posted=pay_min, pay_max_posted=pay_max, pay_mid_posted=pay_mid,
        ))
        for seq, (section, bullet) in enumerate(extract_bullets(text), 1):
            bullets.append(Bullet(
                job_id=str(job["id"]), title=job["title"].strip(),
                department=jobs[-1].department, resp_seq=seq,
                section=section, verbatim_responsibility=bullet,
            ))
    return jobs, bullets


def jsonl_payload_text(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)
