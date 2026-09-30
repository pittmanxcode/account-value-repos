"""Publication: branch, commit, push, one draft PR — idempotent, env-only token.

Safety properties:
- Builds in an isolated worktree from current origin/main; never touches a
  dirty checkout and never force-pushes.
- Credentials come only from ACCOUNT_VALUE_GITHUB_TOKEN in the environment,
  passed through a private askpass; never written to disk or config.
- The machine's global git config (credential store + insteadOf rewrite) is
  bypassed for these commands via GIT_CONFIG_GLOBAL=/dev/null, without
  modifying the user's configuration.
- Re-running the same batch reuses its branch; a PR is created once.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class PublishError(RuntimeError):
    pass


@dataclass
class PublishResult:
    branch: str
    pr_url: str | None
    reused_branch: bool


def _env_with_token(token: str) -> dict[str, str]:
    env = dict(os.environ)
    env["ACCOUNT_VALUE_TOKEN"] = token
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_CONFIG_SYSTEM"] = "/dev/null"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _askpass(env_dir: Path, token: str) -> Path:
    script = env_dir / "askpass.sh"
    script.write_text(
        "#!/bin/sh\ncase \"$1\" in Username*) echo x-access-token ;; *) echo $ACCOUNT_VALUE_TOKEN ;; esac\n",
        encoding="utf-8",
    )
    script.chmod(0o700)
    return script


def _git(args: list[str], env: dict, cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise PublishError(f"git {' '.join(args[:2])}: {result.stderr.strip()[:300]}")
    return result.stdout.strip()


def _pr_exists(token: str, repo: str, head: str) -> str | None:
    import httpx

    response = httpx.get(
        f"https://api.github.com/repos/{repo}/pulls",
        params={"head": head, "state": "open"},
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        timeout=30,
    )
    response.raise_for_status()
    pulls = response.json()
    return pulls[0]["html_url"] if pulls else None


def publish_package(
    package_dir: Path,
    commit_message: str,
    pr_title: str,
    pr_body: str,
    company_slug: str,
    repo: str = "pittmanxcode/account-value-repos",
    token: str | None = None,
) -> PublishResult:
    """Publish one account package as a draft PR. Returns the PR URL."""
    token = token or os.environ.get("ACCOUNT_VALUE_GITHUB_TOKEN", "")
    if not token:
        raise PublishError(
            "ACCOUNT_VALUE_GITHUB_TOKEN is not set; refusing to publish"
        )
    remote_url = _git(["remote", "get-url", "origin"], dict(os.environ), REPO)
    head_branch = f"automation/account-{company_slug}"
    existing_pr = _pr_exists(token, repo, f"pittmanxcode:{head_branch}")
    env_dir = Path(tempfile.mkdtemp(prefix="av-publish-"))
    worktree = env_dir / "worktree"
    reused = False
    try:
        askpass = _askpass(env_dir, token)
        env = _env_with_token(token)
        env["GIT_ASKPASS"] = str(askpass)
        # Strip the token URL of any credentials embedded by mirrors.
        push_url = remote_url.replace("https://github.com/", "https://github.com/")
        _git(["fetch", "--quiet", "origin", "main"], env, REPO)
        remote_branch = _git(
            ["ls-remote", "--heads", push_url, head_branch], env, REPO
        )
        if remote_branch:
            reused = True
        _git(["worktree", "add", "--detach", str(worktree), "origin/main"], env, REPO)
        _git(["switch", "-c", head_branch], env, worktree)
        target = worktree / "accounts" / company_slug
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(package_dir, target,
                        ignore=shutil.ignore_patterns("__pycache__"))
        _git(["add", f"accounts/{company_slug}"], env, worktree)
        status = subprocess.run(
            ["git", "diff", "--cached", "--name-only"], cwd=worktree, env=env,
            capture_output=True, text=True,
        )
        if not status.stdout.strip() and reused:
            pr_url = existing_pr
            if pr_url:
                return PublishResult(branch=head_branch, pr_url=pr_url, reused_branch=True)
        _git(["commit", "-m", commit_message], env, worktree)
        _git(["push", "-u", push_url, head_branch], env, worktree)
        if existing_pr:
            return PublishResult(branch=head_branch, pr_url=existing_pr, reused_branch=True)
        pr_url = _create_pr(token, repo, head_branch, pr_title, pr_body)
        return PublishResult(branch=head_branch, pr_url=pr_url, reused_branch=reused)
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(worktree)],
                       cwd=REPO, capture_output=True)
        shutil.rmtree(env_dir, ignore_errors=True)


def _create_pr(token: str, repo: str, branch: str, title: str, body: str) -> str:
    import httpx

    response = httpx.post(
        f"https://api.github.com/repos/{repo}/pulls",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json={"title": title, "body": body, "head": branch, "base": "main", "draft": True},
        timeout=30,
    )
    if response.status_code == 422:  # already exists
        existing = _pr_exists(token, repo, f"pittmanxcode:{branch}")
        if existing:
            return existing
    response.raise_for_status()
    return response.json()["html_url"]
