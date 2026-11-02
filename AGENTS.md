# Working in this repo

This is a library of plain Agent Skills (agentskills.io format) and the single
source of truth for skills on this machine. The canonical source is
`skills/<name>/`. The local install is a symlink per skill in
`~/.claude/skills/` and `~/.agents/skills/`, so an edit here is live at once;
the README says how to link a skill.

Rules:

- **Added, renamed, or removed a skill?** Add, move, or delete its symlinks
  in `~/.claude/skills/` and `~/.agents/skills/` in the same task, and update
  the README's skill table. Reload the agent after a new skill or a
  frontmatter change.
- **Creating or changing a skill?** Follow `skills/jacob-create-skill/SKILL.md`
  — it is the house process (clarify → scaffold → draft → validate).
- Every skill must pass
  `uv run skills/jacob-create-skill/scripts/validate_skill.py skills/<name>`
  before commit. Treat warnings as decisions, not noise.
- Skill descriptions are directive triggers: capability and top keywords in
  the first sentence (~80 chars), then "Use when …" with an "even if …"
  clause. The validator enforces the shape.
- Skills are model-invocable by default (no `disable-model-invocation`
  field). Add `disable-model-invocation: true` only for skills that must
  never fire on their own.
- Keep the skill count low. Fold new material into an existing skill
  (`python-standards` for Python implementation or tooling) before
  creating a new one.
- All bundled Python is a single file with a PEP 723 `# /// script` header,
  runnable via `uv run` with no environment setup.
- **Git workflow:** work directly on main, commit at every working
  checkpoint, push after every commit, end every task with a clean working
  tree — no feature branches or PRs unless the user explicitly requests one.
