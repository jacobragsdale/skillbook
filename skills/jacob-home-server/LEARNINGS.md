# Learnings

Dated corrections from real use of this skill. Read before executing;
fold recurring/confirmed entries into SKILL.md and delete them here.

Format: `- YYYY-MM-DD: <what happened> → <what to do instead>`

(All entries through 2026-07-10 folded into SKILL.md or its references.)

- 2026-07-10: Jarvis bind data and mounted Codex state contained root-owned files, so a user `rm` only partially cleaned them → inspect ownership and use `sudo` on the exact app-owned paths during an explicitly approved full removal.
- 2026-07-10: `scripts/vm.sh status` and `off` expanded required Windows credentials without SOPS and failed before Compose ran → wrap every Windows Compose subcommand in the stack's SOPS environment, including read-only status and stop.
- 2026-07-10: In-guest restarts after enabling Hyper-V/WSL repeatedly hung at the UEFI boot-manager screen, while a graceful container stop/start recovered the preserved disk → allow for a full VM power cycle after Windows feature changes and verify SSH before continuing.
- 2026-07-10: Docker Desktop inside the Windows VM needed an interactive-session start, bounded `docker info` polling, and a console-context public base pull because the desktop credential helper failed over SSH → document this boundary before using the VM for container workflow rehearsals.
- 2026-07-11: Windows OpenSSH ignored the user's key after the test account had been an administrator because elevated accounts use `administrators_authorized_keys` → provision both authorized-key locations before demoting the disposable test identity.
- 2026-07-11: Windows SCP destinations written with backslashes were interpreted inconsistently by the remote shell → normalize guest SCP paths to forward slashes while keeping PowerShell paths native.
