# skillbook

`skillbook` is Jacob's canonical library of portable
[Agent Skills](https://agentskills.io/). Each skill is a `SKILL.md` instruction
file with optional scripts, references, assets, and client metadata.

[`skills/`](skills/) is the source of truth. Edit a canonical skill here, never
an installed copy. The repository contains no skill-serving service or other
runtime: agents receive ordinary skill directories through Agent Plugins.

## Current skills

Each skill is a folder under [`skills/`](skills/) whose name matches the
`name:` field in its `SKILL.md`.

| Skill | Purpose |
| --- | --- |
| [`herdr`](skills/herdr/SKILL.md) | Control Herdr panes, tabs, workspaces, and other agents from a Herdr-managed session. Vendored from [herdr v0.8.2](https://github.com/herdrdev/herdr/blob/v0.8.2/skills/herdr/SKILL.md). |
| [`jacob-create-skill`](skills/jacob-create-skill/SKILL.md) | Create, improve, scaffold, and validate reusable agent skills. |
| [`jacob-home-server`](skills/jacob-home-server/SKILL.md) | Operate the home server: Docker stacks, SOPS secrets, deployments, backups, media, networking, and recovery. |
| [`python-standards`](skills/python-standards/SKILL.md) | Apply high-integrity Python, Pydantic, typing, pandas, async, performance, uv, Ruff, and ty standards. |
| [`python-testing`](skills/python-testing/SKILL.md) | Design and review pytest tests, fixtures, and pandas test data. |
| [`typescript-standards`](skills/typescript-standards/SKILL.md) | Apply strict TypeScript, Angular, ESLint, template, API, async, and runtime-validation standards. |
| [`write-diataxis-docs`](skills/write-diataxis-docs/SKILL.md) | Write and audit technical documentation as tutorials, how-to guides, reference, or explanation. |

Skills are model-invocable by default through their descriptions.

## Publish the skills

Agent Plugins reads [`agent-plugins.json`](agent-plugins.json), whose packages
contain only `skill` components under `skills/`. Every skill is available as a
standalone package; related skills may also appear together in an optional
bundle. Installed skills are namespaced copies (`skillbook-<name>`), not live
links into this repository.

Requires `python3`, `zip`, `curl`, and `shasum`. Upload uses the Nexus `admin`
password from `NEXUS_PASSWORD`, the macOS keychain item `repo.ragsdale.dev`, or
a curl prompt.

```bash
# Pack and validate without uploading
./scripts/publish-source.sh --dry-run

# Replace https://repo.ragsdale.dev/repository/files/sources/skillbook-latest.zip
./scripts/publish-source.sh
```

The script rejects non-skill components, zips the manifest and referenced skill
directories, replaces the existing Nexus artifact, and verifies the anonymous
download against the local SHA-256 checksum. After publishing, refresh
Skillbook in Agent Plugins and update already-installed packages. Reload an
agent after adding a skill or changing frontmatter.

## Create or update a skill

Use [`jacob-create-skill`](skills/jacob-create-skill/SKILL.md) as the house
process: clarify the intent and boundary, scaffold, draft, and validate.

```bash
uv run skills/jacob-create-skill/scripts/init_skill.py my-skill --dir skills
uv run skills/jacob-create-skill/scripts/validate_skill.py skills/my-skill
```

Every skill must pass validation with no unresolved warnings before commit.
Descriptions are directive triggers: put the capability and main keywords in
the first sentence, then describe when the skill should be used and include an
`even if` clause. Skills are automatic by default; add
`disable-model-invocation: true` only when a skill must never run implicitly.

Bundled Python is self-contained: each script has a PEP 723 header and runs
with `uv run`, without repository environment setup. Put stable supporting
material in `references/` and reusable files in `assets/`.

## Verify changes

Run a changed skill's validator:

```bash
uv run skills/jacob-create-skill/scripts/validate_skill.py skills/<name>
```

For a new, renamed, or removed skill, update `agent-plugins.json` and publish
the refreshed artifact. The full workflow is documented in
[`AGENTS.md`](AGENTS.md).

## Repository layout

```text
skills/<name>/SKILL.md       # canonical skill instructions
skills/<name>/scripts/       # optional self-contained uv scripts
skills/<name>/references/    # optional on-demand documentation
skills/<name>/assets/        # optional reusable templates or files
agent-plugins.json           # skills-only artifact manifest
scripts/publish-source.sh    # packs the skills and replaces the Nexus artifact
AGENTS.md                    # repository workflow and maintenance rules
```

Keep the skill count low: extend an existing skill when its trigger, boundary,
and output remain coherent. Add a new skill only when it has a genuinely
independent capability, dependency, or invocation policy.
