---
name: jacob-home-server
description: "Operates Jacob's declarative home server safely. Use when checking status/drift, debugging Docker/networking, changing stacks/services or SOPS secrets, deploying host config, handling backups, media, router/Tailscale, Windows VM, or rebuilds."
---

# Jacob's home server

Operate `desktop` at `100.103.224.99` over Tailscale as user `jacob`. Treat
`~/Development/home-server` on the Mac as the source of truth and
`~/home-server` on the server as an rsync target. The server never pulls from
GitHub; a verified commit and push are the configuration backup.

## Start every task

1. Read `LEARNINGS.md`, then work from the Mac repository. Check the worktree
   with `git status --short` before editing and preserve unrelated changes.
2. Read `README.md`, `docs/services.md`, and the files that own the requested
   behavior. Do not trust a service list copied into this skill: this repo
   changes quickly.
3. For current state, run `scripts/drift.sh`. For host health, run
   `ssh 100.103.224.99 'bash ~/home-server/host/scripts/status.sh --summary'`.
   Docs describe intent; scripts and live inspection establish reality.
4. Classify every target as repo-owned configuration, app-owned runtime data,
   or external/cloud state before changing it. State the boundary when it
   affects the solution.
5. Match the action to the request. A diagnosis authorizes inspection and an
   explanation, not an unrequested restart, deploy, cleanup, or fix.

Read [references/operations.md](references/operations.md) in full before a
normal diagnosis or change. Read [references/recovery-and-vm.md](references/recovery-and-vm.md)
in full before backup restoration, rebuild work, a rehearsal, or any Windows
VM operation.

## Safety boundaries

- Never edit compose files, scripts, units, dotfiles, or declared host config
  on the server. Edit the Mac repo and apply it with the repo scripts; deploy
  uses `rsync --delete`, so remote edits disappear.
- Every deploy syncs the entire Mac working tree. A stack argument limits which
  Compose projects are applied, not which files rsync copies. Do not deploy an
  unrelated, unready dirty change along with the requested work.
- Never create a plaintext `.env`, inline a secret, write decrypted data to
  disk, or include a decrypted value in output. Edit `*.sops.env` with `sops`;
  inspect key names only. Treat `host/codex/auth.sops.json` as the documented
  special case and use `scripts/codex-auth.sh`.
- Never put application data under `~/home-server`. Bind it from a separate
  server path recorded in `docs/services.md`.
- Never delete a volume, bind-mount directory, backup snapshot, media, VM disk,
  or drift-reported data without Jacob's explicit approval for that deletion.
  Removing configuration does not imply deleting its data.
- Bind new admin UIs to `100.103.224.99` by default. LAN or public exposure is
  a deliberate design choice that requires the matching network and auth work.
- Use `REHEARSAL=1` for every practice rebuild command. Without it, a rehearsal
  can join production systems, repoint DNS, arm notification timers, and prune
  the real backup repository.
- Prefer the repository's Bash entry points. The SSH login shell is zsh; for
  nontrivial ad-hoc remote logic, invoke Bash explicitly. If pacman was killed,
  confirm no pacman process exists before removing `/var/lib/pacman/db.lck`.

## Apply changes

1. Establish the failure or desired state with the narrowest read-only check.
2. Edit every owning artifact, including service inventory, backup coverage,
   ingress, health probes, credentials, and router/DNS declarations when they
   are actually affected.
3. Validate locally where possible. For a stack with secrets, run from its
   directory:
   `sops exec-env secrets.sops.env 'docker compose config --quiet'`.
4. Deploy the narrowest scope: `scripts/deploy.sh <stack>`. Use a full deploy
   only when multiple stacks or global behavior require it; remember that both
   forms sync the whole tree. For `host/` changes, deploy first, then run
   `ssh 100.103.224.99 'bash ~/home-server/host/install.sh'`.
5. Verify the changed container/unit, its logs, and the user-visible endpoint.
   Run the broader healthcheck or drift check when the change can affect shared
   infrastructure. A successful command is not sufficient proof by itself.
6. Review the diff for secrets and accidental scope. When the requested change
   is verified, commit and push the home-server repo unless Jacob asked to stop
   before publication.

## Completion report

Report the observed cause or requested outcome, files changed, live actions,
verification evidence, and any manual/cloud steps still required. Never print
secret values. If no live action was authorized, say explicitly that the repo
or server was not changed.

## Improving this skill

Before executing, read `LEARNINGS.md` in this skill's folder — entries there
override the instructions above. After use, if the user corrected you or the
outcome surprised you, append one dated line to `LEARNINGS.md`:
`- YYYY-MM-DD: <what happened> → <what to do instead>`. Do not edit SKILL.md
directly; lessons are folded in deliberately, not on the fly.
