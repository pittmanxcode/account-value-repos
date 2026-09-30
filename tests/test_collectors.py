"""Collectors: parsing, reconciliation, terms-blocked honesty."""

import json
from pathlib import Path

import pytest

from account_value.collectors import collect as run_collector
from account_value.collectors.base import (
    CollectorError,
    TermsBlocked,
    UnsupportedCollector,
)


class FakeResponse:
    def __init__(self, status_code=200, text="{}", payload=None):
        self.status_code = status_code
        self._text = text
        self._payload = payload

    def json(self):
        if self._payload is not None:
            return self._payload
        return json.loads(self._text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise CollectorError(f"HTTP {self.status_code}")

    @property
    def text(self):
        return self._text


def test_greenhouse_fixture_parses_and_reconciles(fixture_collection):
    assert fixture_collection.reconciled
    assert len(fixture_collection.jobs) == 77
    assert len(fixture_collection.bullets) == 964


def test_greenhouse_404_raises(tmp_path):
    with pytest.raises(CollectorError, match="not found"):
        run_collector("greenhouse", "missing-org", tmp_path,
                      fetch=lambda url: FakeResponse(status_code=404, text="{}"))


def test_workday_is_honestly_terms_blocked(tmp_path):
    with pytest.raises(TermsBlocked):
        run_collector("workday", "tenant", tmp_path)


def test_unsupported_ats_raises(tmp_path):
    with pytest.raises(UnsupportedCollector):
        run_collector("smartrecruiters", "x", tmp_path)


def test_jsonld_extract():
    page = """
    <html><head>
    <script type="application/ld+json">
    {"@type":"JobPosting","title":"Backend Engineer","identifier":"b1",
     "url":"https://x/jobs/1",
     "responsibilities":"<p>Build backend services and debug production issues</p>"}
    </script></head></html>"""
    result = run_collector("jsonld", "https://x/careers", Path("tmp"),
                           fetch=lambda url: FakeResponse(text=page))
    assert len(result.jobs) == 1
    assert result.jobs[0].title == "Backend Engineer"
    assert "Build backend services" in result.bullets[0].verbatim_responsibility


def test_jsonld_falls_back_to_page_sections():
    page = "<html><body><h2>Key Responsibilities</h2><p>Build and ship backend services daily here</p></body></html>"
    result = run_collector("jsonld", "https://x/careers", Path("tmp"),
                           fetch=lambda url: FakeResponse(text=page))
    assert result.jobs
    assert result.bullets


def test_jsonld_no_postings_raises():
    with pytest.raises(CollectorError, match="no JSON-LD"):
        run_collector("jsonld", "https://x/careers", Path("tmp"),
                      fetch=lambda url: FakeResponse(text="<html><body>hi</body></html>"))


def test_lever_parses_plain_text(tmp_path):
    payload = [{
        "id": "l1", "text": "Backend Engineer",
        "categories": {"department": "Eng", "location": "US"},
        "applyUrl": "https://jobs.lever.co/x/l1",
        "descriptionPlain": "Key Responsibilities\n- Build backend services and debug production issues\n",
    }]
    result = run_collector("lever", "xco", tmp_path,
                           fetch=lambda url: FakeResponse(payload=payload))
    assert result.jobs[0].title == "Backend Engineer"
    assert any("backend" in b.verbatim_responsibility for b in result.bullets)
