# jacob-agent-skills

Personal library of [Agent Skills](https://agentskills.io) — portable
SKILL.md folders that work in Cursor, Claude Code, and any agent implementing
the open standard. This repo is the single source of truth for skills on
this machine; agent skill directories only ever hold symlinks into it.

## Skills

- `python-standards` — the house standard for Python repos: uv, one
  pyproject.toml, ruff, basedpyright, pytest + coverage ratchet, pre-commit,
  .env convention.
- `git-ops` — the solo git workflow: main only, frequent commits, push after
  every commit, clean tree at end of task.
- `jacob-home-server` — operating the home server.
- `jacob-create-skill` — meta-skill: creates and improves the other skills
  (scaffolder, validator, trigger testing, learnings loop).

Skills are model-invocable by default — the description is the trigger. Add
`disable-model-invocation: true` only for skills that must never fire on
their own.

## Layout

```
skills/                    # canonical source of truth — one folder per skill
  <name>/
    SKILL.md               # instructions (loaded when the skill triggers)
    LEARNINGS.md           # dated corrections from real use (self-improvement)
    scripts/               # self-contained uv/PEP 723 scripts (optional)
    references/            # docs loaded on demand (optional)
rules/                     # always-on rules, referenced from repo AGENTS.md files
tests/                     # regression tests for skill tooling
install.py                 # symlinks each skill into agent skill directories
```

## Install

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv run install.py            # symlink skills into ~/.agents/skills and ~/.claude/skills
uv run install.py --dry-run  # preview
uv run install.py --uninstall
```

Per-skill symlinks mean edits in this repo take effect everywhere
immediately. `install.py` only needs re-running when a skill is added,
renamed, or removed — agents working in this repo do that automatically
(see AGENTS.md).

Voice-assistant skills for jarvis live with the assistant
(`~/Development/jarvis/skills/`), not here — they follow different
conventions and deploy with the app.

## Creating a skill

Ask your agent — `jacob-create-skill` walks through clarifying questions,
scaffolding, validation, and a trigger test. By hand:

```bash
uv run skills/jacob-create-skill/scripts/init_skill.py my-skill --dir skills
uv run skills/jacob-create-skill/scripts/validate_skill.py skills/my-skill
```

## Conventions

- Every skill passes `validate_skill.py` before commit.
- Every skill has a `LEARNINGS.md`: agents append dated corrections after
  use; recurring lessons get folded into SKILL.md deliberately.
- Bundled Python (if any) is single-file with PEP 723 inline deps, run via
  `uv run`.
- Few skills, kept sharp — fold related material into an existing skill
  before creating a new one.
