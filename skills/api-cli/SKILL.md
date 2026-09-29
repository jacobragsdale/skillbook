---
name: api-cli
description: "Generate agent-first Python CLIs from OpenAPI, Swagger, or AsyncAPI specs. Use when the user wants a CLI for a REST or websocket API, or to wrap a service's API for agents — even if they only share a spec URL. Not for SDKs or MCP servers."
---

# API to agent-first CLI

Turn one or more OpenAPI 2/3 or AsyncAPI 2/3 specs into an installed Python
CLI whose main user is an agent: search-first discovery, compact help, and
small JSON output. This skill generates and verifies the CLI; it does not
design APIs, write SDKs, or build MCP servers.

## Workflow

1. **Get the spec.** Use the URL or file the user gave; otherwise probe the
   service's usual spec paths (`/openapi.json`, `/swagger.json`,
   `/v3/api-docs`, `/swagger/v1/swagger.json`, `/api/openapi.json`; Gitea and
   Forgejo serve `/swagger.v1.json`). Websocket APIs need an AsyncAPI
   document. If no spec exists, stop and say so; write one only when asked.
2. **Pick the names.** `--name` becomes the command. Use the service's name,
   or `<service>-api` when the service ships its own CLI under that name
   (gitea, docker, gh) or `command -v <name>` finds something. `--env`
   defaults to the upper-cased name; reuse a variable users already have,
   e.g. `--env GITHUB` for `GITHUB_TOKEN`.
3. **Build.** Run the generator; `--help` documents every flag:

   ```bash
   uv run <this-skill-dir>/scripts/build.py SPEC [SPEC ...] --name NAME [--base-url URL] [--auth AUTH]
   ```

   It writes a uv project to `~/dev/NAME` (`--out DIR` to change it; the
   steps below say `~/dev/NAME` for either) and prints the command and group
   counts plus warnings. Several specs merge into one command tree, so pass
   a service's OpenAPI and AsyncAPI documents together. Prefix a spec as
   `ns=SPEC` to give it its own namespace; do that for separate services,
   and the build fails with that hint when two specs define the same command.
4. **Fix what the report flags**, then rebuild:
   - `no absolute server URL`: pass `--base-url`. FastAPI and most
     self-hosted apps ship an empty or relative `servers` entry.
   - Auth comes from the spec's security schemes. Override it with `--auth`
     when the spec declares none (GitHub: `bearer`) or the token needs a
     prefix; the build warns about an unprefixed `Authorization` key and
     quotes what the spec says (Gitea: `header:Authorization:token {token}`).
   - Unsupported parameters (cookies) are listed; tell the user.
5. **Verify.** Every step must pass before you report success:

   ```bash
   cd ~/dev/NAME && uv sync && git init -q && git add -A   # sync first so uv.lock is tracked
   uv run pytest -q                         # every command's help, dry-run and search
   uv run pre-commit run --all-files        # house ruff, format, uv-lock, ty
   uv run NAME && uv run NAME search "<a task in the user's words, else the API's most common one>"
   uv run NAME <group> <action> --help
   uv run NAME <group> <action> ... --fields <2-3 fields>   # one live, read-only call
   ```

   Never verify with a write: preview POST, PUT, PATCH and DELETE with
   `--dry-run`. A 401 or 403 means a missing credential; name the variable
   for the user instead of hunting for tokens.
6. **Install and commit.** Run `uv tool install --editable ~/dev/NAME`, then
   `git add -A && git commit` in the generated repo. Do not push or publish it.
7. **Report** the command, its variables (`<ENV>_TOKEN`, `<ENV>_BASE_URL`,
   `<ENV>_READ_ONLY`, and `<ENV>_WS_URL` for websockets), and three example
   commands drawn from the user's own tasks.

## Updating

- The API changed: `uv run <this-skill-dir>/scripts/build.py --rebuild ~/dev/NAME`
  (the build inputs are recorded in `.api-cli.json`), then step 5.
- The runtime should behave differently: edit this skill's `assets/cli.py.tmpl`,
  never a generated copy, then rebuild the affected projects and repeat
  step 5. Read `references/design.md` first: its defaults are trial-tested,
  and several plausible "improvements" measured worse.

## What the generated CLI does

Keep these behaviors when changing the runtime; each is backed by a trial
finding in `references/design.md`.

- `NAME` prints an overview under 1 KB: search hint, flags, auth state, the
  current UTC time, and groups. `NAME search <words>` ranks commands and
  shows six with their required flags. `NAME <group>` lists a group (names
  only above 40 commands). `<command> --help` shows flags, the body,
  `Returns:` fields, and a runnable example using `--fields`.
- Output is JSON, compact when piped, with nulls and empties dropped.
  `--fields a,b.c` projects nested fields through lists. Responses over
  12 KB are cut to valid JSON; the full copy goes to a temp file and stderr
  lists the available field paths. `--raw` prints the untouched response;
  `--output FILE` saves the raw bytes (downloads, binary bodies).
- Bare values fill path parameters in order (`NAME orders get 51f1a3ed`).
  Unknown commands and flags get "did you mean" suggestions and an example.
  Usage errors exit 2 and API errors exit 1, with the status, body, and a hint.
- `--dry-run` shows any request without sending it. DELETE needs `--yes`,
  and `<ENV>_READ_ONLY=1` refuses every method except GET and websocket
  listening. `--paginate` follows `Link` headers or a `next` URL in the
  body, up to 20 pages.
- `NAME ws <channel>` connects, sends each `--send` message, and prints
  matching (`--match path=value`) messages as JSON lines, stopping at
  `--count` or `--timeout`.

## Gotchas

- **Deliberate house-standard exceptions.** The runtime reads its optional
  variables with `os.environ`, because pydantic-settings adds about 120 ms of
  import time to every call. `check-added-large-files` skips the generated
  `commands.json` (the GitHub catalogue is 1.4 MB). `websockets` is always a
  dependency, because ty checks the runtime's websocket code even in
  REST-only projects.
- **AsyncAPI perspective.** Public AsyncAPI 3 documents describe the server,
  so its `receive` operations are what a client sends. For a document
  written from the client's side, pass `--asyncapi-client-view`; otherwise
  help shows Send and Receives swapped.
- **An API group named `search`** (GitHub has one). `NAME search <action>`
  runs the API operation when `<action>` exists in that group; any other
  words are a discovery search.
- **OpenAPI has no websocket convention.** Endpoints with a `101` response
  are not treated as websockets. For a websocket API without AsyncAPI, write
  a minimal AsyncAPI 3 document only if the user asks.
- **External `$ref`s** stop the build. Bundle the spec first:
  `npx @redocly/cli bundle SPEC -o bundled.json`.

## Example

Request: "Make a CLI for our Gitea so agents can triage issues."

```bash
# gitea-api, not gitea: the server's own binary is called gitea
uv run <this-skill-dir>/scripts/build.py http://git.lan:3000/swagger.v1.json \
  --name gitea-api --auth 'header:Authorization:token {token}'
# 482 commands in 9 groups -> ~/dev/gitea-api
# (the spec's relative base path /api/v1 resolves against the spec URL)
cd ~/dev/gitea-api && uv sync && git init -q && git add -A && uv run pytest -q
uv run pre-commit run --all-files
uv run gitea-api search "close an issue"
#   gitea-api issue edit  --owner --repo --index  # Edit an issue.
GITEA_API_TOKEN=… uv run gitea-api issue list acme api-server --state open --fields number,title
uv tool install --editable ~/dev/gitea-api && git add -A && git commit -qm "Generate gitea-api from swagger.v1.json"
```

Reply: "`gitea-api` is installed (482 commands). Set `GITEA_API_TOKEN`; try
`gitea-api search "…"`, `gitea-api issue list OWNER REPO --fields number,title`,
and `gitea-api issue edit OWNER REPO 7 --state closed --dry-run`."

## Bundled resources

- `scripts/build.py`: **run** to generate or `--rebuild` a CLI project.
- `assets/cli.py.tmpl`: the runtime engine, copied verbatim into every
  project as `cli.py`. **Read** it before changing runtime behavior; edit it
  here, not in copies.
- `assets/template/`: project files `build.py` renders (pyproject with the
  house ruff and ty config, pre-commit, README, smoke tests). **Read** only
  when changing what a generated project contains.
- `references/design.md`: **read** before changing the runtime, or when
  agents struggle with a generated CLI. It holds the trial method, results,
  and the evidence behind each default.
