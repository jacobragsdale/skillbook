#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Symlink each skill in this repo's skills/ into agent skill directories.

Creates per-skill symlinks (never links the whole directory — Claude Code
writes internal files into its skills dir, which breaks a dir-level symlink):

    ~/.agents/skills/<name>  -> <repo>/skills/<name>   (Cursor)
    ~/.claude/skills/<name>  -> <repo>/skills/<name>   (Claude Code)

Edits in the repo take effect everywhere immediately. Re-run after adding a
skill; use --uninstall to remove only symlinks that point into this repo.

Also offers (ask-once; force with --with-harvest, skip with --no-harvest)
to wire the learnings/metrics loop:

  - a Claude Code PostToolUse hook that logs every Skill invocation to
    metrics/<user>.jsonl (scripts/log_skill_use.py)
  - a daily 17:00 launchd/cron job that ships new LEARNINGS.md entries and
    metrics upstream as a PR (scripts/harvest.py)
"""

import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
SKILLS = REPO / "skills"
TARGET_ROOTS = [Path.home() / ".agents" / "skills", Path.home() / ".claude" / "skills"]

CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"
HOOK_MARKER = "log_skill_use.py"
PLIST = Path.home() / "Library" / "LaunchAgents" / "io.jacob-agent-skills.harvest.plist"
HARVEST_LOG = Path.home() / ".local" / "state" / "jacob-agent-skills" / "harvest.log"
CRON_MARKER = "# jacob-agent-skills harvest"


def repo_skills() -> list[Path]:
    return sorted(d for d in SKILLS.iterdir() if (d / "SKILL.md").is_file())


def install(dry_run: bool, force: bool) -> int:
    problems = 0
    for skill in repo_skills():
        for root in TARGET_ROOTS:
            link = root / skill.name
            if link.is_symlink() and link.resolve() == skill:
                print(f"ok        {link}")
                continue
            if link.exists() or link.is_symlink():
                if not force:
                    print(f"CONFLICT  {link} exists and is not a link to this repo (use --force)")
                    problems += 1
                    continue
                if dry_run:
                    print(f"replace   {link} -> {skill}")
                    continue
                if link.is_symlink():
                    link.unlink()
                else:
                    print(f"CONFLICT  {link} is a real file/dir — refusing to delete even with --force")
                    problems += 1
                    continue
            if dry_run:
                print(f"link      {link} -> {skill}")
                continue
            root.mkdir(parents=True, exist_ok=True)
            link.symlink_to(skill)
            print(f"linked    {link} -> {skill}")
    return 1 if problems else 0


def uninstall(dry_run: bool) -> int:
    for root in TARGET_ROOTS:
        if not root.is_dir():
            continue
        for link in sorted(root.iterdir()):
            if link.is_symlink() and SKILLS in link.resolve().parents:
                if dry_run:
                    print(f"would remove  {link}")
                else:
                    link.unlink()
                    print(f"removed       {link}")
    return 0


# --- learnings/metrics loop -------------------------------------------------


def uv_path() -> str:
    return shutil.which("uv") or "uv"


def hook_wired() -> bool:
    if not CLAUDE_SETTINGS.is_file():
        return False
    try:
        data = json.loads(CLAUDE_SETTINGS.read_text())
    except json.JSONDecodeError:
        return False
    for entry in data.get("hooks", {}).get("PostToolUse", []):
        for h in entry.get("hooks", []):
            if HOOK_MARKER in h.get("command", ""):
                return True
    return False


def wire_hook(dry_run: bool) -> None:
    if hook_wired():
        print(f"ok        metrics hook in {CLAUDE_SETTINGS}")
        return
    if dry_run:
        print(f"would add metrics hook (PostToolUse/Skill) to {CLAUDE_SETTINGS}")
        return
    data = json.loads(CLAUDE_SETTINGS.read_text()) if CLAUDE_SETTINGS.is_file() else {}
    if CLAUDE_SETTINGS.is_file():
        CLAUDE_SETTINGS.with_suffix(".json.bak").write_text(CLAUDE_SETTINGS.read_text())
    entry = {
        "matcher": "Skill",
        "hooks": [{"type": "command", "command": f'{uv_path()} run "{REPO / "scripts" / "log_skill_use.py"}"'}],
    }
    data.setdefault("hooks", {}).setdefault("PostToolUse", []).append(entry)
    CLAUDE_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    CLAUDE_SETTINGS.write_text(json.dumps(data, indent=2) + "\n")
    print(f"wired     metrics hook in {CLAUDE_SETTINGS} (backup: settings.json.bak)")


def timer_wired() -> bool:
    if platform.system() == "Darwin":
        return PLIST.is_file()
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return CRON_MARKER in r.stdout


def install_timer(dry_run: bool) -> None:
    if timer_wired():
        print(f"ok        daily harvest job ({PLIST if platform.system() == 'Darwin' else 'crontab'})")
        return
    harvest = REPO / "scripts" / "harvest.py"
    if platform.system() == "Darwin":
        if dry_run:
            print(f"would install launchd job {PLIST} (daily 17:00)")
            return
        HARVEST_LOG.parent.mkdir(parents=True, exist_ok=True)
        PLIST.parent.mkdir(parents=True, exist_ok=True)
        PLIST.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>io.jacob-agent-skills.harvest</string>
    <key>ProgramArguments</key>
    <array>
        <string>{uv_path()}</string>
        <string>run</string>
        <string>{harvest}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
    <key>StandardOutPath</key><string>{HARVEST_LOG}</string>
    <key>StandardErrorPath</key><string>{HARVEST_LOG}</string>
</dict>
</plist>
""")
        subprocess.run(["launchctl", "unload", str(PLIST)], capture_output=True)
        r = subprocess.run(["launchctl", "load", str(PLIST)], capture_output=True, text=True)
        status = "loaded" if r.returncode == 0 else f"wrote plist, load failed: {r.stderr.strip()}"
        print(f"installed daily harvest job (17:00) — {status}")
    else:
        line = f'0 17 * * * {uv_path()} run "{harvest}" >> "{HARVEST_LOG}" 2>&1 {CRON_MARKER}'
        if dry_run:
            print(f"would add crontab line: {line}")
            return
        HARVEST_LOG.parent.mkdir(parents=True, exist_ok=True)
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        subprocess.run(["crontab", "-"], input=current.rstrip("\n") + "\n" + line + "\n", text=True, check=True)
        print("installed daily harvest crontab entry (17:00)")


def unwire_harvest(dry_run: bool) -> None:
    if hook_wired():
        if dry_run:
            print(f"would remove metrics hook from {CLAUDE_SETTINGS}")
        else:
            data = json.loads(CLAUDE_SETTINGS.read_text())
            post = data.get("hooks", {}).get("PostToolUse", [])
            data["hooks"]["PostToolUse"] = [
                e for e in post if not any(HOOK_MARKER in h.get("command", "") for h in e.get("hooks", []))
            ]
            if not data["hooks"]["PostToolUse"]:
                del data["hooks"]["PostToolUse"]
            CLAUDE_SETTINGS.write_text(json.dumps(data, indent=2) + "\n")
            print(f"removed   metrics hook from {CLAUDE_SETTINGS}")
    if platform.system() == "Darwin" and PLIST.is_file():
        if dry_run:
            print(f"would remove launchd job {PLIST}")
        else:
            subprocess.run(["launchctl", "unload", str(PLIST)], capture_output=True)
            PLIST.unlink()
            print(f"removed   launchd job {PLIST}")
    elif platform.system() != "Darwin":
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        if CRON_MARKER in current:
            if dry_run:
                print("would remove harvest crontab entry")
            else:
                kept = "\n".join(l for l in current.splitlines() if CRON_MARKER not in l)
                subprocess.run(["crontab", "-"], input=kept + "\n", text=True, check=True)
                print("removed   harvest crontab entry")


def setup_harvest(dry_run: bool, with_harvest: bool, no_harvest: bool) -> None:
    if no_harvest:
        return
    if hook_wired() and timer_wired():
        wire_hook(dry_run)
        install_timer(dry_run)
        return
    if not with_harvest:
        if not sys.stdin.isatty():
            print("hint      run with --with-harvest to wire the metrics hook + daily learnings PR job")
            return
        answer = input("Wire learnings/metrics loop (Claude Code Skill-usage hook + daily 17:00 harvest PR job)? [Y/n] ")
        if answer.strip().lower() in ("n", "no"):
            return
    wire_hook(dry_run)
    install_timer(dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print actions without making changes")
    parser.add_argument("--force", action="store_true", help="replace existing symlinks that point elsewhere")
    parser.add_argument("--uninstall", action="store_true", help="remove symlinks, hook, and harvest job installed by this script")
    parser.add_argument("--with-harvest", action="store_true", help="wire the learnings/metrics loop without prompting")
    parser.add_argument("--no-harvest", action="store_true", help="skip the learnings/metrics loop entirely")
    args = parser.parse_args()

    if args.uninstall:
        rc = uninstall(args.dry_run)
        unwire_harvest(args.dry_run)
        return rc
    rc = install(args.dry_run, args.force)
    setup_harvest(args.dry_run, args.with_harvest, args.no_harvest)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
