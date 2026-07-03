#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Report skill usage and health from metrics/*.jsonl and LEARNINGS.md files.

Answers: which skills get used (and by whom), which are dead weight, and
which are fighting reality (high correction density). Run from anywhere:

    uv run scripts/skill_stats.py            # last 30 days + all-time
    uv run scripts/skill_stats.py --days 7
    uv run scripts/skill_stats.py --projects # add per-project breakdown

Events are logged by the Claude Code hook (log_skill_use.py); Cursor usage
is not captured, so treat counts as a floor, not a census.
"""

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENTRY_RE = re.compile(r"^- \d{4}-\d{2}-\d{2}: ")


def load_events() -> list[dict]:
    events = []
    for f in sorted((REPO / "metrics").glob("*.jsonl")):
        for line in f.read_text().splitlines():
            try:
                e = json.loads(line)
                e["dt"] = datetime.strptime(e["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                events.append(e)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
    return events


def repo_skills() -> list[str]:
    return sorted(d.name for d in (REPO / "skills").iterdir() if (d / "SKILL.md").is_file())


def learnings_count(skill: str) -> int:
    f = REPO / "skills" / skill / "LEARNINGS.md"
    if not f.is_file():
        return 0
    return sum(1 for l in f.read_text().splitlines() if ENTRY_RE.match(l))


def skill_added_date(skill: str) -> str:
    r = subprocess.run(
        ["git", "-C", str(REPO), "log", "--reverse", "--format=%ad", "--date=short", "--", f"skills/{skill}/SKILL.md"],
        capture_output=True, text=True,
    )
    lines = r.stdout.splitlines()
    return lines[0] if lines else "?"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=30, help="recent window in days (default 30)")
    parser.add_argument("--projects", action="store_true", help="include per-project breakdown")
    args = parser.parse_args()

    events = load_events()
    skills = repo_skills()
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    by_skill: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_skill[e["skill"]].append(e)

    print(f"Skill usage — {len(events)} events, {len({e['user'] for e in events})} user(s), "
          f"window = last {args.days} days\n")
    header = f"{'skill':<24} {'added':<12} {'all-time':>8} {f'last {args.days}d':>9} {'users':>6} {'lessons':>8}  health"
    print(header)
    print("-" * len(header))

    for skill in skills:
        evs = by_skill.get(skill, [])
        recent = [e for e in evs if e["dt"] >= cutoff]
        users = len({e["user"] for e in evs})
        lessons = learnings_count(skill)
        if not evs:
            health = "NEVER USED — fix description, evangelize, or delete"
        elif lessons and len(evs) < 5:
            health = "corrections early — watch"
        elif lessons >= 3:
            health = f"high correction density ({lessons}/{len(evs)}) — fold or fix"
        elif not recent:
            health = "idle this window"
        else:
            health = "ok"
        print(f"{skill:<24} {skill_added_date(skill):<12} {len(evs):>8} {len(recent):>9} {users:>6} {lessons:>8}  {health}")

    other = sorted(set(by_skill) - set(skills))
    if other:
        print("\nNon-repo skills seen in events (plugins, project-local):")
        for s in other:
            print(f"  {s}: {len(by_skill[s])}")

    if args.projects:
        print("\nPer-project (all-time):")
        proj = Counter((e["skill"], e["project"]) for e in events)
        for (skill, project), n in proj.most_common():
            print(f"  {skill:<24} {project:<24} {n}")

    if not events:
        print("\nNo events yet. The logger only records use going forward, and only")
        print("from Claude Code sessions on machines where install.py wired the hook.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
