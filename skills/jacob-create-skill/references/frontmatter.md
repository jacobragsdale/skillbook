# Skill metadata by target

Verified 2026-07-18. Start with the agentskills.io core, then add only the
extensions required by confirmed target clients.

## Contents

- Routing windows by client
- Core Agent Skills profile
- Cursor profile
- Cursor reliability gotchas
- Claude Code profile
- Codex profile
- House choices
- Sources

## Routing windows by client

What each client actually shows the model when deciding whether to invoke a
skill — the numbers behind the house description rules:

| Client | Router-visible description |
|---|---|
| Cursor | ~80 chars in cloud sessions (hard ellipsis); variable local trimming that grows with installed skill count |
| Claude Code | up to 1,536 chars per entry (description + `when_to_use`); whole listing budgeted at 1% of the context window, least-invoked skills dropped first on overflow |
| Codex | listing capped at 2% of the context window or 8,000 chars; descriptions shortened to fit |

House rule: the first sentence must be self-sufficient in ~80 characters;
keep the whole description under 250.

## Core Agent Skills profile

Strict core validation permits only these frontmatter fields:

| Field | Required | Constraints |
|---|---|---|
| `name` | yes | 1–64 chars; lowercase letters, digits, single hyphens; must match the folder name |
| `description` | yes | 1–1024 chars; describe what it does and when to use it |
| `license` | no | Short license name or bundled license-file pointer |
| `compatibility` | no | 1–500 chars describing non-obvious environment requirements |
| `metadata` | no | Mapping of string keys to string values |
| `allowed-tools` | no | Experimental space-separated pre-approved-tool string |

Vendor fields make a skill core-shaped but not strictly core-valid. The
reference validator rejects unexpected frontmatter rather than guaranteeing
that every client will ignore it.

## Cursor profile

Cursor documents these additions:

| Field | Meaning |
|---|---|
| `paths` | Comma-separated glob string or list; surface only for matching files (legacy alias `globs` accepted) |
| `disable-model-invocation` | `true` makes the skill explicit `/skill-name` only |

Cursor documents only `name`, `description`, `paths`, `disable-model-invocation`,
and `metadata`; assume `license`, `compatibility`, and `allowed-tools` are
ignored rather than honored.

Cursor discovers `.agents/skills/`, `.cursor/skills/`, `.claude/skills/`, and
`.codex/skills/` at project and user scope. Nested project skill directories are
automatically scoped to their subtree. Cursor also walks nested category folders
inside a skill root.

## Cursor reliability gotchas

Before blaming a description for not triggering in Cursor, verify discovery —
these are all confirmed failure modes, and every one masquerades as a
description-quality problem:

- Cursor discovers skills **at startup only** — reload or start a new session
  after adding a skill or changing frontmatter (Claude Code live-watches its
  skill directories; Cursor does not).
- Sessions launched seconds after Cursor starts can get an **empty skill
  list** (confirmed race); wait a moment or reload.
- `.agents/skills` entries have previously been discovered (visible in
  Settings and the `/` menu) but **omitted from the system-prompt skill
  catalog**, so the model could not auto-invoke them. Symlink discovery has
  also regressed across Cursor releases. After a Cursor update, sanity-check
  by asking the agent "what skills are available?".
- **Cursor subagents get no skills at all.** For a background/sub agent that
  must follow a skill, embed the SKILL.md's absolute path in the task prompt
  and tell it to read the file.
- Auto-triggering is **best-effort** everywhere (passive descriptions measure
  roughly 20–50% activation). For behavior that must always hold, use an
  always-on rule or explicit `/skill-name` — see
  `placement-and-conflicts.md`.

## Claude Code profile

Claude Code currently documents these extensions:

| Field | Meaning |
|---|---|
| `when_to_use` | Additional trigger context appended to the description |
| `argument-hint` | Autocomplete hint for expected arguments |
| `arguments` | Positional argument names, as a string or list |
| `disable-model-invocation` | Prevent automatic loading; keep explicit `/name` |
| `user-invocable` | `false` hides the skill from the `/` menu |
| `allowed-tools` | Pre-approved tools; string or list |
| `disallowed-tools` | Tools removed while the skill is active |
| `model` / `effort` | Turn-scoped model and effort override |
| `context` | `fork` runs the skill in an isolated subagent context |
| `agent` | Agent type used with `context: fork` |
| `hooks` | Lifecycle hooks scoped to the skill |
| `paths` | Glob patterns for file-scoped automatic activation |
| `shell` | `bash` or `powershell` for dynamic shell blocks |

Claude Code discovers `.claude/skills/` at personal, project, nested-project,
plugin, and managed scopes. This repository therefore maintains Claude symlinks
even though Cursor can also discover the canonical `.agents` location.

When `disable-model-invocation: true`, Claude does not put the description in
model context. A description test then measures menu/catalog quality and future
auto-trigger behavior, not current automatic invocation.

## Codex profile

Keep `SKILL.md` frontmatter on the core fields. Put Codex-specific UI,
dependency, and invocation metadata in `agents/openai.yaml`:

```yaml
policy:
  allow_implicit_invocation: false
```

`allow_implicit_invocation` defaults to `true`. Setting it to `false` keeps
explicit `$skill-name` invocation while preventing implicit selection. Codex
discovers `.agents/skills/` from the working directory toward the repository
root, plus user/admin/system locations, and follows symlinked skill folders.

## House choices

- New repository skills default to automatic invocation — no
  `disable-model-invocation` field. Add `disable-model-invocation: true` only
  for skills that must never fire on their own (orchestrator sub-steps,
  destructive operations).
- Add the Codex policy sidecar when Codex is a confirmed target.
- Use `--strict-core` scaffolding and `--profile core` validation when strict
  standard conformance matters more than vendor invocation controls.
- Treat `allowed-tools` as convenience pre-approval, never a safety boundary.
- Validate every claimed client profile; portability is tested, not assumed.

## Sources

- https://agentskills.io/specification
- https://cursor.com/docs/skills
- https://code.claude.com/docs/en/skills
- https://developers.openai.com/codex/skills
- Cursor 80-char truncation and gotchas (staff-confirmed):
  https://forum.cursor.com/t/skill-descriptions-are-truncated-in-initial-agent-context/163761,
  https://forum.cursor.com/t/local-skill-loading-is-inconsistent-or-non-existent/163768,
  https://forum.cursor.com/t/cursor-agent-skills-in-agents-skills/161142
