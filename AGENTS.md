# Working in this repo

This is a library of Agent Skills (agentskills.io format). The canonical
source is `skills/<name>/`; agent-specific directories (`~/.agents/skills`,
`~/.claude/skills`) receive per-skill symlinks via `install.py` — never edit
skills there, edit them here.

Rules:

- **Creating or changing a skill?** Follow `skills/jacob-create-skill/SKILL.md`
  — it is the house process (clarify → scaffold → draft → validate → trigger
  test → learnings loop).
- Every skill must pass
  `uv run skills/jacob-create-skill/scripts/validate_skill.py skills/<name>`
  before commit. Treat warnings as decisions, not noise.
- All bundled Python is a single file with a PEP 723 `# /// script` header,
  runnable via `uv run` with no environment setup.
- Never edit a skill's SKILL.md to record a one-off correction — append a
  dated line to that skill's `LEARNINGS.md` instead. Folding learnings into
  SKILL.md is a deliberate, reviewed step.
- One skill, one job. If a change makes a skill's description need an "and",
  split it.
