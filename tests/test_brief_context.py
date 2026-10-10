import json
from pathlib import Path

from account_value.brief_context import _posting_texts, build_context, write_context

ROLE_HEADER = (
    "job_id,title,department,location,url,occupation_soc,occupation,seniority,"
    "us_equiv_base_pay,pay_source,posted_range,hourly_equiv,loaded_hourly_equiv,"
    "role_hours_annual,saved_hours_conservative,saved_hours_base,saved_hours_upside,"
    "saved_value_base,pct_capacity_freed_base\n"
)


def _package(tmp_path: Path, ats: str, snapshot_name: str, payload) -> Path:
    pkg = tmp_path / "accounts" / "acme"
    (pkg / "data" / "raw").mkdir(parents=True)
    (pkg / "data" / "processed").mkdir(parents=True)
    (pkg / "data" / "raw" / snapshot_name).write_text(json.dumps(payload), encoding="utf-8")
    (pkg / "account-value.json").write_text(json.dumps({
        "generated_at": "2026-10-09T00:00:00+00:00",
        "request": {"company_name": "Acme", "domain": "acme.com", "careers_url": "https://acme.com/jobs"},
        "collection": {"ats": ats, "snapshot": snapshot_name, "snapshot_hash": "abc123def456789"},
    }), encoding="utf-8")
    (pkg / "data" / "processed" / "role_summary.csv").write_text(
        ROLE_HEADER
        + "1,Staff Engineer,Eng,Remote,u,15-1252.00,Software Developers,staff,"
          "250000,posted pay range,,130,169,1920,100,200,300,33800,10.4\n"
        + "2,Account Executive,Sales,NYC,u,13-2011.00,Sales,senior,"
          "150000,posted pay range,,78,101,1920,50,100,150,10100,5.2\n",
        encoding="utf-8",
    )
    return pkg


ASHBY = {"jobs": [{
    "title": "Staff Engineer", "department": "Eng", "location": "Remote",
    "jobUrl": "https://jobs/1", "publishedAt": "2026-05-01T00:00:00Z",
    "descriptionHtml": "<h2>About</h2><p>We run 100M background jobs per day on "
                       "Kubernetes and Postgres.</p><ul><li>5+ years of experience</li></ul>",
}]}


def test_ashby_context_quotes_figures_and_splits_engineering(tmp_path):
    pkg = _package(tmp_path, "ashby", "ashby_postings.json", ASHBY)
    text = build_context(pkg)
    assert "# Acme — brief context" in text
    assert "Saved hours, all 2 roles: 300 h/yr" in text
    assert "engineering roles only (SOC 15-xxxx, 1 roles): 200 h/yr · $33,800" in text
    assert "- [Staff Engineer] We run 100M background jobs per day" in text
    assert "5+ years of experience" not in text.split("## Technology")[0].split("## Figures")[1]
    assert "- kubernetes: 1 posting(s) — Staff Engineer" in text
    assert "- postgres: 1 posting(s)" in text
    assert "### Staff Engineer" in text and "## About" in text


def test_greenhouse_and_lever_readers_normalize_text():
    gh = {"jobs": [{
        "title": "SRE", "departments": [{"name": "Infra"}], "location": {"name": "SF"},
        "absolute_url": "https://gh/1", "first_published": "2026-01-02T00:00:00",
        "content": "&lt;p&gt;On-call for 40 services on AWS.&lt;/p&gt;",
    }]}
    [p] = _posting_texts("greenhouse", gh)
    assert p["department"] == "Infra" and p["published"] == "2026-01-02"
    assert "On-call for 40 services on AWS." in p["text"]

    lever = [{
        "text": "Backend Engineer", "categories": {"department": "Eng", "location": "Remote"},
        "hostedUrl": "https://lever/1", "createdAt": 1700000000000,
        "descriptionPlain": "Join us.",
        "lists": [{"text": "Responsibilities", "content": "<li>Migrate off Rails 6</li>"}],
        "additionalPlain": "We are an equal opportunity employer.",
    }]
    [p] = _posting_texts("lever", lever)
    assert p["title"] == "Backend Engineer"
    assert "## Responsibilities" in p["text"] and "Migrate off Rails 6" in p["text"]
    assert "equal opportunity" in p["text"]


def test_write_context_lands_in_package(tmp_path):
    pkg = _package(tmp_path, "ashby", "ashby_postings.json", ASHBY)
    out = write_context(pkg)
    assert out == pkg / "brief-context.md"
    assert out.read_text(encoding="utf-8").startswith("# Acme — brief context")
