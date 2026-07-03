# metrics/

Machine-written skill-usage events — one JSONL file per developer, appended
by the Claude Code PostToolUse hook (`scripts/log_skill_use.py`) and shipped
upstream by the daily harvest job. Do not hand-edit.

Each line:

```json
{"ts": "2026-07-02T21:04:11Z", "skill": "python-testing", "user": "jacob", "project": "billing-sync", "session": "23303d97"}
```

What is logged: timestamp, skill name, username, project **directory
basename** only, truncated session id. Never prompts, file paths, or code.
Cursor sessions are not captured — counts are a floor, not a census.

Read the numbers with `uv run scripts/skill_stats.py`.
