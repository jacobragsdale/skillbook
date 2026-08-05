# skillbook

`skillbook` is Jacob's canonical library of portable
[Agent Skills](https://agentskills.io/). Each skill is a `SKILL.md` instruction
file with optional supporting text, scripts, references, and assets.

The repository can deliver those skills in two ways:

| Delivery path | Intended use | What it does |
| --- | --- | --- |
| Per-skill symlinks | Local agents that discover installed skills | `install.py` links each canonical `skills/<name>/` directory into the agent-specific skill directories. |
| MCP server | MCP hosts that should discover and load skills on demand | A local, read-only service exposes the catalog, complete `SKILL.md` files, and UTF-8 supporting files. |

In both cases, [`skills/`](skills/) remains the source of truth. Edit a
canonical skill here, never an installed copy.

## How MCP skill delivery works

The MCP server is a thin read-only view over [`skills/`](skills/). It does not
install, modify, or execute skills. It also does not preload the library into a
model's context when the host discovers the server.

### What the server serves

The server exposes:

- a summary for every directory matching `skills/<name>/SKILL.md`;
- the complete `SKILL.md` for one selected skill; and
- individual UTF-8 files inside that skill directory, including references and
  text-based scripts or assets.

Each summary contains the skill name, trigger description, `skill://` URI,
SHA-256 content hash, optional compatibility statement, and whether model
invocation is enabled. Catalog and file contents are read from disk on every
request, so edits are visible without restarting the server.

It does not expose `AGENTS.md`, `rules/`, tests, repository metadata, or files
outside a selected skill directory. It also excludes cache files, compiled
Python files, `.DS_Store`, and symlinks that escape the skill directory.

### What a client and model receive

The `2026-07-28` protocol is stateless. There is no `initialize` handshake and
no protocol session. Every request carries its protocol version, client
identity, and client capabilities. A client may call
[`server/discover`](https://modelcontextprotocol.io/specification/2026-07-28/server/discover)
before any other method, but discovery is optional; it can instead make a
normal request and handle an unsupported-version error.

Strictly speaking, the MCP host's client communicates with this service. The
model does not open the HTTP connection, and the host decides what MCP metadata
and results enter model context.

With the locked `mcp==2.0.0` SDK, `server/discover` returns:

| Item | Value |
| --- | --- |
| Protocol revision | `2026-07-28` |
| Server identity | Name `skillbook`, title `Skillbook`, version `0.1.0`, description `Jacob's canonical Agent Skills library.` |
| Capabilities | Tools, resources, prompts, list-change notifications, and resource subscriptions. No prompts are registered, so `prompts/list` is empty. |
| Server instructions | `Call list_skills` to find trigger descriptions, then `read_skill`, then any referenced `read_skill_file`. |
| Result metadata | `resultType: "complete"`, `ttlMs: 0`, `cacheScope: "private"`, and server identity in `_meta`. |
| Skill contents | None. Catalog and skill bodies require subsequent requests. |

The SDK advertises change notifications because it provides the
`subscriptions/listen` method. This application does not watch the filesystem
or proactively publish catalog changes. Its `ttlMs: 0` responses are
immediately stale, so clients should re-fetch when they next need the catalog;
every fetch reads the current files from disk.

The normal model-facing sequence is:

1. The host discovers three tool definitions, one fixed resource, and two
   resource templates. It receives their names, descriptions, schemas, and
   read-only safety hints—not the contents of all skills.
2. The host exposes whichever tools it permits to the model. When a task appears
   relevant, the model can call `list_skills` and receive all skill summaries.
3. The model calls `read_skill` for the matching skill. Only then does that
   complete `SKILL.md` enter the tool result.
4. If the selected skill refers to another file, the model calls
   `read_skill_file` for that specific path.

For example, a Python task can produce this retrieval sequence:

```text
list_skills()
  -> summaries for all skills

read_skill(name="python-standards")
  -> complete SKILL.md + available file paths

read_skill_file(name="python-standards", path="references/pandera.md")
  -> that file's text, media type, and hash
```

The final file call uses a real path referenced by `python-standards`; the model
should request only paths listed or referenced by the selected skill.

### Tools and resources expose the same library differently

The current specification distinguishes who controls retrieval:

- [**Tools are model-controlled.**](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
  A host can expose `list_skills`, `read_skill`, and `read_skill_file` to the
  model so it can retrieve instructions as needed.
- [**Resources are application-controlled.**](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)
  A host can read the catalog or a skill URI itself and attach that content to
  context.

The server provides both interfaces so different MCP hosts can use the same
catalog. It registers no MCP prompts. Resources are not automatically injected
into model context merely because the server advertises them.

Retrieval is also not enforcement. A successful `read_skill` call proves that
the server delivered the instructions; it does not prove that a host exposed
them, that the model followed them, or that the result was correct. Likewise,
`model_invocation_enabled: false` is advisory metadata that the client must
honor; the underlying skill remains readable.

### Standards status of skills over MCP

The `2026-07-28` core specification defines tools, resources, and prompts; it
does not define a finalized skill primitive. The MCP Skills Over MCP Working
Group's resource-based
[Skills Extension (SEP-2640)](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2640)
is still in review. This server therefore uses stable core tools and resources
and does not advertise the draft extension. Revisit that choice when the
extension is finalized and supported by target hosts.

## Run the MCP server

### Prerequisites

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)

### Start the server

From the repository root:

```bash
uv sync --locked
uv run skillbook-mcp
```

The server listens on `127.0.0.1:8000` and exposes Streamable HTTP at:

```text
http://127.0.0.1:8000/mcp
```

Keep that process running, then register the URL as a Streamable HTTP server in
your MCP host. Configuration syntax is host-specific; the connection needs only
the URL because this local experiment has no authentication.

### Verify the live catalog

In another terminal:

```bash
curl http://127.0.0.1:8000/health
```

The response contains `status: "ok"` and the number of currently valid skills:

```json
{"status":"ok","skills":9}
```

The count is computed from the live catalog and changes when skills are added or
removed. FastAPI's OpenAPI UI for the health route is available at
<http://127.0.0.1:8000/docs>.

## MCP reference

With the locked dependencies, the server uses
[`mcp==2.0.0`](https://pypi.org/project/mcp/), the current stable official
Python SDK for
[MCP revision `2026-07-28`](https://modelcontextprotocol.io/specification/2026-07-28).
The transport is stateless Streamable HTTP with one JSON-RPC request per HTTP
`POST` and JSON responses.

There is no initialization exchange or `Mcp-Session-Id`. `server/discover`
reports the supported protocol revision, capabilities, server identity, and
usage instructions. Every modern request repeats its protocol version and
client capabilities; every result includes `resultType` and server identity.

### Tools

| Tool | Arguments | Result |
| --- | --- | --- |
| `list_skills` | None | All skill summaries, sorted by name. |
| `read_skill` | `name` | The selected summary, complete `SKILL.md`, and all catalogued file paths under the skill directory. |
| `read_skill_file` | `name`, `path` | One file's skill name, relative path, media type, SHA-256 hash, and UTF-8 content. |

`name` must use lowercase letters, digits, and single hyphens. `path` must be a
relative POSIX path inside the named skill directory. All three definitions
include `readOnlyHint: true` and `openWorldHint: false`.

### Resources

| Kind | URI | Media type | Result |
| --- | --- | --- | --- |
| Resource | `skills://catalog` | `application/json` | JSON array containing the live skill summaries. |
| Resource template | `skill://{name}` | `text/markdown` | Complete `SKILL.md` for one skill. |
| Resource template | `skill-file://{name}/{+path}` | `text/plain` | Contents of one UTF-8 file inside a skill. |

### Modern response metadata

The SDK supplies the fields required by the `2026-07-28` specification:

| Field | Value | Meaning |
| --- | --- | --- |
| `resultType` | `complete` | The request completed without a multi-round-trip input request. |
| `ttlMs` | `0` on `server/discover`, list operations, and resource reads | The live filesystem result is immediately stale and may be re-fetched when needed. |
| `cacheScope` | `private` on cacheable results | A cached response must not be reused across authorization contexts. |
| `_meta.io.modelcontextprotocol/serverInfo` | Skillbook identity | Identifies the server on every result. |

On Streamable HTTP, a conforming client also sends `MCP-Protocol-Version` and
`Mcp-Method` headers on every request, plus `Mcp-Name` for tool calls and
resource reads. The SDK validates those headers against the JSON-RPC body and
returns HTTP 400 with error `-32020` when they do not match.

### Response fields

`SkillSummary`:

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | string | Exact skill name and directory name. |
| `description` | string | Frontmatter description used as the skill's trigger. |
| `uri` | string | `skill://<name>` resource URI. |
| `sha256` | string | SHA-256 hash of the complete `SKILL.md` text. |
| `compatibility` | string or null | Optional frontmatter compatibility statement. |
| `model_invocation_enabled` | boolean | Inverse of `disable-model-invocation`; advisory to the client. |

`read_skill` adds:

| Field | Type | Meaning |
| --- | --- | --- |
| `summary` | `SkillSummary` | Metadata for the selected skill. |
| `content` | string | Complete UTF-8 `SKILL.md`, including frontmatter. |
| `files` | array of strings | Safe relative file paths catalogued under the skill directory. A listed binary file is not readable through this text-only server. |

`read_skill_file` returns:

| Field | Type | Meaning |
| --- | --- | --- |
| `skill` | string | Skill that owns the file. |
| `path` | string | Relative POSIX path requested by the client. |
| `media_type` | string | Type inferred from the filename extension, or `text/plain`. |
| `sha256` | string | SHA-256 hash of the returned text. |
| `content` | string | Complete UTF-8 file contents. |

### Validation and errors

The catalog rejects malformed frontmatter, a frontmatter name that differs from
its directory, unknown skills or files, absolute paths, path traversal, Windows
path separators, non-regular files, escaping symlinks, and non-UTF-8 content.
Binary assets can appear in a skill directory but cannot be read through this
text-only MCP surface.

### Security boundary

This server is intended only for the local machine. It binds to loopback, and
the SDK enables localhost host and Origin checks to reduce DNS-rebinding risk.
It has no authentication or browser CORS policy. Do not bind it to a LAN or
public interface without adding an explicit deployment security design.

The registered tool inputs contain only a skill name and optional file path.
This implementation has no prompt input, telemetry, or usage database.

## Current skills

Each skill is a folder under [`skills/`](skills/) whose name matches the
`name:` field in its `SKILL.md`.

| Skill | Purpose |
| --- | --- |
| [`git-ops`](skills/git-ops/SKILL.md) | Keep solo repositories on `main`, commit at working checkpoints, push after each commit, and finish clean. |
| [`jacob-create-skill`](skills/jacob-create-skill/SKILL.md) | Create, improve, and validate skills, including scaffolding, trigger tests, and forward tests. |
| [`jacob-home-server`](skills/jacob-home-server/SKILL.md) | Operate the home server: Docker stacks, SOPS secrets, deployments, backups, media, networking, and recovery. |
| [`mermaid`](skills/mermaid/SKILL.md) | Create and render viewer-focused Mermaid engineering diagrams. |
| [`python-standards`](skills/python-standards/SKILL.md) | Apply high-integrity Python, Pydantic, Pandera, pandas, async, performance, uv, Ruff, and Pyrefly standards. |
| [`python-testing`](skills/python-testing/SKILL.md) | Design and review pytest tests, fixtures, and pandas/Pandera test data. |
| [`releases`](skills/releases/SKILL.md) | Maintain local release records backed by live Azure Repos evidence. This skill is explicit-only. |
| [`typescript-standards`](skills/typescript-standards/SKILL.md) | Apply strict TypeScript, Angular, ESLint, template, API, async, and runtime-validation standards. |
| [`write-diataxis-docs`](skills/write-diataxis-docs/SKILL.md) | Write and audit technical documentation as tutorials, how-to guides, reference, or explanation. |

Skills are model-invocable by default through their descriptions. The
`releases` skill is deliberately manual-only because it reads and writes local
release records and requires an Azure DevOps preflight.

## Install skills locally

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
the first sentence, then describe when the skill should be used and include an
`even if` clause. Skills are automatic by default; add
`disable-model-invocation: true` only when a skill must never run implicitly.

Bundled Python is self-contained: each script has a PEP 723 header and runs
with `uv run`, without a repository environment setup. Put stable supporting
material in `references/` and reusable files in `assets/` when a skill needs
them.

## Verify changes

Run the MCP contract tests after changing the server or its catalog:

```bash
uv run pytest tests/test_mcp_catalog.py tests/test_mcp_server.py
```

Run every standalone tooling test after changing skills or skill tooling:

```bash
uv run tests/test_install.py
uv run tests/test_jacob_create_skill.py
```

For a skill change, also run its validator. For a new, renamed, or removed
skill, run `uv run install.py` and confirm the installed links are current.
The repository workflow is documented in [`AGENTS.md`](AGENTS.md).

## Repository layout

```text
src/skillbook_mcp/           # read-only catalog and MCP/FastAPI server
skills/<name>/SKILL.md       # canonical skill instructions
skills/<name>/scripts/       # optional self-contained uv scripts
skills/<name>/references/    # optional on-demand documentation
skills/<name>/assets/        # optional reusable templates or files
rules/                       # always-on rules referenced by repo instructions
tests/                       # regression and MCP contract tests
install.py                   # installs and prunes per-skill symlinks
AGENTS.md                    # repository workflow and maintenance rules
```

Keep the skill count low: extend an existing skill when its trigger, boundary,
and output remain coherent. Add a new skill only when it has a genuinely
independent capability, dependency, or invocation policy.
