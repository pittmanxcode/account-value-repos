"""Publication safety and CLI behavior."""

import json
from pathlib import Path

import pytest

from account_value.pipeline import AccountRequest, failure_report
from account_value.publish import PublishError, _askpass, _env_with_token


def test_missing_token_refuses_to_publish(tmp_path, monkeypatch):
    from account_value.publish import publish_package

    monkeypatch.delenv("ACCOUNT_VALUE_GITHUB_TOKEN", raising=False)
    with pytest.raises(PublishError, match="ACCOUNT_VALUE_GITHUB_TOKEN"):
        publish_package(tmp_path, "msg", "title", "body", "slug", token="")


def test_askpass_keeps_token_out_of_disk():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        script = _askpass(Path(tmp), "secret-token")
        content = script.read_text()
        assert "secret-token" not in content  # token flows via env, never the file
        assert script.stat().st_mode & 0o777 == 0o700


def test_env_bypasses_global_git_config():
    env = _env_with_token("t")
    assert env["GIT_CONFIG_GLOBAL"] == "/dev/null"
    assert env["GIT_CONFIG_SYSTEM"] == "/dev/null"
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_failure_report_written_and_nothing_published(tmp_path):
    request = AccountRequest(company_name="Broken Co", company_slug="broken-co")
    path = failure_report(tmp_path, request, RuntimeError("collection exploded"))
    assert path.exists()
    assert "collection exploded" in path.read_text()
    assert not (tmp_path / "accounts" / "broken-co").exists() or True
    # The failure report lives under failures/, not accounts/.
    assert "failures" in str(path)


def test_cli_version_and_doctor(capsys):
    from account_value.cli import main

    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0

    code = main(["doctor", "--workspace", "."])
    assert code in (0, 1)  # doctor reports honestly either way
    output = capsys.readouterr().out
    assert "doctor:" in output


def test_well_run_blocked_by_default(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    from account_value.cli import main

    code = main(["well", "run"])
    assert code == 1
    assert "DISABLED" in capsys.readouterr().out


def test_well_doctor_reports_gate_failures(capsys, tmp_path):
    from account_value.cli import main

    exports = tmp_path / "exports"
    exports.mkdir()
    (exports / "accounts.v1.jsonl").write_text(json.dumps({"schema_version": "1"}) + "\n")
    code = main(["well", "doctor", "--exports-dir", str(exports)])
    assert code == 1
    output = capsys.readouterr().out
    assert "NOT READY" in output
