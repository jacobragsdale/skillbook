# Working in this repo

This is a library of plain Agent Skills (agentskills.io format) and the single
source of truth for skills on this machine. The canonical source is
`skills/<name>/`. Skill Manager installs namespaced copies
(`~/.agents/skills/skillbook-*`, `~/.claude/skills/skillbook-*`) from the
Nexus zip — never edit those copies, edit them here.

Rules:

- **Added, renamed, or removed a skill?** Update `skill-manager.json` in
  the same change: every `skills/<name>/` directory needs a standalone v2
  skill package, and any optional bundle of those skills must list that
  component. Then run `./scripts/publish-source.sh` and
  refresh/update Skillbook in Skill Manager. Agents do not see an edit
  until that snapshot is published and the app updates. Reload the agent
  after a new skill or a frontmatter change.
- **Creating or changing a skill?** Follow `skills/jacob-create-skill/SKILL.md`
  — it is the house process (clarify → scaffold → draft → validate).
- Every skill must pass
  `uv run skills/jacob-create-skill/scripts/validate_skill.py skills/<name>`
  before commit. Treat warnings as decisions, not noise.
- Run the test suite (`uv run tests/<file>.py` for each file in `tests/`)
  before committing changes to skills or tooling.
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
- **Git workflow:** the `git-ops` skill. In short: work directly on main,
  commit at every working checkpoint, push after every commit, end every
  task with a clean working tree — no feature branches or PRs unless the
  user explicitly requests one.
