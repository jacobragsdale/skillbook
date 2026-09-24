---
name: jacob-home-server
description: "Operates Jacob's home server: Docker stacks, SOPS secrets, deploys, backups. Use whenever a task touches the home server or its repo — status or drift checks, debugging its services or networking, changing stacks or secrets, host config, media, router/DNS, Tailscale, Windows VM, restores, rebuilds — even if the user doesn't name the server. Do not SSH to it or edit the home-server repo without this skill. Not for Docker questions unrelated to Jacob's server."
---

# Jacob's home server

Operate `desktop` (Tailscale `100.103.224.99`) as user `jacob`, normally from
its own checkout at `~/dev/home-server`; the Mac clone is the recovery control
plane. Treat the git checkout as the source of truth and `~/home-server` on
the server as its rsync target; `./scripts/deploy.sh` syncs it there from either
machine. The server never pulls from GitHub; a verified commit and push are
the configuration backup.

## Start every task

1. Work from the git checkout. Check the worktree with `git status --short`
   before editing and preserve unrelated changes.
2. Read `README.md`, `docs/services.md`, and the files that own the requested
   behavior. Read `docs/state-and-backups.md` for persistence or recovery
   changes. Do not trust a service list copied into this skill: this repo
   changes quickly.
3. For current state, run `./scripts/drift.sh`. For host health, run
   `bash ~/home-server/host/scripts/status.sh --summary` (through
   `ssh 100.103.224.99` when working from the Mac).
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
  on the server. Edit the checkout and apply it with the repo scripts; deploy
  uses `rsync --delete`, so remote edits disappear.
- Every deploy syncs the entire clean, committed checkout. A stack argument
  limits which Compose projects are applied, not which files rsync copies, and
  `deploy.sh` refuses staged, unstaged, or untracked changes. Review, commit,
  and push the complete intended artifact before deploying it unless Jacob
  explicitly asked to stop before publication; in that case, do not deploy.
- Never create a plaintext `.env`, inline a secret, write decrypted data to
  disk, or include a decrypted value in output. Edit `*.sops.env` with `sops`;
  inspect key names only.
- Never put application data under `~/home-server`. Bind it from a separate
  server path declared in `host/data-layout.tsv`; explain its recovery class in
  `docs/state-and-backups.md` and service ownership in `docs/services.md`.
- Never delete a volume, bind-mount directory, backup snapshot, media, VM disk,
  or drift-reported data without Jacob's explicit approval for that deletion.
  Removing configuration does not imply deleting its data.
- Bind new admin UIs to `100.103.224.99` by default. LAN exposure is a
  deliberate design choice. Public ingress is retired; reintroduce it only on
  explicit request with the matching network, DNS, and authentication work.
- Use `REHEARSAL=1` for every practice rebuild command. Without it, a rehearsal
  can join production systems, repoint DNS, arm notification timers, and prune
  the real backup repository.
- Prefer the repository's Bash entry points. The SSH login shell is zsh; for
  nontrivial ad-hoc remote logic, invoke Bash explicitly. If pacman was killed,
  confirm no pacman process exists before removing `/var/lib/pacman/db.lck`.

## Apply changes

1. Establish the failure or desired state with the narrowest read-only check.
2. Edit every owning artifact, including service inventory, data-layout and
   recovery policy, ingress, health probes, credentials, and router/DNS
   declarations when they are actually affected.
3. Run `./scripts/check.sh`. For a stack with secrets, also render Compose from
   its directory with
   `sops exec-env secrets.sops.env 'docker compose config --quiet'` when a
   focused model check helps diagnose the change.
4. Review the diff for secrets and accidental scope, then commit and push the
   home-server repo. If Jacob asked to stop before publication, stop here and
   do not deploy. Deployment accepts only a clean committed artifact; if live
   verification exposes a problem, fix it in a new commit and repeat.
5. Deploy the narrowest valid scope with `./scripts/deploy.sh <stack>`. Use a
   full no-argument deploy for multi-stack/global behavior or **any `host/`
   change**, including `host/data-layout.tsv`; the full deploy runs
   `host/install.sh` automatically. Do not run it again afterward.
   `host/install.sh --activate` is only the post-restore cold-host transition
   described in the recovery runbook, never a normal update step.
6. Verify the changed container/unit, its logs, and the user-visible endpoint.
   Run `./scripts/verify.sh` and `./scripts/drift.sh` for host, shared
   infrastructure, persistence, or multi-stack changes. A successful deploy
   command is not sufficient proof by itself.

## Completion report

Report the observed cause or requested outcome, files changed, live actions,
verification evidence, and any manual/cloud steps still required. Never print
secret values. If no live action was authorized, say explicitly that the repo
or server was not changed.
