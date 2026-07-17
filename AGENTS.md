# Working in this repo

This is a library of Agent Skills (agentskills.io format) and the single
source of truth for skills on this machine. The canonical source is
`skills/<name>/`; agent-specific directories (`~/.agents/skills`,
`~/.claude/skills`) receive per-skill symlinks via `install.py` — never edit
skills there, edit them here.

Rules:

- **Added, renamed, or removed a skill?** Run `uv run install.py` before
  finishing so the symlinks in `~/.agents/skills` and `~/.claude/skills`
  stay current. Editing an existing skill needs nothing — symlinks pick it
  up immediately.
- **Creating or changing a skill?** Follow `skills/jacob-create-skill/SKILL.md`
  — it is the house process (clarify → scaffold → draft → validate → trigger
  test → learnings loop).
- Every skill must pass
  `uv run skills/jacob-create-skill/scripts/validate_skill.py skills/<name>`
  before commit. Treat warnings as decisions, not noise.
- Skills are model-invocable by default (no `disable-model-invocation`
  field). Add `disable-model-invocation: true` only for skills that must
  never fire on their own.
- Keep the skill count low. Fold new material into an existing skill
  (`python-standards` for anything Python tooling/testing related) before
  creating a new one.
- All bundled Python is a single file with a PEP 723 `# /// script` header,
  runnable via `uv run` with no environment setup.
- **Git workflow:** the `git-ops` skill. In short: work directly on main,
  commit at every working checkpoint, push after every commit, end every
  task with a clean working tree — no feature branches or PRs unless the
  user explicitly requests one.
- Never edit a skill's SKILL.md to record a one-off correction — append a
  dated line to that skill's `LEARNINGS.md` instead. Folding learnings into
  SKILL.md is a deliberate, reviewed step.
