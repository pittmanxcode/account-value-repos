"""Real-world board shapes: Lever `lists`, observed heading variants, and
recorded exclusions for postings with no parseable responsibilities.

These cases come from the 2026-10-09 batch over the qualified migration
accounts (EQ Bank, Achievers, Filevine and Everbridge keep their content in
Lever lists; Hinge Health, Engine, Reddit and NetDocuments use section titles
the original parser did not match; Oscar, Onbe and Fivetran carry talent-pool
or general-application postings with no responsibilities at all).
"""

from __future__ import annotations

from account_value.collectors import lever
from account_value.parse import extract_bullets
from account_value.pay import ANNUAL_HOURS
from account_value.validate import format_report, validate_package


def _response(payload, text=""):
    return type("R", (), {
        "status_code": 200,
        "text": text or str(payload),
        "json": lambda s: payload,
        "raise_for_status": lambda s: None,
    })()


def test_lever_lists_content_is_parsed(tmp_path):
    payload = [{
        "id": "j1",
        "text": "Senior Software Engineer",
        "categories": {"department": "Platform", "location": "Remote"},
        "descriptionPlain": "Achievers is an employee recognition company.",
        "lists": [
            {"text": "What you'll do:",
             "content": "<ul><li>Transform our monolith internal systems into robust"
                        " microservices for user records</li></ul>"},
            {"text": "What you'll bring:",
             "content": "<ul><li>Five or more years of experience building"
                        " distributed services</li></ul>"},
        ],
        "createdAt": 1_700_000_000,
        "applyUrl": "https://jobs.lever.co/example/j1",
    }]

    def fetch(url):
        assert "api.lever.co" in url
        return _response(payload, text="[{}]")

    result = lever.collect("example", tmp_path, fetch=fetch)
    assert len(result.jobs) == 1
    assert result.jobs[0].title == "Senior Software Engineer"
    joined = " ".join(b.verbatim_responsibility for b in result.bullets)
    assert "monolith internal systems" in joined
    # The qualifications list is a stop section, never modeled as work.
    assert "Five or more years" not in joined


def test_observed_responsibility_heading_variants_parse():
    cases = {
        "hinge": (
            "The Opportunity\n"
            "What You'll Accomplish\n"
            "- Lead the MWeb Next.js migration strategy across every page we ship\n"
            "Basic Qualifications\n"
            "- Eight years of software engineering experience\n"
        ),
        "engine": (
            "About Engine\n"
            "Your Mission\n"
            "- Evaluate what stays in the monolith versus what moves to microservices and make the call\n"
            "What You'll Bring to Engine\n"
            "- Five years of backend experience\n"
        ),
        "reddit": (
            "You will:\n"
            "Build and scale new storage and messaging systems for Reddit's infrastructure teams\n"
            "You have:\n"
            "Experience operating distributed systems at scale\n"
        ),
        "netdocuments": (
            "About the Opportunity\n"
            "What Your Contributions Will Be\n"
            "- Establish migration patterns that let legacy and next-generation experiences operate side by side\n"
            "What You Will Bring to the Team\n"
            "- Deep experience with C# and .NET\n"
        ),
    }
    for label, text in cases.items():
        bullets = extract_bullets(text)
        assert bullets, f"{label}: expected responsibility bullets, got none"
        assert not [b for b in bullets if "experience" in b[1].lower()
                    and "migration" not in b[1].lower()], f"{label}: qualification leaked in"


def test_lever_style_achievevers_and_eqb_headings():
    text = (
        "Why you'll love this role:\n"
        "Competitive salary and meaningful equity at a recognition company\n"
        "How you'll shape our accounting practices:\n"
        "- Automate the month-end close so the team stops copy-pasting between ledgers\n"
    )
    bullets = extract_bullets(text)
    assert len(bullets) == 1
    assert "month-end close" in bullets[0][1]


def _job(job_id, title):
    return {"job_id": job_id, "title": title, "url": f"https://example.com/{job_id}",
            "content_chars": 1500, "pay_min_posted": 0, "pay_max_posted": 0}


def _scored(job_id):
    return {
        "job_id": job_id, "bullet_count": 1, "fit_normal": 50, "fit_bespoke": 60,
        "addressable_share": 0.5, "time_basis": "posted range", "time_source": "board",
        "evidence_confidence": "Medium", "role_hours_annual": ANNUAL_HOURS,
        "saved_hours_conservative": 100.0, "saved_hours_base": 200.0,
        "saved_hours_upside": 400.0,
    }


def _package(jobs, modeled_job_ids):
    normalized = [
        {"job_id": jid, "cluster": "platform-engineering", "is_noise": 0}
        for jid in modeled_job_ids
    ]
    scored = [_scored(jid) for jid in modeled_job_ids]
    roles = [{
        "job_id": jid, "title": "Engineer", "us_equiv_base_pay": 120_000.0,
        "pay_source": "BLS OEWS median", "occupation": "Software Developers",
        "hourly_equiv": 120_000.0 / ANNUAL_HOURS,
        "loaded_hourly_equiv": 1.3 * 120_000.0 / ANNUAL_HOURS,
        "role_hours_annual": float(ANNUAL_HOURS), "saved_hours_base": 200.0,
    } for jid in modeled_job_ids]
    clusters = [{"bullet_count": len(modeled_job_ids)}] if modeled_job_ids else []
    return jobs, normalized, scored, roles, clusters


def test_bulletless_postings_are_recorded_exclusions_not_failures():
    jobs = [_job("j1", "Senior Software Engineer, Backend"),
            _job("j2", "General Application")]
    payload = _package(jobs, ["j1"])
    report = validate_package(
        jobs=payload[0], normalized=payload[1], scored=payload[2],
        roles=payload[3], clusters=payload[4], components=[],
        reconciliation={"combined_blocked_reason": None},
    )
    assert report.passed, report.failures
    assert report.excluded_jobs == [{"job_id": "j2", "title": "General Application"}]
    text = format_report(report)
    assert "ALL VALIDATIONS PASSED" in text
    assert "Excluded postings: 1" in text
    assert "General Application" in text


def test_all_postings_excluded_fails_closed():
    jobs = [_job("j1", "Compiler Developer (LLVM, C++)")]
    payload = _package(jobs, [])
    report = validate_package(
        jobs=payload[0], normalized=payload[1], scored=payload[2],
        roles=payload[3], clusters=payload[4], components=[],
        reconciliation={"combined_blocked_reason": None},
    )
    assert not report.passed
    assert any("at least one posting modeled" in f for f in report.failures)
