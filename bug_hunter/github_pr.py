"""
github_pr.py
------------
NOT YET WIRED UP — this is the next step after dry-run mode works well
for you. It documents exactly what's needed to go from "local branch +
commit" to "real PR opened on GitHub", using the GitHub REST API
directly (no extra dependency beyond `requests`, which you already have).

You'll need a GitHub Personal Access Token with `repo` scope (or a
fine-grained token with contents:write + pull-requests:write on the
target repo). Never hardcode it — read it from an environment variable.

The flow, once you're ready:

    1. Push the local branch created by pr_dryrun.py to your fork/remote:
         git push origin <branch_name>
       (subprocess call, same pattern as pr_dryrun.py's _run() helper)

    2. Open the PR via the GitHub API:
         POST https://api.github.com/repos/{owner}/{repo}/pulls
         headers: {"Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json"}
         body: {
             "title": pr_title,
             "body": pr_body,          # from report.pr_body_markdown()
             "head": branch_name,       # from pr_dryrun.run_dry_run_pr()
             "base": "main",
         }

That's genuinely it — two API-shaped steps. Everything else (finding
bugs, deciding what's fixable, generating the diff and PR description)
already happens in analyzer.py / fixer.py / report.py / pr_dryrun.py.

Below is a real (but currently unused) implementation of step 2 so it's
ready to call once you plug in a token and decide you're comfortable
having it actually push to GitHub.
"""

import os
import requests


def open_pull_request(owner, repo, branch_name, base_branch, pr_title, pr_body, token=None):
    """
    Opens a real PR on GitHub. Requires the branch to already be pushed
    to the remote (see module docstring, step 1).

    token: GitHub PAT. If not passed, reads from GITHUB_TOKEN env var.
    """
    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError(
            "No GitHub token found. Set GITHUB_TOKEN env var or pass token= explicitly. "
            "Never commit a token to source control."
        )

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    payload = {
        "title": pr_title,
        "body": pr_body,
        "head": branch_name,
        "base": base_branch,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    if resp.status_code >= 300:
        raise RuntimeError(f"GitHub API error {resp.status_code}: {resp.text}")

    data = resp.json()
    return {"pr_url": data["html_url"], "pr_number": data["number"]}


def push_branch(repo_path, branch_name, remote="origin"):
    """Pushes the locally-created fix branch to the remote."""
    import subprocess
    result = subprocess.run(
        ["git", "push", "-u", remote, branch_name],
        cwd=repo_path, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"git push failed:\n{result.stderr}")
    return result.stdout.strip()
