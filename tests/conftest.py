"""Shared fixtures: the golden Crunchyroll snapshot as an offline collection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from account_value.collectors.base import CollectionResult
from account_value.collectors.greenhouse import postings_from_greenhouse_payload

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "crunchyroll"


@pytest.fixture()
def fixture_collection() -> CollectionResult:
    snapshot = FIXTURE / "data" / "raw" / "greenhouse_board_snapshot.json"
    payload = snapshot.read_text(encoding="utf-8")
    data = json.loads(payload)
    jobs, bullets = postings_from_greenhouse_payload(data)
    return CollectionResult(
        ats="greenhouse",
        snapshot_path=snapshot,
        snapshot_hash=hashlib.sha256(payload.encode()).hexdigest(),
        jobs=jobs,
        bullets=bullets,
        advertised_count=data.get("meta", {}).get("total"),
    )


@pytest.fixture()
def fixture_title_overrides() -> dict[str, tuple[str, str]]:
    from account_value.pay import load_title_overrides

    return load_title_overrides(FIXTURE / "pay_title_map.yaml")


@pytest.fixture()
def no_network():
    def _fail(url: str):
        raise AssertionError(f"unexpected network fetch: {url}")

    return _fail
