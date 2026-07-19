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
   network/VPN → Caddy → LAN/router/DNS → Tailscale or public provider.
4. Check `host/logs/{healthcheck,maintenance,backup}.log` and the corresponding
   systemd unit when the issue may be scheduled or host-wide.
5. Explain the cause before proposing a change. Do not restart first and erase
   the evidence unless availability requires it and the user authorized a fix.

## Change an existing stack

- Read its complete compose file, SOPS key names, mounts, networks, and the
  matching `docs/services.md` row. Search for cross-stack references before
  renaming a service, container, port, secret, hostname, or path.
- Validate Compose through `sops exec-env`; never render a decrypted config into
  the response. Deploy only that stack, then verify container state, logs, and
  the endpoint through the same path its client uses.
- For Caddy changes, read `docs/public-ingress.md` and the complete Caddyfile.
  `scripts/deploy.sh caddy` performs the reload and CrowdSec sync; still verify
  the affected route and run
  `ssh 100.103.224.99 'docker exec -w /etc/caddy caddy caddy validate'`.

## Add a stack or service

1. Follow the current conventions in neighboring stacks: top-level `name:`,
   explicit `container_name:`, restart policy, healthcheck, security options,
   network, and `${VAR:?run via sops exec-env}` for required secrets.
2. Put mutable data outside `~/home-server`; choose ownership deliberately.
   Decide whether it belongs in `host/scripts/backup.sh` and whether restore
   needs to recreate excluded/cache directories.
3. Default UI ports to the Tailscale IP. For internal HTTPS or public ingress,
   update every layer documented in `docs/public-ingress.md` and the router/DNS
   declarations. Add authentication and a CrowdSec login scenario when the
   exposure model requires them.
4. Update `docs/services.md` and `docs/credentials.md` when applicable. The
   healthcheck derives container presence from `container_name:`; add an HTTP or
   TCP probe only when it provides a stable, meaningful signal.
5. Validate, deploy the new stack explicitly, exercise the endpoint, run the
   relevant healthcheck, and confirm drift is clean.

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
   and named volumes by default. Deploy affected shared stacks and confirm no
   orphaned route, container, or drift remains.

## Change host state

- Declare packages in `host/packages.txt`, host configuration in `host/etc/`,
  units in `host/systemd/`, and automation in `host/scripts/`. Do not use an
  ad-hoc `pacman -S` as the final state.
- Deploy to sync the tree, run `host/install.sh` remotely, then verify the
  affected unit/config and `scripts/drift.sh`. Package removal is a separate
  human decision: inspect reverse dependencies before `pacman -Rns`.
- Routine maintenance deliberately excludes Docker runtime upgrades. Read
  `host/scripts/maintenance.sh` before intentionally updating Docker,
  containerd, or runc because that path restarts the runtime and runs a canary.

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
  `docs/public-ingress.md` as applicable. Identify admin-console steps that a
  repo deploy cannot perform.
- Projects listed as “own repo” in `docs/services.md` are changed and deployed
  from their own Mac repository. Do not migrate their compose files into this
  repo merely to operate them.

## Service-specific guardrails

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
