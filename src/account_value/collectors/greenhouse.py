"""Greenhouse public board collector (no auth, terms-friendly boards-api)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx

from account_value.collectors.base import (
    CollectionResult,
    CollectorError,
    postings_from_greenhouse_payload,
    save_snapshot,
)

API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


def collect(token: str, raw_dir: Path, fetch=None) -> CollectionResult:
    fetcher = fetch or (lambda url: httpx.get(url, timeout=60, follow_redirects=True))
    url = API.format(token=token)
    response = fetcher(url)
    if response.status_code == 404:
        raise CollectorError(f"greenhouse board {token!r} not found (404)")
    response.raise_for_status()
    payload = response.json()
    jobs, bullets = postings_from_greenhouse_payload(payload)
    snapshot, digest = save_snapshot(raw_dir, "greenhouse_board_snapshot.json", response.text)
    return CollectionResult(
        ats="greenhouse",
        snapshot_path=snapshot,
        snapshot_hash=digest,
        jobs=jobs,
        bullets=bullets,
        advertised_count=payload.get("meta", {}).get("total"),
        notes=[f"source: {url} at {datetime.now(UTC).isoformat(timespec='seconds')}"],
    )

