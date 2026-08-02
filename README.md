# skillbook

Personal library of [Agent Skills](https://agentskills.io/) in the portable
`SKILL.md` format. This repository is the single source of truth for the
skills installed on this machine: edit `skills/<name>/`, never an installed
copy.

## Skills

Each skill is a folder under [`skills/`](skills/) whose name matches the
`name:` field in its `SKILL.md`.

| Skill | Purpose |
| --- | --- |
| [`jacob-create-skill`](skills/jacob-create-skill/SKILL.md) | Create, improve, and validate skills, including scaffolding, trigger tests, and forward tests. |
| [`git-ops`](skills/git-ops/SKILL.md) | Keep solo repositories on `main`, commit at working checkpoints, push after each commit, and finish clean. |
| [`jacob-home-server`](skills/jacob-home-server/SKILL.md) | Operate the home server: Docker stacks, SOPS secrets, deployments, backups, media, networking, and recovery. |
| [`python-standards`](skills/python-standards/SKILL.md) | Apply high-integrity Python, Pydantic, Pandera, pandas, async, performance, uv, Ruff, and Pyrefly standards. |
| [`python-testing`](skills/python-testing/SKILL.md) | Design and review pytest tests, fixtures, and pandas/Pandera test data. |
| [`typescript-standards`](skills/typescript-standards/SKILL.md) | Apply strict TypeScript, Angular, ESLint, template, API, async, and runtime-validation standards. |
| [`write-diataxis-docs`](skills/write-diataxis-docs/SKILL.md) | Write and audit technical documentation as tutorials, how-to guides, reference, or explanation. |
| [`releases`](skills/releases/SKILL.md) | Maintain local release records backed by live Azure Repos evidence. This skill is explicit-only. |

Skills are model-invocable by default through their descriptions. The
`releases` skill is deliberately manual-only because it reads and writes local
release records and requires an Azure DevOps preflight.

## Install

Requires [uv](https://docs.astral.sh/uv/).

```bash
# Preview changes
uv run install.py --dry-run

# Install one symlink per skill
uv run install.py
```

The installer links every canonical skill into both `~/.agents/skills` and
`~/.claude/skills`. It also prunes links into this repository whose source
skill has been removed. `--force` can replace a conflicting symlink; it does
not delete a real file or directory. To remove this repository's installed
links:

```bash
uv run install.py --uninstall
```

Run the installer after adding, renaming, or removing a skill. Editing an
existing skill needs no reinstall because the installed entries are symlinks;
Claude Code sees the change immediately, while Cursor needs a reload after a
new skill or frontmatter change.

## Create or update a skill

Use [`jacob-create-skill`](skills/jacob-create-skill/SKILL.md) as the house
process: clarify the intent and boundary, scaffold, draft, validate, test
triggers, and forward-test the result.

To scaffold a new skill:

```bash
uv run skills/jacob-create-skill/scripts/init_skill.py my-skill --dir skills
```

Then edit the canonical `skills/my-skill/SKILL.md` and validate it:

```bash
uv run skills/jacob-create-skill/scripts/validate_skill.py skills/my-skill
```

Every skill must pass validation with no unresolved warnings before commit.
Descriptions are directive triggers: put the capability and main keywords in
the first sentence, then describe when the skill should be used and include
an `even if` clause. Skills are automatic by default; add
`disable-model-invocation: true` only when a skill must never run implicitly.

Bundled Python is self-contained: each script has a PEP 723 header and runs
with `uv run`, without a repository environment setup. Put stable supporting
material in `references/` and reusable files in `assets/` when a skill needs
them.

## Verify changes

The repository's regression tests are standalone uv scripts. Run every test
file before committing changes to skills or tooling:

```bash
uv run tests/test_install.py
uv run tests/test_jacob_create_skill.py
```

For a skill change, also run its validator. For a new, renamed, or removed
skill, run `uv run install.py` and confirm the installed links are current.
The repository workflow is documented in [`AGENTS.md`](AGENTS.md).

## Layout

```text
skills/<name>/SKILL.md       # canonical skill instructions
skills/<name>/scripts/       # optional self-contained uv scripts
skills/<name>/references/    # optional on-demand documentation
skills/<name>/assets/        # optional reusable templates or files
rules/                       # always-on rules referenced by repo instructions
tests/                       # regression tests for the skill tooling
install.py                   # installs and prunes per-skill symlinks
AGENTS.md                    # repository workflow and maintenance rules
```

Keep the skill count low: extend an existing skill when its trigger, boundary,
and output remain coherent. Add a new skill only when it has a genuinely
independent capability, dependency, or invocation policy.
