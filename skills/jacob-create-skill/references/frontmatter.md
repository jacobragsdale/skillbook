# Skill metadata by target

Verified 2026-07-09. Start with the agentskills.io core, then add only the
extensions required by confirmed target clients. This repository keeps the
first 250 description characters as its portable routing budget.

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
| `paths` | Comma-separated glob string or list; surface only for matching files |
| `disable-model-invocation` | `true` makes the skill explicit `/skill-name` only |

Cursor discovers `.agents/skills/`, `.cursor/skills/`, `.claude/skills/`, and
`.codex/skills/` at project and user scope. Nested project skill directories are
automatically scoped to their subtree. Cursor also walks nested category folders
inside a skill root.

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

- New repository skills default to explicit invocation for Cursor and Claude
  using `disable-model-invocation: true`.
- Add the Codex policy sidecar when Codex is a confirmed target.
- Use `--strict-core` scaffolding and `--profile core` validation when strict
  standard conformance matters more than vendor invocation controls.
- Treat `allowed-tools` as convenience pre-approval, never a safety boundary.
- Validate every claimed client profile; portability is tested, not assumed.

## Sources

- https://agentskills.io/specification
- https://cursor.com/docs/skills
- https://code.claude.com/docs/en/skills
- https://learn.chatgpt.com/docs/build-skills
