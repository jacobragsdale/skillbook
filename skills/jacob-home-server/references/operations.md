# Routine operations

Read this file before diagnosing or changing the home server. Keep volatile
service facts in the home-server repo rather than copying them here.

## Contents

- Diagnose from intent to symptom
- Change an existing stack
- Add a stack or service
- Remove a stack or service
- Change host state
- Change secrets or credentials
- App-owned and external state
- Service-specific guardrails

## Diagnose from intent to symptom

1. Read the relevant compose/config, `docs/services.md`, and recent git diff or
   history. Run `scripts/drift.sh` to separate undeployed intent from runtime
   failure.
2. Inspect `host/scripts/status.sh --summary`, `docker ps`, the affected
   container's last 100–200 log lines, health status, and the exact endpoint.
3. Follow dependencies outward only as evidence requires: app → shared Docker
   network/VPN → Caddy → LAN/router/DNS → Tailscale.
4. Check `host/logs/{healthcheck,maintenance,backup}.log` and the corresponding
   systemd unit when the issue may be scheduled or host-wide.
5. Explain the cause before proposing a change. Do not restart first and erase
   the evidence unless availability requires it and the user authorized a fix.

## Change an existing stack

- Read its complete compose file, SOPS key names, mounts, networks, and the
  matching `docs/services.md` row. Search for cross-stack references before
  renaming a service, container, port, secret, hostname, or path.
- Preserve the repository's reproducibility contract: external images use a
  readable tag plus an immutable digest, and Caddy bases/modules are pinned.
  Inspect release notes and the new digest, then make upgrades as reviewed Git
  changes; maintenance does not refresh application images.
- Validate Compose through `sops exec-env`; never render a decrypted config into
  the response. Run the offline gate, commit and push the clean artifact,
  deploy only that stack when no host/shared change requires more, then verify
  container state, logs, and the endpoint through the same path its client
  uses.
- For Caddy changes, read `docs/ingress.md` and the complete Caddyfile.
  `scripts/deploy.sh caddy` performs the reload; still verify the affected
  route and run
  `ssh 100.103.224.99 'docker exec -w /etc/caddy caddy caddy validate'`.

## Add a stack or service

1. Choose a lifecycle boundary from dependencies, secrets, restart coupling,
   and failure domain. Reuse an existing stack when those are shared; do not
   merge unrelated projects merely to reduce the Compose-file count.
2. Follow current neighboring conventions: top-level `name:`, explicit
   `container_name:`, pinned `tag@sha256:digest` image, restart policy,
   healthcheck, security options, network, and
   `${VAR:?run via sops exec-env}` for required secrets.
3. Put mutable data outside `~/home-server`. Add every persistent bind source
   to `host/data-layout.tsv` with deliberate owner, group, mode, and
   `backup=yes|no`; explain the consequence in `docs/state-and-backups.md`.
   Add an application-consistent export when backing up live files is unsafe.
4. Default UI ports to the Tailscale IP. For internal HTTPS or LAN ingress,
   update every layer documented in `docs/ingress.md` and the router/DNS
   declarations. Public ingress is not part of the current architecture.
5. Update `docs/services.md` and `docs/credentials.md` when applicable. The
   healthcheck derives container presence from `container_name:`; add an HTTP or
   TCP probe only when it provides a stable, meaningful signal.
6. Validate, commit, and push. Use a full deploy when the new service added a
   data-layout or other `host/` change so host convergence creates bind sources
   before Compose; otherwise deploy the new stack explicitly. Exercise the
   endpoint, run verification, and confirm drift is clean.

## Remove a stack or service

1. Inventory ingress, DNS, health probes, notifications, integrations, backup
   paths, credentials, and app data. Ask separately about deleting data. Bind
   data often contains root-owned files, so a plain user `rm` cleans it only
   partially — during an explicitly approved full removal, inspect ownership
   first and use `sudo` on the exact app-owned paths.
2. While the deployed compose definition still exists, stop/remove the compose
   project with `docker compose down` through its SOPS environment. Do not add
   `--volumes` unless Jacob explicitly approved volume deletion.
3. Remove repo configuration and all now-stale references. Preserve bind data
   and named volumes by default. If Jacob wants the retired state recoverable,
   keep its `backup=yes` data-layout row or create a validated export under an
   explicitly backed-up path and document it; merely leaving data on the live
   disk is not preservation after a host loss. Validate, commit/push, deploy
   affected shared or host scope, and confirm no orphaned route, container, or
   drift remains.

## Change host state

- Declare packages in `host/packages.txt`, host configuration in `host/etc/`,
  units in `host/systemd/`, and automation in `host/scripts/`. Do not use an
  ad-hoc `pacman -S` as the final state.
- After checks and a clean commit/push, run the full no-argument deploy. It
  invokes `host/install.sh`, creates missing data-layout roots, converges the
  repo-owned systemd namespace in both directions, and preserves the current
  activation state. Do not run the installer a second time. Package removal is
  a separate human decision: inspect reverse dependencies before `pacman -Rns`.
- Routine maintenance deliberately excludes Docker runtime upgrades. Read
  `host/scripts/maintenance.sh` before intentionally updating Docker,
  containerd, or runc because that path restarts the runtime and runs a canary.
- Docker's desired default logger is `local`. A changed daemon config restarts
  Docker, and a full deploy may recreate legacy containers so the new default
  takes effect; treat that as a disruptive migration and verify every project.

## Change secrets or credentials

- Edit encrypted values with `sops <file>`. List only key names when inspecting.
  Use `sops exec-env` for validation and live commands.
- Read the secrets inventory in `docs/services.md` and reset recipes in
  `docs/credentials.md`. Rotate every documented duplicate and downstream
  consumer; a SOPS value is not always the live app credential.

## App-owned and external state

- Use `docs/services.md` to distinguish repo-owned config from app databases,
  generated config, cloud consoles, and router state. Make runtime edits only
  when the app owns that state and record the rebuild procedure in the canonical
  docs if it is not already reproducible.
- For router or Tailscale work, read `host/router-openwrt.sh`,
  `host/router-adguardhome.yaml`, `docs/tailscale.md`, and
  `docs/ingress.md` as applicable. Identify admin-console steps that a
  repo deploy cannot perform.
- The router's hijack-DNS DNAT intercepts direct port 53, including
  `dig @1.1.1.1`. Test a public resolver with DoH to its literal IP instead:
  `curl -H 'accept: application/dns-json' 'https://1.1.1.1/dns-query?name=<host>'`.
- The Cloudflare `ragsdale.dev` zone carries ProtonMail MX, DKIM, SPF, and DMARC
  records. Never bulk-delete the zone when changing web or ingress records.
- Live OpenWrt firewall redirects may be anonymous `@redirect[N]` sections
  even though `router-openwrt.sh` now writes named sections. Match the `name`
  option and delete anonymous indices from highest to lowest.
- Projects listed as “own repo” in `docs/services.md` are changed and deployed
  from their own checkout under `~/dev` on the server. Do not migrate their
  compose files into this repo merely to operate them.

## Service-specific guardrails

- After a reboot or a Tailscale-bound port failure, inspect
  `jacob-home-net-reconcile.service` and `host/logs/net-reconcile.log` before
  restarting containers individually. The boot service waits for the declared
  Tailscale IP and converges every always-on project; there is intentionally no
  periodic healer. Use `host/scripts/docker-net-heal.sh` only for an evidenced
  detached Docker network endpoint.
- Add media through Seerr/Sonarr/Radarr, not Transmission. Stop Transmission
  before editing its server-side `settings.json`; it rewrites that file on
  shutdown. Test linuxserver-container file operations as uid 1000 when
  ownership matters.
- Run media cleanup with `DRY_RUN=1` before changing deletion behavior or
  executing an unusual cleanup. Jellyfin favorites and in-progress playback are
  deliberate protections; read the script before altering them.
- RomM's `EJS_defaultControls` replaces the entire control map. Supply a full
  per-core map; browser localStorage may still override per-game toggles.
- Treat only the Home Assistant files explicitly synced by `deploy.sh` as
  repo-owned. The rest of `~/home-assistant` is live, root-owned app data.
- Read `docs/services.md` hardware detail before audio or ML work. Match ALSA
  devices by name, not card number, and assume CPU-only inference unless the
  live host proves otherwise.
