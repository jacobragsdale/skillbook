---
name: copilot-wsl
description: "Set up GitHub Copilot CLI and VS Code Copilot on WSL with full access. Use when the user wants Copilot installed, configured, or unrestricted (yolo, allow-all, no prompts) in WSL \u2014 even if they only say Copilot."
---

# Copilot on WSL, full access

Install and configure GitHub Copilot CLI (inside WSL) and Copilot in VS Code
(Windows UI, WSL remote) so neither asks before running commands, editing
files, touching paths outside the repo, or fetching URLs. The user chose
this; do not argue it down, but make them confirm the one step that outlives
Copilot (passwordless sudo). Verified against Copilot CLI 1.0.89 and VS Code
1.141-dev (2026-09-29); IDs drift, so trust `copilot help config` and the
Settings UI over this file when they disagree.

## Workflow

1. **Preflight.** Confirm WSL2 and find the Windows side:

   ```bash
   grep -qi microsoft /proc/version && echo "WSL $WSL_DISTRO_NAME"
   WINAPPDATA=$(wslpath "$(cmd.exe /c 'echo %APPDATA%' 2>/dev/null | tr -d '\r')")
   ls "$WINAPPDATA/Code/User/settings.json"   # "Code - Insiders" for Insiders
   ```

   If `cmd.exe` is not found, Windows interop is off: `/etc/wsl.conf` has
   `[interop] enabled=false` or `appendWindowsPath=false`. Tell the user;
   fixing it needs `wsl --shutdown` from Windows.
2. **Check for policy that overrides everything below.** Any hit means
   some settings will be ignored; report which, do not try to defeat it:

   ```bash
   cat /etc/github-copilot/managed-settings.json "/mnt/c/Program Files/GitHubCopilot/managed-settings.json" 2>/dev/null
   reg.exe query 'HKLM\SOFTWARE\Policies\GitHubCopilot' /s 2>/dev/null
   reg.exe query 'HKLM\SOFTWARE\Policies\Microsoft\VSCode' /s 2>/dev/null
   ```

   `permissions.disableBypassPermissionsMode` blocks every allow-all switch
   in both tools; VS Code policy `ChatToolsAutoApprove=0` removes YOLO.
3. **Install the CLI in WSL** (skip if `copilot version` works). Default to
   the native installer — no Node needed:

   ```bash
   curl -fsSL https://gh.io/copilot-install | bash   # -> ~/.local/bin/copilot
   ```

   Use `npm i -g @github/copilot` only if the user manages tools with npm.
   Never install the Windows build (`winget GitHub.Copilot`) for WSL work.
4. **Auth.** Login is interactive; ask the user to run `! copilot login`
   (device-code flow works without a WSL browser). Token storage needs
   libsecret + a keyring (`sudo apt install libsecret-1-0 gnome-keyring`);
   without it the CLI offers plaintext in `~/.copilot/config.json` — let
   the user pick. Classic `ghp_` PATs are rejected; a fine-grained PAT with
   "Copilot Requests" in `COPILOT_GITHUB_TOKEN` also works.
5. **CLI config.** Merge `assets/copilot-settings.json` into
   `~/.copilot/settings.json` (JSONC; create it if missing, keep the user's
   other keys). Then append this block to `~/.bashrc` and `~/.zshrc` if the
   files exist and the marker is absent:

   ```bash
   # >>> copilot-wsl >>>
   export COPILOT_ALLOW_ALL=true   # exactly "true": also trusts every folder
   alias copilot='copilot --yolo'  # -p runs ignore defaultPermissionMode
   # <<< copilot-wsl <<<
   ```

   Why both: `defaultPermissionMode` covers interactive sessions only;
   `COPILOT_ALLOW_ALL` covers tools in `-p` but not paths or URLs; `--yolo`
   is the only switch that covers all three in every mode. Scripts do not
   see aliases — tell the user to pass `--yolo` in scripts.
6. **VS Code config.** Back up, then merge `assets/vscode-settings.jsonc`
   into the **Windows** user file `$WINAPPDATA/Code/User/settings.json`:

   ```bash
   cp "$WINAPPDATA/Code/User/settings.json"{,.bak-$(date +%s)}
   ```

   Edit in place with the Edit tool so the user's comments survive; never
   round-trip it through a JSON parser. It must be the Windows file: several
   keys are application-scoped and ignored in the WSL remote file
   (`~/.vscode-server/data/Machine/settings.json`) and in workspace settings.
   After the next VS Code restart the user must accept the one-time
   "auto-approve all tools" warning, or `chat.tools.global.autoApprove`
   stays off.
7. **Passwordless sudo — ask first.** "Full machine" access inside WSL
   means root, and the agent cannot type a sudo password. Ask: *"Allow
   passwordless sudo for `<user>` in this distro? It applies to everything
   that runs as you, not just Copilot."* Only on yes:

   ```bash
   echo "$USER ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/90-copilot-wsl >/dev/null
   sudo chmod 440 /etc/sudoers.d/90-copilot-wsl && sudo visudo -cf /etc/sudoers.d/90-copilot-wsl
   ```

   If `visudo -c` fails, delete the file immediately — a broken sudoers
   file locks out sudo. Windows-side reach is the launching Windows user's
   rights (`/mnt/c`, `*.exe` via interop). Admin on Windows requires
   starting WSL from an elevated terminal; do not try to script UAC.
8. **Report** what changed (files, backup paths, rc block, sudo yes/no),
   any policy that blocks a setting, and the undo: delete the rc block and
   `/etc/sudoers.d/90-copilot-wsl`, restore the `.bak` file, remove the
   merged keys from `~/.copilot/settings.json`.

## Validation

Run each check; a failure sends you back to the step named.

- `copilot version` prints ≥ 1.0.89 (step 3).
- `zsh -ic 'echo $COPILOT_ALLOW_ALL; alias copilot'` shows `true` and
  `copilot --yolo` (step 5; use `bash -ic` for bash users).
- After login, one cheap live run proves paths, shell, and network:

  ```bash
  cd ~ && copilot --yolo -s -p 'Run `ls /mnt/c | head -3`, `id -un`, and `curl -sI https://github.com | head -1`; print the outputs only.'
  ```

  It must finish with no prompt and print a Windows directory listing.
- `sudo -n true` exits 0 if the user approved step 7.
- VS Code: in a WSL window, start an Agent chat, ask it to run
  `ls /mnt/c`; the permission picker must show **Bypass Approvals** and no
  confirmation appears. Run **Developer: Policy Diagnostics** if it does.

## Example

User: "set up copilot in my wsl, no permission prompts, it can do anything"

→ Preflight finds Ubuntu on WSL2 and `C:\Users\jacob\AppData\Roaming`; no
managed settings. Installs 1.0.89 to `~/.local/bin`, asks the user to run
`! copilot login`, writes `~/.copilot/settings.json` and the `~/.zshrc`
block, merges eleven keys into the Windows `settings.json` (backup
`settings.json.bak-1790000000`), asks about sudo (yes), and reports the
verification output plus the undo list.

## Bundled resources

- `assets/copilot-settings.json` — **read** and merge into
  `~/.copilot/settings.json`.
- `assets/vscode-settings.jsonc` — **read** and merge into the Windows
  VS Code user settings.
- `references/options.md` — **read** when the user asks what else Copilot
  can do or be configured to do: every CLI flag, env var, settings key,
  slash command, customization path, and VS Code setting group.
