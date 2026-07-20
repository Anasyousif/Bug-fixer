"""
pr_dryrun.py
------------
Simulates the "open a PR with the fixes" step WITHOUT touching GitHub:
  1. Creates a new local git branch inside the target repo
  2. Applies the auto-fixes and writes the files
  3. Commits the changes locally
  4. Writes out a PR title + body to a markdown file

This lets you inspect exactly what would be pushed/opened before wiring
up real GitHub API calls (see github_pr.py for that, once you're ready).

Requires the target path to already be a git repository. If it isn't,
we initialize one (useful for the bundled sample_buggy_repo demo).
"""

import os
import subprocess
import datetime

BRANCH_PREFIX = "bug-hunter/auto-fixes"


def _run(cmd, cwd):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()


def ensure_git_repo(repo_path):
    if not os.path.isdir(os.path.join(repo_path, ".git")):
        _run(["git", "init"], cwd=repo_path)
        _run(["git", "config", "user.email", "bug-hunter@example.local"], cwd=repo_path)
        _run(["git", "config", "user.name", "Bug Hunter Bot"], cwd=repo_path)
        _run(["git", "add", "-A"], cwd=repo_path)
        # Only commit if there's something to commit
        status = _run(["git", "status", "--porcelain"], cwd=repo_path)
        if status:
            _run(["git", "commit", "-m", "Initial commit (pre-existing code)"], cwd=repo_path)
        return True
    return False


def create_fix_branch(repo_path):
    branch_name = f"{BRANCH_PREFIX}-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    _run(["git", "checkout", "-b", branch_name], cwd=repo_path)
    return branch_name


def write_fixed_files(repo_path, file_fixes):
    """file_fixes: dict[relative_or_absolute_path] -> list[str] (new source lines)"""
    for filepath, new_lines in file_fixes.items():
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")


def commit_fixes(repo_path, files_changed, commit_message):
    _run(["git", "add"] + files_changed, cwd=repo_path)
    _run(["git", "commit", "-m", commit_message], cwd=repo_path)
    return _run(["git", "rev-parse", "HEAD"], cwd=repo_path)


def get_diff_against_parent(repo_path):
    return _run(["git", "diff", "HEAD~1", "HEAD"], cwd=repo_path)


def run_dry_run_pr(repo_path, file_fixes, pr_title, pr_body, output_dir):
    """
    Full dry-run pipeline. file_fixes: dict[filepath] -> list[new_source_lines]
    (only files that had at least one applied fix should be included).
    Returns a summary dict with branch name, commit hash, and paths of
    generated artifacts.
    """
    initialized = ensure_git_repo(repo_path)
    branch_name = create_fix_branch(repo_path)

    write_fixed_files(repo_path, file_fixes)

    rel_paths = [os.path.relpath(p, repo_path) for p in file_fixes.keys()]
    commit_hash = commit_fixes(
        repo_path, rel_paths,
        commit_message=f"fix: auto-fix {len(file_fixes)} file(s) via Bug Hunter\n\n{pr_title}"
    )
    diff_text = get_diff_against_parent(repo_path)

    os.makedirs(output_dir, exist_ok=True)
    pr_body_path = os.path.join(output_dir, "PR_BODY.md")
    diff_path = os.path.join(output_dir, "changes.diff")

    with open(pr_body_path, "w") as f:
        f.write(f"# {pr_title}\n\n{pr_body}\n")
    with open(diff_path, "w") as f:
        f.write(diff_text)

    return {
        "repo_initialized_fresh": initialized,
        "branch_name": branch_name,
        "commit_hash": commit_hash,
        "pr_body_path": pr_body_path,
        "diff_path": diff_path,
        "files_changed": rel_paths,
    }
