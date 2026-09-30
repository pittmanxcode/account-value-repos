"""Taxonomy classification, pay basis, and deterministic scenario math."""

from account_value.events import load_registry
from account_value.pay import OCC_WAGE, load_title_overrides, pay_basis
from account_value.taxonomy import classify, noise_pattern
from account_value.value_model import Bullet, JobPosting, build_model, scenario_adoption


def test_classify_ports_the_fixture_behavior():
    assert classify("Build backend services and review pull requests") == "sw_dev"
    assert classify("Prepare journal entries and reconcile invoices") == "accounting_tx"
    assert classify("Translate subtitles for seasonal releases") == "localization"
    assert classify("Own the roadmap and run sprint ceremonies") == "pm_program"
    assert classify("Something entirely unclassifiable here") == "other_generalist"


def test_plural_singularity_matches():
    assert classify("Run audits on internal controls") == "tax_sox"
    assert classify("Maintain dashboards and KPIs for the leadership team") == "analytics_bi"


def test_noise_pattern_is_company_injected():
    noise = noise_pattern("Crunchyroll")
    assert noise.search("Crunchyroll is an equal opportunity employer")
    assert noise.search("You will report to the Senior Director")
    assert not noise.search("Build data pipelines for the analytics team")


def test_pay_basis_prefers_posted_pay():
    basis = pay_basis("Software Engineer", posted_mid=150000)
    assert basis.base_pay == 150000
    assert basis.pay_source == "posted pay range"


def test_pay_basis_uses_overrides_then_heuristic():
    overrides = load_title_overrides(
        __import__("pathlib").Path("examples/crunchyroll/pay_title_map.yaml")
    )
    basis = pay_basis("Data Engineer III", overrides=overrides)
    assert basis.soc == "15-1252.00"
    assert basis.seniority == "senior"
    heuristic = pay_basis("Total Mystery Title With No Match")
    assert heuristic.occupation != "unknown occupation"
    assert heuristic.pay_source.startswith("BLS OEWS")


def test_wage_table_covers_all_mapped_socs():
    from account_value.pay import OCC_LABELS

    missing = [soc for soc in OCC_LABELS if soc not in OCC_WAGE]
    assert not missing, f"wage table missing: {missing}"


def _job(job_id="j1", title="Software Engineer", pay_mid=0, language="en"):
    return JobPosting(job_id=job_id, title=title, department="Eng",
                      location="US", language=language, url="https://x/j1")


def _bullet(job_id, text, seq=1):
    return Bullet(job_id=job_id, title="Software Engineer", department="Eng",
                  resp_seq=seq, section="duties", verbatim_responsibility=text)


def test_build_model_scenario_monotonic_and_hours_normalized(fixture_title_overrides):
    jobs = [_job(), _job(job_id="j2", title="Accounting Director")]
    bullets = [
        _bullet("j1", "Build backend services and debug production issues"),
        _bullet("j1", "Write automated tests for the release pipeline", seq=2),
        _bullet("j2", "Prepare journal entries and reconcile invoices"),
    ]
    model = build_model(jobs, bullets, fixture_title_overrides, "TestCo")
    assert len(model["roles"]) == 2
    for role in model["roles"]:
        assert abs(float(role["role_hours_annual"]) - 1920) < 0.5
        cons, base, up = (float(role[f"saved_hours_{s}"]) for s in
                          ("conservative", "base", "upside"))
        assert cons <= base <= up
        assert up <= 1920
    total_saved = sum(float(r["saved_hours_base"]) for r in model["roles"])
    total_hours = sum(float(r["role_hours_annual"]) for r in model["roles"])
    assert total_saved <= total_hours


def test_non_english_twin_inherits_english_distribution(fixture_title_overrides):
    jobs = [_job(), _job(job_id="j2", title="Software Engineer", language="ja")]
    bullets = [_bullet("j1", "Build backend services and debug production issues")]
    model = build_model(jobs, bullets, fixture_title_overrides, "TestCo")
    roles = {r["job_id"]: r for r in model["roles"]}
    assert roles["j1"]["saved_hours_base"] == roles["j2"]["saved_hours_base"]


def test_scenario_adoption_ordering():
    assert scenario_adoption("conservative")[0] < scenario_adoption("base")[0]
    assert scenario_adoption("base")[0] < scenario_adoption("upside")[0]


def test_registry_loads_and_cross_checks():
    registry = load_registry()
    assert any(s.id == "R1" for s in registry.deadline_signals)
    assert all(s.hard_cost_anchor is None or s.hard_cost_label for s in registry.deadline_signals)
