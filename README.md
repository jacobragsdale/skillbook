# jacob-agent-skills

Personal library of [Agent Skills](https://agentskills.io) — portable
SKILL.md folders that work in Cursor, Claude Code, and any agent implementing
the open standard.

## Layout

```
skills/                    # canonical source of truth — one folder per skill
  jacob-create-skill/      # meta-skill: creates and improves other skills
    SKILL.md               # instructions (loaded when the skill triggers)
    LEARNINGS.md           # dated corrections from real use (self-improvement)
    scripts/               # self-contained uv/PEP 723 scripts
    references/            # docs loaded on demand
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
immediately, and each skill's `LEARNINGS.md` stays versioned here. Re-run
after adding a new skill.

Voice-assistant skills for jarvis live with the assistant
(`~/Development/jarvis/skills/`), not here — they follow different
conventions and deploy with the app.

## Creating a skill

Ask your agent to create one — `jacob-create-skill` triggers on it and walks
through clarifying questions, scaffolding, validation, and a trigger test.
By hand:

```bash
uv run skills/jacob-create-skill/scripts/init_skill.py my-skill --dir skills
uv run skills/jacob-create-skill/scripts/validate_skill.py skills/my-skill
```

## Conventions

- Every skill passes `validate_skill.py` before commit.
- Bundled Python is single-file with PEP 723 inline deps, run via `uv run`.
- Every skill has a `LEARNINGS.md`: agents append dated corrections after
  use; recurring lessons get folded into SKILL.md deliberately.
