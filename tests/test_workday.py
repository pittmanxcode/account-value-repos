import json

import pytest

from account_value.collectors import CollectorError
from account_value.collectors import collect as run_collector
from account_value.collectors.workday import parse_token
from account_value.pipeline import AccountRequest, collect_with_fallback

LIST = {
    "total": 2,
    "jobPostings": [
        {"title": "Staff Data Engineer", "externalPath": "/job/SF/Staff-Data-Engineer_R-1",
         "locationsText": "San Francisco", "postedOn": "Posted Today"},
        {"title": "Account Executive", "externalPath": "/job/NY/AE_R-2",
         "locationsText": "New York", "postedOn": "Posted Yesterday"},
    ],
}
DETAIL = {
    "/job/SF/Staff-Data-Engineer_R-1": {"jobPostingInfo": {
        "id": "abc", "title": "Staff Data Engineer", "location": "San Francisco",
        "startDate": "2026-10-09", "jobReqId": "R-1",
        "externalUrl": "https://turo.wd12.myworkdayjobs.com/Turo_careers/job/SF/Staff-Data-Engineer_R-1",
        "jobDescription": "<h2>Responsibilities</h2><ul><li>Build the data platform on Kubernetes</li>"
                          "<li>Own on-call for ingestion pipelines</li></ul>"
                          "<h2>Compensation</h2><p>Base salary range: $180,000 - $220,000</p>",
    }},
    "/job/NY/AE_R-2": {"jobPostingInfo": {
        "id": "def", "title": "Account Executive", "location": "New York",
        "startDate": "2026-10-08", "jobReqId": "R-2",
        "externalUrl": "https://turo.wd12.myworkdayjobs.com/Turo_careers/job/NY/AE_R-2",
        "jobDescription": "<h2>What you'll do</h2><ul><li>Close enterprise deals</li></ul>",
    }},
}
API = "https://turo.wd12.myworkdayjobs.com/wday/cxs/turo/Turo_careers"


class Resp:
    def __init__(self, payload, status_code=200):
        self._payload, self.status_code = payload, status_code
        self.text = json.dumps(payload) if not isinstance(payload, str) else payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise CollectorError(f"HTTP {self.status_code}")


def fake_fetch(url, method="GET", json_body=None):
    if url == f"{API}/jobs" and method == "POST":
        assert json_body["limit"] == 20
        return Resp(LIST if json_body["offset"] == 0 else {"total": 2, "jobPostings": []})
    for path, detail in DETAIL.items():
        if url == f"{API}{path}":
            return Resp(detail)
    return Resp("<html>blocked</html>", status_code=403)


def test_parse_token_accepts_url_and_short_form():
    assert parse_token("https://turo.wd12.myworkdayjobs.com/Turo_careers") == (
        "https://turo.wd12.myworkdayjobs.com", "turo", "Turo_careers")
    assert parse_token("https://clio.wd3.myworkdayjobs.com/en-US/ClioCareerSite/job/x")[2] == "ClioCareerSite"
    assert parse_token("healthcatalyst.wd1/healthcatalystcareers")[1] == "healthcatalyst"
    with pytest.raises(CollectorError, match="careers URL"):
        parse_token("Turo_careers")


def test_workday_collects_postings_bullets_and_pay(tmp_path):
    result = run_collector("workday", "https://turo.wd12.myworkdayjobs.com/Turo_careers",
                           tmp_path, fetch=fake_fetch)
    assert result.ats == "workday" and result.advertised_count == 2 and result.reconciled
    assert [j.job_id for j in result.jobs] == ["R-1", "R-2"]
    # The salary line under the Compensation heading is read from the text.
    assert (result.jobs[0].pay_min_posted, result.jobs[0].pay_mid_posted) == (180000, 200000)
    assert result.jobs[0].pay_note == "text"
    assert result.jobs[0].first_published == "2026-10-09"
    assert [b.verbatim_responsibility for b in result.bullets if b.job_id == "R-1"] == [
        "Build the data platform on Kubernetes", "Own on-call for ingestion pipelines"]
    snapshot = json.loads(result.snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["total"] == 2 and len(snapshot["jobs"]) == 2
    assert "Workday public JSON" in result.notes[0]


def test_primary_collector_runs_first_and_workday_is_only_a_fallback(tmp_path):
    # No ATS configured: the prebuilt JSON-LD path runs first, fails on the
    # Workday-hosted page (403), and only then does the Workday collector run.
    request = AccountRequest(company_name="Turo", company_slug="turo",
                             careers_url="https://turo.wd12.myworkdayjobs.com/Turo_careers")
    result = collect_with_fallback(request, None, tmp_path, fetch=fake_fetch)
    assert result.ats == "workday" and len(result.jobs) == 2
    assert any(n.startswith("fallback: workday used after primary failed — jsonld")
               for n in result.notes)


def test_no_fallback_for_non_workday_hosts(tmp_path):
    request = AccountRequest(company_name="Clio", company_slug="clio",
                             careers_url="https://www.clio.com/about/careers/search/")
    with pytest.raises(CollectorError, match="all collection paths failed: jsonld"):
        collect_with_fallback(request, None, tmp_path, fetch=fake_fetch)
