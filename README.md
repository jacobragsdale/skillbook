# jacob-agent-skills

Personal library of [Agent Skills](https://agentskills.io) — portable
SKILL.md folders that work in Cursor, Claude Code, and any agent implementing
the open standard.

## Layout

```
skills/                    # Mac-side dev skills — one folder per skill
  jacob-create-skill/      # meta-skill: creates and improves other skills
    SKILL.md               # instructions (loaded when the skill triggers)
    LEARNINGS.md           # dated corrections from real use (self-improvement)
    scripts/               # self-contained uv/PEP 723 scripts
    references/            # docs loaded on demand
voice-skills/              # jarvis (voice assistant) skills — see its README
install.py                 # symlinks skills/ into agent skill directories
scripts/install-server.sh  # symlinks voice-skills/ into ~/.codex/skills (server)
Makefile                   # `make deploy` = sync voice skills to the server
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

## Voice skills (jarvis)

`voice-skills/` deploys to the home server over git, not symlinks: the
server keeps a clone at `~/jarvis-skills` with a write deploy key, because
jarvis edits its own skills by voice — everything commits straight to
`main` and goes live immediately (post-hoc review, not a gate). A host
timer pulls the server clone every ten minutes, so Mac pushes to `main`
reach jarvis on their own; `make deploy` does the same pull instantly, and
`make review-jarvis` lists jarvis's recent commits. Conventions differ
from dev skills — read `voice-skills/README.md` before writing one.

## Creating a skill

Ask your agent to create one — `jacob-create-skill` triggers on it and walks
through clarifying questions, scaffolding, validation, and a trigger test.
By hand:

```bash
uv run skills/jacob-create-skill/scripts/init_skill.py my-skill --dir skills
uv run skills/jacob-create-skill/scripts/validate_skill.py skills/my-skill
```

## Learnings harvest & metrics

The `LEARNINGS.md` loop runs itself — developers never think about it:

1. **Capture** — agents append dated corrections to a skill's `LEARNINGS.md`
   after use. Because skills are symlinked, those writes land in this repo's
   local clone as uncommitted changes.
2. **Ship** — a daily 17:00 job (`scripts/harvest.py`, installed by
   `install.py`) fast-forwards `main` (keeping everyone's skills current),
   then commits any new `LEARNINGS.md` entry lines and metrics events to a
   `learnings/<user>` branch in a temporary worktree and opens one PR per
   developer. Offline or nothing new → silent no-op.
3. **Fold** — learnings PRs are human-reviewed (they change every teammate's
   agent behavior). Recurring lessons get folded into SKILL.md via
   `jacob-create-skill`, deliberately.

Usage metrics ride the same loop: a Claude Code hook
(`scripts/log_skill_use.py`, wired by `install.py` — it asks once) logs each
Skill invocation to `metrics/<user>.jsonl`. See `metrics/README.md` for
exactly what is (and is not) recorded. Read the numbers:

```bash
uv run scripts/skill_stats.py            # per-skill usage, users, correction density
uv run scripts/harvest.py --dry-run      # what would ship right now
```

## Conventions

- Every skill passes `validate_skill.py` before commit.
- Bundled Python is single-file with PEP 723 inline deps, run via `uv run`.
- Every skill has a `LEARNINGS.md`: agents append dated corrections after
  use; recurring lessons get folded into SKILL.md deliberately.
- `metrics/` is machine-written; never hand-edit it.
