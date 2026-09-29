# Copilot configuration and feature reference

Checked 2026-09-29 against Copilot CLI 1.0.89 (`copilot --help`, `copilot help
<topic>`, the binary's embedded settings schema) and VS Code `main` 47a634e
(v1.141-dev, `package.json` + source). The CLI is **not** open source (proprietary
license; github/copilot-cli holds only docs and issues). VS Code Copilot is open
source and now lives in `microsoft/vscode/extensions/copilot`. For anything newer,
run `copilot help config|environment|permissions|commands` and search `@tag:agent`
in VS Code settings.

## Contents

1. CLI permission switches
2. CLI files and precedence
3. CLI settings keys
4. CLI environment variables
5. CLI flags and subcommands
6. CLI slash commands
7. Customization (instructions, skills, agents, hooks, MCP, plugins, LSP)
8. CLI sandbox
9. VS Code approvals and permissions
10. VS Code settings by area
11. WSL scopes and gotchas
12. Policy that overrides the user

## 1. CLI permission switches

| Switch | Covers | Mode |
|---|---|---|
| `--allow-all` / `--yolo` | tools + paths + URLs | any |
| `--allow-all-tools` / `COPILOT_ALLOW_ALL` | tools only | any |
| `--allow-all-paths`, `--allow-all-urls` | paths / URLs | any |
| `defaultPermissionMode: "allow-all"` | everything | new interactive sessions only |
| `/allow-all on` (`/yolo`), `/permissions allow-all` | everything | current session |
| `COPILOT_ALLOW_ALL=true` (exact) | also trusts every folder: loads repo skills, plugins, MCP, hooks | any |

- Rule patterns for `--allow-tool` / `--deny-tool`: `shell(git:*)`, `shell(rm)`,
  `write(path)`, `<mcp-server>(tool)`, `url(https://*.github.com)`. Deny always
  beats allow, including `--yolo`.
- `--available-tools` / `--excluded-tools` hide tools from the model entirely.
- `--add-dir <dir>` (repeatable) grants a directory without allow-all-paths.
- `--secret-env-vars` strips and redacts named variables.
- Modes: `--mode interactive|plan|autopilot`, `--autopilot`,
  `--max-autopilot-continues` (default 5), `defaultMode`, `stayInAutopilot`.
- `assisted` permission mode: an LLM judge approves "safe" requests
  (experimental, `--assisted-approval`).
- Persistent per-folder approvals live in `~/.copilot/permissions-config.json`;
  `/reset-allowed-tools` clears them.

## 2. CLI files and precedence

Config dir `~/.copilot` (override with `COPILOT_HOME`; XDG is not read, only
migrated). Cache `~/.cache/copilot` (`COPILOT_CACHE_HOME`).

| File | Owner | Purpose |
|---|---|---|
| `settings.json` (JSONC) | you | user settings |
| `config.json` | CLI | auth, `trustedFolders`, plugins, state |
| `permissions-config.json` | CLI | remembered approvals, allowed dirs |
| `mcp-config.json` | you / `copilot mcp add` | MCP servers |
| `lsp-config.json` | you | language servers |
| `providers.json` | you | BYOK model providers |
| `copilot-instructions.md`, `instructions/` | you | personal instructions |
| `agents/`, `skills/`, `hooks/`, `extensions/` | you | customizations |
| `session-state/`, `session-store.db`, `logs/` | CLI | history, logs |

Precedence, low to high: defaults → managed settings → `~/.copilot/settings.json`
→ `.github/copilot/settings.json` → `.github/copilot/settings.local.json` → env →
flags. `.claude/settings{,.local}.json` contribute hooks and marketplaces.
`/settings --repo|--local` writes the repo files.

## 3. CLI settings keys

The schema has 182 keys; `copilot help config` documents the common ones.

- **Permissions and trust:** `defaultPermissionMode`, `allowedUrls`,
  `deniedUrls`, `askUser`, `trustedFolders` (in config.json), `sandbox.*`.
- **Model:** `model` (`auto` allowed), `planModel`, `effortLevel`
  (none…max), `contextTier`, `autoTier`, `continueOnAutoMode`.
- **Modes:** `defaultMode`, `stayInAutopilot`.
- **GitHub MCP:** `enableAllGithubMcpTools`, `githubMcpToolsets`,
  `githubMcpTools`, `githubMcpInsiders`, `disabledMcpServers`,
  `enabledMcpServers`.
- **Customization:** `skillDirectories`, `disabledSkills`,
  `ignoredSkillsLocations`, `hooks.<event>`, `disableAllHooks`,
  `disabledHooks`, `customAgents.defaultLocalOnly`, `enabledPlugins`,
  `extraKnownMarketplaces`.
- **Memory and git:** `memory` (cross-session facts, default on),
  `includeCoAuthoredBy`, `worktreePathTemplate`, `worktreeBaseRef`.
- **UI:** `theme` (default|github|dim|high-contrast|colorblind), `banner`,
  `bannerStyle`, `screenReader`, `mouse`, `copyOnSelect`, `compactPaste`,
  `commandHistoryMaxSize`, `statusLine.*`, `footer.*` (incl. `showYolo`),
  `sidebar.*`, `tabs.*`, `companyAnnouncements`.
- **Notifications:** `beep`, `beepOnSchedule`, `notifications`,
  `terminalNotifications`, `keepAlive` (off|on|busy).
- **Shell and network:** `bashEnv`, `powershellFlags`, `shellShortcut`
  (lone `$` opens a shell), `proxyUrl`, `proxyKerberosServicePrincipal`.
- **Updates and misc:** `autoUpdate`, `autoUpdatesChannel`, `experimental`,
  `enabledFeatureFlags`, `logLevel`, `storeTokenPlaintext`, `ide.*`,
  `voice.*`, `workflows.*`, `subagents.*`, `telemetry.capture.*`.

## 4. CLI environment variables

- **Auth:** `COPILOT_GITHUB_TOKEN` > `GH_TOKEN` > `GITHUB_TOKEN`;
  `COPILOT_GH_HOST` / `GH_HOST` for GHE.
- **Behavior:** `COPILOT_ALLOW_ALL`, `COPILOT_MODEL`, `COPILOT_AUTO_TIER`,
  `COPILOT_AUTO_UPDATE`, `COPILOT_ASSISTED_APPROVAL`, `COPILOT_OFFLINE`.
- **Paths:** `COPILOT_HOME`, `COPILOT_CACHE_HOME`,
  `COPILOT_CUSTOM_INSTRUCTIONS_DIRS`, `COPILOT_SKILLS_DIRS`, `COPILOT_EDITOR`.
- **BYOK:** `COPILOT_PROVIDER_{BASE_URL,TYPE,API_KEY,API_KEY_COMMAND,BEARER_TOKEN,WIRE_API,MODEL_ID,HEADERS,…}`
  — point the CLI at OpenAI-compatible, Anthropic, Azure, or local models.
- **Proxy / display:** `HTTP(S)_PROXY`, `NO_PROXY`, `COPILOT_PROXY_KERBEROS_SPN`,
  `NO_COLOR`, `PLAIN_DIFF`, `COPILOT_MULTIPLEXER`, `COPILOT_DISABLE_TERMINAL_TITLE`.
- **Telemetry:** `COPILOT_OTEL_*`, `OTEL_*` (OpenTelemetry export).
- **`-p` in untrusted folders:** `GITHUB_COPILOT_PROMPT_MODE_WORKSPACE_MCP`,
  `…_REPO_HOOKS`, `…_EXTENSIONS` (`=true`).

## 5. CLI flags and subcommands

- **Session:** `-p/--prompt`, `-i`, `-s/--silent`, `-r/--resume [id|name]`,
  `--continue`, `-n/--name`, `--session-id`, `-C <dir>`, `--agent`,
  `--model`, `--reasoning-effort`, `--context default|long_context`,
  `--fleet` (parallel subagents), `--enable-memory`, `--no-ask-user`.
- **Output:** `--output-format text|json` (JSONL events), `--stream on|off`,
  `--share [path]`, `--share-gist`, `--usage-output-file`,
  `--max-ai-credits`, `--attachment`, `--plain-diff`.
- **MCP:** `--additional-mcp-config <json|@file>`, `--disable-mcp-server`,
  `--disable-builtin-mcps`, `--enable-all-github-mcp-tools`,
  `--add-github-mcp-toolset`, `--add-github-mcp-tool`.
- **Other:** `--acp` (Agent Client Protocol server for editors),
  `--remote`, `--experimental`, `--no-custom-instructions`,
  `--no-auto-update`, `--log-level`, `--log-dir`, `--banner`,
  `--screen-reader`. Hidden: `--worktree [name]`, `--sandbox`,
  `--server`/`--headless`, `--auth-token-env <var>`.
- **Subcommands:** `login`, `update [stable|prerelease]`, `version`, `init`,
  `mcp {list,get,add,remove,enable,disable}`,
  `skill {list,add,remove,enable,disable}`, `plugin …`, `instruction list`,
  `lsp list`, `workflow run`, `sessions import`, `memories import`,
  `completion {bash,zsh,fish}`, `app`.

## 6. CLI slash commands

- **Permissions:** `/allow-all` (`/yolo`), `/permissions`, `/add-dir`,
  `/list-dirs`, `/cwd` (`/cd`), `/reset-allowed-tools`.
- **Agents:** `/model`, `/agent`, `/subagents`, `/delegate` (hand off to
  the cloud coding agent → PR), `/fleet`, `/autopilot` (`/goal`), `/plan`,
  `/tasks`, `/research`, `/rubber-duck`, `/ask` (`/btw`, side question).
- **Code:** `/diff`, `/review`, `/security-review`, `/pr`, `/ide`, `/lsp`,
  `/terminal-setup`, `/computer`.
- **Session:** `/resume`, `/rename`, `/fork`, `/worktree`, `/rewind`,
  `/compact`, `/context`, `/usage`, `/limits`, `/share` (`/export`),
  `/copy`, `/session`, `/remote`, `/clear`, `/new`, `/every` (`/loop`),
  `/after`, `/keep-alive`.
- **Environment:** `/init`, `/skills`, `/mcp`, `/plugin`, `/instructions`,
  `/memory`, `/env`, `/settings`, `/theme`, `/statusline`, `/footer`,
  `/vim`, `/voice`, `/experimental`, `/update`, `/diagnose`, `/login`,
  `/logout`, `/help`, `/exit`.

## 7. Customization

| Kind | Repo | Personal |
|---|---|---|
| Instructions | `.github/copilot-instructions.md`, `.github/instructions/**/*.instructions.md` (`applyTo`), `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.claude/rules` | `~/.copilot/copilot-instructions.md`, `~/.copilot/instructions/` |
| Skills (`SKILL.md`) | `.github/skills`, `.agents/skills`, `.claude/skills` | `~/.copilot/skills`, `~/.agents/skills` (not with `COPILOT_HOME`; `~/.claude/skills` not read) |
| Custom agents (`*.agent.md`) | `.github/agents`, `.claude/agents` | `~/.copilot/agents` |
| Hooks (JSON) | `.github/hooks/*.json` | `~/.copilot/hooks/`, `hooks` in settings |
| MCP | `.mcp.json`, `.github/mcp.json`, `.vscode/mcp.json` | `~/.copilot/mcp-config.json` |
| LSP | `.github/lsp.json` | `~/.copilot/lsp-config.json` |

- Repo MCP servers, hooks, and plugins load only in trusted folders.
- Hook events: `sessionStart`, `sessionEnd`, `userPromptSubmitted`,
  `preToolUse`, `postToolUse`, `postToolUseFailure`, `permissionRequest`,
  `preMcpToolCall`, `preCompact`, `subagentStart`, `subagentStop`,
  `agentStop`, `errorOccurred`, `notification`. `preToolUse` can return
  `permissionDecision` and `modifiedArgs`.
- MCP entry: `{"type":"local|stdio|http|sse","command","args","env","url","headers","tools":["*"],"timeout"}`.
- Plugins bundle agents, skills, hooks, and MCP; default marketplaces are
  `copilot-plugins` and `awesome-copilot`. Install with
  `copilot plugin install name@marketplace` or `OWNER/REPO`.
- Built-in agents: explore, task, research, code-review, security-review,
  rubber-duck.

## 8. CLI sandbox

Off by default (`sandbox.enabled`). Linux/WSL2 needs `bwrap` ≥ 0.5,
`slirp4netns`, `/dev/net/tun`. Keys: `sandbox.userPolicy.filesystem.{readwritePaths,readonlyPaths,deniedPaths}`,
`sandbox.userPolicy.network.{allowOutbound,allowLocalNetwork,allowedHosts,blockedHosts}`,
`sandbox.allowBypass`, `sandbox.sandboxMcpServers`, `sandbox.auth.{gh,git}`.
Allow-all still runs inside the sandbox when it is on.

## 9. VS Code approvals and permissions

- `chat.tools.global.autoApprove` — master YOLO switch (policy
  `ChatToolsAutoApprove`); one-time warning dialog.
- `chat.permissions.default` — `default` | `autoApprove` | `autopilot`.
- `chat.defaultConfiguration` — `{mode: interactive|plan|autopilot, approvals: manual|assisted|allowAll}`
  for Copilot-harness sessions.
- `chat.autoReply` — the agent answers its own questions (autonomy, not
  permission).
- `chat.tools.terminal.{enableAutoApprove,autoApprove,ignoreDefaultAutoApproveRules,blockDetectedFileWrites,autoApproveWorkspaceNpmScripts}`.
- `chat.tools.urls.autoApprove`, `chat.tools.edits.autoApprove`
  (application scope), `chat.tools.eligibleForAutoApproval`,
  `chat.editing.autoAcceptDelay`, `chat.agent.maxRequests`.
- `github.copilot.chat.additionalReadAccessPaths`.
- Chat slash commands: `/yolo`, `/disableYolo`, `/autopilot`,
  `/exitAutopilot`.
- Sandbox: `chat.agent.sandbox.{enabled,allowNetwork,allowUnsandboxedCommands,allowAutoApprove,fileSystem.linux}`
  (WSL2 needs `bubblewrap socat`), network filter
  `chat.agent.{networkFilter,allowedNetworkDomains,deniedNetworkDomains}`.
- Dead IDs: `chat.tools.autoApprove`,
  `chat.tools.terminal.autoReplyToPrompts`,
  `chat.agent.terminal.allowList/denyList`.
- Claude and Codex harnesses inside VS Code use their own permission
  modes, not these settings.

## 10. VS Code settings by area

- **Harnesses:** Local (deprecated), Copilot (the CLI engine in the Agent
  Host), Claude, Codex, Cloud. `chat.defaultToCopilotHarness`,
  `chat.agentHost.{claudeAgent,codexAgent}.enabled`,
  `github.copilot.chat.cli.*`, `github.copilot.chat.cloudAgent.enabled`.
- **Models:** `chat.defaultModel`, `chat.planAgent.defaultModel`,
  `chat.exploreAgent.defaultModel`, `chat.utilityModel`,
  `github.copilot.chat.reasoningEffortOverride`, BYOK custom endpoints.
- **Agent:** `chat.checkpoints.enabled`, `chat.requestQueuing.defaultAction`
  (steer|queue), `chat.subagents.*`, `chat.customAgentInSubagent.enabled`,
  `chat.tools.todos.showWidget`, `github.copilot.chat.agent.autoFix`.
- **Terminal tool:** `chat.tools.terminal.terminalProfile.linux`,
  `shellIntegrationTimeout`, `outputLocation`, `preventShellHistory`,
  `chat.agentHost.shellTool.initScript.enabled` (source `~/.bashrc`).
- **MCP:** `chat.mcp.{access,autostart,discovery.enabled,gallery.enabled,serverSampling,apps.enabled}`;
  files `.vscode/mcp.json` (`servers`, `inputs`) and the portable
  `.mcp.json` / `~/.copilot/mcp-config.json`.
- **Customization:** `chat.useAgentsMdFile`, `chat.useNestedAgentsMdFiles`,
  `chat.useClaudeMdFile`, `chat.useAgentSkills`, `chat.useHooks`,
  `chat.useClaudeHooks`, `chat.plugins.*`, prompt files in
  `.github/prompts`, custom agents with handoffs.
- **Completions:** `github.copilot.enable` (per language),
  `github.copilot.nextEditSuggestions.{enabled,eagerness,fixes}`,
  `github.copilot.selectedCompletionModel`.
- **Other:** code review (`github.copilot.chat.reviewAgent.enabled`),
  `git.addAICoAuthor`, browser tools
  (`workbench.browser.enableChatTools`), voice and dictation, OTel
  (`github.copilot.chat.otel.*`), Agents window, automations, worktree and
  Dev Container sessions.

## 11. WSL scopes and gotchas

- Settings files: Windows user `%APPDATA%\Code\User\settings.json` →
  WSL remote `~/.vscode-server/data/Machine/settings.json` → workspace
  `.vscode/settings.json`; later wins.
- Application-scoped keys (`chat.tools.edits.autoApprove`, network filter,
  `chat.plugins.*`) work only in the Windows user file.
  `chat.tools.global.autoApprove` and `chat.autoReply` work in the Windows
  user file or the remote file, never workspace.
- Copilot's extension host and agent terminal run in WSL; `~` in
  customization paths means the WSL home.
- Policy is read on the Windows side only.
- The VS Code server does not source shell rc files; set env for it in
  `~/.vscode-server/server-env-setup`.
- CLI in WSL: clipboard via `clip.exe` (OSC 52 fallback); token storage
  needs libsecret + gnome-keyring, else plaintext prompt; use
  `copilot login --device-code` when no browser opens.
- Repos under `/mnt/c` are slow (9P); keep work in the Linux filesystem.

## 12. Policy that overrides the user

- Managed settings, precedence MDM > server > file:
  - Registry: `HKLM\SOFTWARE\Policies\GitHubCopilot`.
  - Server: an org `.github-private` repo, `copilot/managed-settings.json`.
  - Files: `%ProgramFiles%\GitHubCopilot\managed-settings.json`,
    `/etc/github-copilot/managed-settings.json`.
- Keys that block full access:
  - `permissions.disableBypassPermissionsMode: "disable"`
  - `permissions.{deny,ask}`
  - `sandbox.allowBypass: false`
  - `allowManagedMcpServersOnly`
  - `allowManagedHooksOnly`
- VS Code device policies (`HKLM\SOFTWARE\Policies\Microsoft\VSCode`):
  - `ChatToolsAutoApprove`
  - `ChatToolsEligibleForAutoApproval`
  - `ChatToolsTerminalEnableAutoApprove`
  - `ChatAgentSandbox*`
  - `ChatMCP`
  - `ChatAgentMode`
- Org policies: the Copilot CLI and MCP policies and model availability.
- Check what is in effect with **Developer: Policy Diagnostics**.
