#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Claude Code PostToolUse hook: log one JSONL event per Skill invocation.

Wired into ~/.claude/settings.json by install.py (matcher: "Skill"). Reads
the hook payload from stdin and appends one line to metrics/<user>.jsonl in
this repo. Logged fields: timestamp, skill name, username, project-directory
basename, truncated session id. Never prompt content, paths, or code.

A hook must never break the session: every failure path exits 0, silently.
"""

import getpass
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
METRICS = REPO / "metrics"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if payload.get("tool_name") != "Skill":
            return 0
        skill = (payload.get("tool_input") or {}).get("skill")
        if not skill:
            return 0
        event = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "skill": skill,
            "user": getpass.getuser(),
            "project": Path(payload.get("cwd") or ".").name,
            "session": str(payload.get("session_id") or "")[:8],
        }
        METRICS.mkdir(exist_ok=True)
        out = METRICS / f"{event['user']}.jsonl"
        with out.open("a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
