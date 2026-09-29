# Design evidence for the generated CLI

Why the runtime (`assets/cli.py.tmpl`) behaves the way it does, measured on
2026-09-28 with no-context agents. Re-run the trials before overturning a
default.

## Contents

- Trial method
- Results
- Defaults and the evidence for each
- Rejected ideas
- Sources

## Trial method

- **Agents.** Fresh general-purpose subagents on Sonnet 5.5 and Haiku 4.5.
  Each prompt said only: "You have a command-line tool for <service> at
  <path>. It is already configured. Task: <task>. Use only that tool; don't
  read its files." No skill, no hints about the CLI's design.
- **Targets.**
  - A throwaway Gitea 1.27 container (482 operations, Swagger 2.0) seeded
    with an org, repos, 16 issues, labels, milestones, a PR and a release,
    and reset between write tasks.
  - GitHub (1,231 operations; public repos only).
  - weather.gov (69 operations; no tags or summaries).
  - A demo exchange (FastAPI REST plus WebSocket feeds, with an AsyncAPI 3
    document).
- **Measurement.**
  - Each CLI ran behind a shim that logged every call's argv, exit code, and
    stdout/stderr size.
  - The subagent's final token count, tool calls, and wall time came from
    the task report.
  - Answers were checked against the API.
- **Arms.**
  - "Naive": a conventional generated CLI. `--help` lists every operation;
    output is pretty, untrimmed JSON; there is no search.
  - "Agent-first": this design.
  - Ablation: agent-first without search.
- **Known noise.** One run per cell, and the harness's own output limits (for
  example, Claude Code saves bash output over 30 KB to a file) blunt the
  naive arm's worst cases. Differences in *variable* cost are larger than
  the totals show, because every run starts near 30k tokens.

## Results

Round 1 (Sonnet, 8 tasks, naive vs agent-first, all 16 answers correct):

| Task | Naive tokens / calls / s | Agent-first tokens / calls / s |
| --- | --- | --- |
| Gitea: unassigned open bugs | 40.9k / 9 / 38 | 38.1k / 5 / 19 |
| Gitea: close wontfix issues with a comment | 43.1k / 10 / 34 | 40.0k / 15 / 32 |
| Gitea: collaborator + release | 37.3k / 9 / 19 | 39.4k / 9 / 34 |
| GitHub: 3 latest bug issues | 37.8k / 7 / 24 | 37.0k / 8 / 27 |
| GitHub: top 5 contributors | 69.8k / 17 / 235 | 33.3k / 5 / 12 |
| GitHub: PRs merged in 7 days | 43.7k / 9 / 68 | 40.7k / 12 / 54 |
| NWS: tonight's forecast | 40.3k / 4 / 8 | 37.6k / 6 / 13 |
| NWS: Florida alerts | 63.8k / 6 / 47 | 35.7k / 7 / 20 |
| **Total** | **376.7k / 71 / 473** | **301.8k / 67 / 211** |

- The naive "top contributors" run made 93 CLI calls and received a 16.8 MB
  response. The naive "PRs merged" run pulled about 17 MB of pull-request
  JSON; the agent-first run got about 7 KB per page because it used
  `--fields`.
- Round 2:
  - Search ablation (Sonnet, 4 tasks): 165.0k tokens without search against
    151.0k with it, all correct. Sonnet finds commands either way on
    familiar APIs.
  - Websocket tasks: both correct. The Sonnet agent started the order-events
    listener in the background before placing the order.
  - Haiku found two defects. A text-prefix output cut produced invalid JSON
    that `--raw` didn't bypass, which cost 17 calls. And 3 of 12
    transcripts, one of them Sonnet's, tried positional path values first.
- Round 3 (Haiku, after the fixes):
  - Six of seven tasks were right the first time.
  - The Florida-alerts task fell from 37.3k tokens and 17 calls to 31.0k/4
    and 26.9k/4.
  - The miss: Haiku opened the order feed after the order had filled. The
    websocket help now says streams are live-only.
- Skill trial (Sonnet following SKILL.md against Gitea): it built and
  verified the CLI and found three defects, all since fixed:
  - With `query:` auth, `--dry-run` printed the token. Every printed URL,
    header, query and error message is now redacted.
  - SKILL.md staged files before `uv sync` created `uv.lock`.
  - Nothing warned that Gitea's `Authorization` key needs a `token ` prefix.
    The build now quotes the scheme's description, and a refused token gets
    its own hint.

## Defaults and the evidence for each

1. **Search is the front door, and browsing stays cheap.** Cloudflare's
   `cf` makes search the entry point, and Haiku reached for search first.
   Sonnet did as well without it. Groups over 40 commands print names only;
   GitHub `repos` went from a 19.8 KB listing to 5 KB.
2. **Ranking.** BM25F over name ×3, summary ×2, path, description, and
   params, multiplied by squared term coverage, with prefix matching, a light
   stemmer, and verb synonyms (close→update/edit, watch→stream). On 40
   labeled queries it put the right command first 26 times and in the top 5
   38 times. Idf-weighted coverage measured worse and was reverted. The
   remaining misses need domain synonyms (for example, "delete a branch" is
   `git delete-ref`).
3. **Every command's help shows `Returns:` and an example with `--fields`.**
   Agent-first runs used `--fields` on their first data call in almost every
   transcript. This is the biggest token saving.
4. **Compact JSON when piped, nulls and empties dropped.** Minified JSON is
   10–36% smaller than indented (TOON benchmark and a research count with
   OpenAI's tokenizer). Field selection matters more than format: in the same
   count, 50 GitHub issues were 123k tokens with every field and 2.6k with six.
5. **The output guard cuts structurally.** At 12 KB it keeps a prefix of the
   largest list, prints valid JSON, lists nested field paths, saves the full
   response to a temp file, and `--raw` bypasses it.
6. **Bare values fill path parameters** (see round 2).
7. **Errors carry the next step.** Unknown names get "did you mean";
   missing flags show an example; HTTP errors include the body and a hint
   (the token variable for 401/403, the path flags for 404).
8. **Safety.** Agents ran `--dry-run` unprompted before writes. DELETE needs
   `--yes` (cf does the same when there is no terminal). `<ENV>_READ_ONLY`
   gives a safe exploration mode. Credentials never reach output: dry-runs,
   error messages and websocket URLs mask the token, raw or URL-encoded.
9. **A built-in name must not shadow an API group.** A GitHub agent couldn't
   reach `search issues-and-pull-requests` until `search <api action>` was
   routed to the API.
10. **Websockets are bounded and line-oriented.** `--count` and `--timeout`
    (Claude Code's shell timeout is 2 minutes), `--match` to filter, one
    JSON message per line, and a note that streams are live.
11. **Fast start.** On GitHub's 1,231 operations, discovery commands take
    about 41 ms and search about 87 ms. `httpx` and `websockets` are
    imported only when a call is made, and pydantic is kept out of the
    runtime.

## Rejected ideas

- **Comma lists on path flags that repeat the call.** No agent used it in
  the trials, so it was removed.
- **A help screen listing every operation** (the naive arm): 113 KB for
  GitHub.
- **A SKILL.md generated for each CLI.** The user declined it; the overview
  is the discovery surface.
- **pydantic-settings in the runtime:** about 120 ms on every call, for
  optional variables only.
- **TSV or TOON output.** It is smaller than JSON only when fields are
  selected, and benchmarks show accuracy risks.
- **Behaviour that changes when an agent is detected.** Vercel's agent mode
  has bugs of this kind. Use hints, not modes.

## Sources

- Cloudflare `cf` launch and the `cf` source (search with MiniSearch BM25+,
  an agent banner on help, `--force` without a terminal):
  https://blog.cloudflare.com/cloudflare-cf-cli-launch/,
  https://blog.cloudflare.com/cf-cli-local-explorer
- Anthropic, writing tools for agents (concise responses, truncation
  defaults, actionable errors):
  https://www.anthropic.com/engineering/writing-tools-for-agents
- Justin Poehnelt, rewriting CLIs for agents (input hardening):
  https://justin.poehnelt.com/posts/rewrite-your-cli-for-ai-agents/
- AsyncAPI 3 migration and websocket bindings:
  https://www.asyncapi.com/docs/migration/migrating-to-v3
- restish, Speakeasy, Stainless, and mcp2cli issue trackers (name clashes,
  path-level params, `anyOf` nulls, exit codes).
