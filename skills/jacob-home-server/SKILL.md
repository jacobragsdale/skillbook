---
name: jacob-home-server
description: "Operate Jacob's home server (desktop, 100.103.224.99): deploy or restart stacks, add/remove a service, edit SOPS secrets, check what's running vs declared, debug a container. Use when a request touches the home server, its docker stacks (media-stack, jellyfin, postgres, dozzle, personal site), its secrets, or server drift/cleanup."
disable-model-invocation: true
---

# Jacob's home server

Arch box `desktop` on Tailscale: `ssh 100.103.224.99` (user `jacob`, key
trusted, passwordless sudo). Everything it runs is declared in
`~/Development/home-server` **on the Mac** — that working tree is the source
of truth. `scripts/deploy.sh` rsyncs it to `~/home-server` on the server and
applies it. GitHub (`jacobragsdale/home-server`, private) is backup only:
the server never pulls from it, and there is no CI and no registry anywhere.

## Hard rules

- **Never edit compose files, scripts, or units on the server.** Edit the
  repo on the Mac and run `scripts/deploy.sh` — the rsync uses `--delete`,
  so server-side edits are silently lost on the next deploy.
- **Never write a plaintext secret** — no `.env` files, no values inlined in
  compose, no decrypted output in your response. Secrets live in per-stack
  `secrets.sops.env` (SOPS + age, safe to commit). Edit with
  `sops stacks/<name>/secrets.sops.env`; inspect keys only
  (`sops decrypt ... | cut -d= -f1`).
- **Removing or adding a service is a three-file change:** the stack dir,
  the container list in `host/scripts/healthcheck.sh`, and
  `docs/services.md`. A dead entry in the healthcheck makes the nightly
  maintenance service fail (this happened with lights-service: it failed
  every night for weeks before anyone noticed).
- **Data never goes under `~/home-server`** (the `--delete` rsync would own
  it). Bind-mount data from its own path; existing locations are in
  `docs/services.md`.
- Bind new UIs/ports to `100.103.224.99` (Tailscale-only) unless LAN
  exposure is the point.

## Workflow

1. Read the repo first: `README.md` for commands, `docs/services.md` for
   what runs where. Trust `scripts/drift.sh` output over any doc.
2. Make changes in the repo, then `scripts/deploy.sh <stack>` (or no args
   for everything). Verify with `docker ps` / the stack's healthcheck.
3. For host automation changes (`host/`): deploy, then run
   `bash ~/home-server/host/install.sh` on the server to reinstall units.
4. Commit and push when the change is verified — the push is the backup.

The personal site is separate: its own repo at
`~/Development/jacob-personal-site`, deployed with `make deploy` (rsync
working tree → native build on the server). Same rules, different repo.

## Example: add an Uptime Kuma stack

```sh
mkdir ~/Development/home-server/stacks/uptime-kuma
# compose.yaml: name: uptime-kuma; bind 100.103.224.99:3001:3001;
#   volume /home/jacob/uptime-kuma:/app/data (data outside the repo)
scripts/deploy.sh uptime-kuma
# then: add "uptime-kuma" to the container list in host/scripts/healthcheck.sh,
# a tcp_check line for 100.103.224.99:3001, and a row in docs/services.md
scripts/deploy.sh   # re-sync host scripts
git -C ~/Development/home-server add -A && git commit && git push
```

## Debugging

- Logs: `make logs` (personal site), Dozzle at `http://100.103.224.99:9999`,
  or `ssh 100.103.224.99 'docker logs --tail 100 <name>'`.
- Health history: `~/home-server/host/logs/{healthcheck,maintenance}.log`
  on the server; timers are `jacob-home-healthcheck` (hourly) and
  `jacob-home-maintenance` (daily 04:30, runs `pacman -Syu` + docker prune).
- Drift: `scripts/drift.sh` flags compose projects outside the repo,
  label-less containers, and dangling volumes. Deleting flagged *data*
  (volumes, directories) always needs Jacob's explicit go-ahead.

## Improving this skill

Before executing, read `LEARNINGS.md` in this skill's folder — entries there
override the instructions above. After use, if the user corrected you or the
outcome surprised you, append one dated line to `LEARNINGS.md`:
`- YYYY-MM-DD: <what happened> → <what to do instead>`. Do not edit SKILL.md
directly; lessons are folded in deliberately, not on the fly.
