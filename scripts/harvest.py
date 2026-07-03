#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Ship locally-accumulated LEARNINGS entries and metrics upstream as a PR.

Runs daily from launchd/cron (installed by install.py); developers never
invoke it. What it does, in order:

1. `git fetch`; if the checkout is on main and clean-mergeable, fast-forward
   it — this is also what keeps every developer's skills current.
2. Collect new lines in skills/*/LEARNINGS.md and metrics/*.jsonl relative
   to HEAD (entry lines only — never ships unrelated edits).
3. Apply those lines onto origin/main in a temporary worktree on branch
   learnings/<user>, commit, push, and open (or update) one PR per user.

The developer's working tree is never modified beyond the ff-pull; once the
PR merges and the next pull lands, their local files match HEAD and the
dirty state clears itself. Offline / no gh / nothing new are all silent
no-ops — the job just tries again tomorrow.
"""

import argparse
import getpass
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENTRY_RE = re.compile(r"^- \d{4}-\d{2}-\d{2}: ")
LOCK = Path.home() / ".local" / "state" / "jacob-agent-skills" / "harvest.lock"
LOCK_STALE_SECONDS = 6 * 3600


def git(*args: str, cwd: Path = REPO, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=check)


def log(msg: str) -> None:
    print(f"harvest: {msg}")


def head_lines(relpath: str) -> set[str]:
    r = git("show", f"HEAD:{relpath}")
    return set(r.stdout.splitlines()) if r.returncode == 0 else set()


def new_learnings() -> dict[str, list[str]]:
    """relpath -> dated entry lines present locally but not in HEAD."""
    out: dict[str, list[str]] = {}
    for f in sorted(REPO.glob("skills/*/LEARNINGS.md")):
        rel = str(f.relative_to(REPO))
        base = head_lines(rel)
        added = [l for l in f.read_text().splitlines() if l.startswith("- ") and l not in base]
        if added:
            out[rel] = added
    return out


def new_metrics(user: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    f = REPO / "metrics" / f"{user}.jsonl"
    if f.is_file():
        rel = str(f.relative_to(REPO))
        base = head_lines(rel)
        added = [l for l in f.read_text().splitlines() if l.strip() and l not in base]
        if added:
            out[rel] = added
    return out


def take_lock() -> bool:
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    if LOCK.exists():
        if time.time() - LOCK.stat().st_mtime < LOCK_STALE_SECONDS:
            return False
        LOCK.unlink()
    LOCK.touch()
    return True


def ff_pull_main() -> None:
    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch != "main":
        log(f"checkout is on '{branch}', skipping pull")
        return
    r = git("merge", "--ff-only", "origin/main")
    log("pulled main" if r.returncode == 0 else "pull skipped (local changes conflict; will retry)")


def apply_additions(wt: Path, learnings: dict[str, list[str]], metrics: dict[str, list[str]]) -> None:
    for rel, lines in learnings.items():
        f = wt / rel
        existing = f.read_text() if f.is_file() else "# Learnings\n"
        existing_lines = set(existing.splitlines())
        fresh = [l for l in lines if l not in existing_lines]
        if not fresh:
            continue
        if "(no entries yet)" in existing:
            existing = existing.replace("(no entries yet)\n", "").replace("(no entries yet)", "")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(existing.rstrip("\n") + "\n" + "\n".join(fresh) + "\n")
    for rel, lines in metrics.items():
        f = wt / rel
        existing_lines = set(f.read_text().splitlines()) if f.is_file() else set()
        fresh = [l for l in lines if l not in existing_lines]
        if not fresh:
            continue
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a") as fh:
            fh.write("\n".join(fresh) + "\n")


def pr_body(learnings: dict[str, list[str]], metrics: dict[str, list[str]], warnings: list[str]) -> str:
    lines = ["Automated learnings harvest. Each entry below was appended by an agent", "after real skill use on this machine.", ""]
    for rel, added in learnings.items():
        lines.append(f"**{rel.split('/')[1]}** ({len(added)} new)")
        lines.extend(f"> {l}" for l in added)
        lines.append("")
    if metrics:
        total = sum(len(v) for v in metrics.values())
        lines.append(f"Plus {total} metrics event(s) in `metrics/`.")
    if warnings:
        lines.append("")
        lines.append("⚠️ Lines not matching the `- YYYY-MM-DD:` format (review closely):")
        lines.extend(f"> {w}" for w in warnings)
    return "\n".join(lines)


def ship(learnings: dict[str, list[str]], metrics: dict[str, list[str]], user: str, push: bool) -> int:
    branch = f"learnings/{user}"
    remote_has = bool(git("ls-remote", "--heads", "origin", branch).stdout.strip())
    base = f"origin/{branch}" if remote_has else "origin/main"
    wt = Path(tempfile.mkdtemp(prefix="skills-harvest-"))
    try:
        r = git("worktree", "add", "-B", branch, str(wt), base)
        if r.returncode != 0:
            log(f"worktree failed: {r.stderr.strip()}")
            return 1
        apply_additions(wt, learnings, metrics)
        git("add", "-A", "--", "skills", "metrics", cwd=wt)
        if git("diff", "--cached", "--quiet", cwd=wt).returncode == 0:
            log("everything already shipped upstream; nothing to do")
            return 0
        skills = ", ".join(sorted(rel.split("/")[1] for rel in learnings)) or "metrics only"
        r = git("commit", "-m", f"learnings({user}): {skills}", cwd=wt, check=False)
        if r.returncode != 0:
            log(f"commit failed: {r.stderr.strip()}")
            return 1
        if not push:
            log(f"--no-push: commit left on local branch {branch}")
            return 0
        r = git("push", "-u", "origin", branch, cwd=wt)
        if r.returncode != 0:
            log(f"push failed (offline or no access), retrying tomorrow: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ''}")
            return 0
        log(f"pushed {branch}")
        if not shutil.which("gh"):
            log("gh not installed; branch pushed, PR not opened")
            return 0
        open_prs = subprocess.run(
            ["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "number"],
            capture_output=True, text=True, cwd=wt,
        )
        if open_prs.returncode == 0 and json.loads(open_prs.stdout or "[]"):
            log("existing open PR updated by push")
            return 0
        warnings = [l for added in learnings.values() for l in added if not ENTRY_RE.match(l)]
        r = subprocess.run(
            ["gh", "pr", "create", "--head", branch, "--title", f"Learnings harvest: {user}",
             "--body", pr_body(learnings, metrics, warnings)],
            capture_output=True, text=True, cwd=wt,
        )
        log(f"PR opened: {r.stdout.strip()}" if r.returncode == 0 else f"PR create failed: {r.stderr.strip()}")
        return 0
    finally:
        git("worktree", "remove", "--force", str(wt))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="report what would ship; change nothing")
    parser.add_argument("--no-push", action="store_true", help="commit to the local harvest branch but do not push or open a PR")
    args = parser.parse_args()
    user = getpass.getuser()

    if not args.dry_run and not take_lock():
        log("another harvest is running; exiting")
        return 0
    try:
        if git("fetch", "origin").returncode != 0:
            log("fetch failed (offline?); exiting")
            return 0
        if not args.dry_run:
            ff_pull_main()

        learnings = new_learnings()
        metrics = new_metrics(user)
        if not learnings and not metrics:
            log("nothing new to ship")
            return 0
        for rel, added in learnings.items():
            log(f"{rel}: {len(added)} new entr{'y' if len(added) == 1 else 'ies'}")
        for rel, added in metrics.items():
            log(f"{rel}: {len(added)} new event(s)")
        if args.dry_run:
            return 0
        return ship(learnings, metrics, user, push=not args.no_push)
    finally:
        if not args.dry_run:
            LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
