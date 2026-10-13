# Recovery, rehearsal, and the Windows VM

Read this file before restoring backups, rebuilding a host, rehearsing a
rebuild, or destroying/resetting the on-demand Windows VM.

## Contents

- Backup and restore
- Production rebuild
- Rebuild rehearsal
- On-demand Windows VM

## Backup and restore

- Read `host/scripts/backup.sh`, `host/scripts/restore.sh`, the backup section
  of `docs/services.md`, `docs/state-and-backups.md`, and the `bootstrap.sh`
  header before acting. `host/data-layout.tsv` is authoritative for path,
  initial ownership/mode, and backup selection.
- A backup is successful only when required paths exist, the router archive and
  RomM logical dump validate, restic commits a snapshot, retention completes,
  and the final log reports zero failures. A prerequisite failure skips the
  snapshot, and retention must never prune after a failed backup.
- Retention keeps the three newest snapshots in addition to the longer
  daily/weekly/monthly buckets. Before a destructive state migration or global
  rollout, confirm a recent fully successful recovery point; do not create
  repeated off-cycle snapshots for ordinary low-risk config edits.
- Inspect snapshots before restoring. `restore.sh` refuses to run while managed
  production containers are active, is intentionally interactive, writes
  absolute paths under `/`, overwrites existing files, and verifies the
  restored data. Restoring configuration is a live destructive action; obtain
  explicit approval for the selected snapshot and target.
- Media and the Windows disk are intentionally outside the restic backup. Do not
  claim they are recoverable from B2. Confirm critical new service state was
  added to `host/data-layout.tsv` before calling a deployment complete.
- Restore merges the fresh host's current SSH authorization key with the
  snapshot, then imports a RomM logical dump while only MariaDB is running and
  stops it again before the full deployment.
- For a non-destructive recovery drill, restore selected artifacts with
  `restic restore --target <mktemp-dir> --verify`; do not run `restore.sh`
  against the live host. Validate the router tarball and gzip, and import the
  RomM dump into a disposable `--network none` MariaDB using the exact image
  declared by Compose. Initialize both root and `romm-user`: dumped views use
  that definer and an unrealistic root-only fixture will fail. Remove the exact
  test container and temporary tree afterward.
- Repeated restore/check/prune drills can exhaust Backblaze download or Class B
  transaction caps. On a 403 cap response, stop retrying, confirm whether the
  snapshot was already committed from `backup.log`, leave the timer armed, and
  report the external cap/reset follow-up instead of hammering B2.

## Production rebuild

Follow `docs/rebuild.md` and the current `bootstrap.sh` header, not a memorized
sequence. The durable shape is: identify the target disk by model and serial
→ from a Debian live system, `host/debian/provision-root.sh partition` (only
when `/home` is lost) and `build` → reboot and check the new SSH host key →
restore the age key → `deploy.sh --sync-only` → run
`bootstrap.sh` with automation cold → reclaim and approve the Tailscale
identity/IP → restore the chosen restic snapshot → full deploy →
`EXPECT_AUTOMATION=cold scripts/verify.sh` plus drift →
`host/install.sh --activate` → normal verify/drift and real client tests → a
fresh successful backup. When `/home` survived, `build` alone reinstalls the
system beside it: skip the age key and the restic restore.

Reconfirm the hostname, fixed Tailscale identity/IP, LAN reservation, disk
layout, age key, restic password, and SSH access before starting. Credentials
remain interactive or in a local uncommitted file.

Do not deploy the stacks until the fixed Tailscale address exists; several
ports bind directly to it. After reboot, require the boot reconciliation unit
to succeed before treating container restart-policy state as healthy.

## Rebuild rehearsal

- `host/debian/rehearsal.sh` builds and runs the rehearsal guest on the server
  (its header lists the commands); `docs/rebuild.md` "Rehearse safely" has the
  sequence.
- Set `REHEARSAL=1` on `bootstrap.sh`, `host/install.sh`, and every deploy or
  drift command pointed at the VM. Also set `SERVER=<vm-alias>`. This prevents a
  tailnet join and leaves timers disarmed.
- Never arm production timers on a rehearsal box. The backup timer executes
  `restic forget --prune` against the real B2 repository; health and cleanup
  timers can page the phone or delete rehearsal data.
- Compose binds the production Tailscale and LAN addresses. Add both as `/32`
  loopback addresses in the VM before deploy and re-add them after reboot.
- For QEMU/slirp, disable IPv6 or provide deterministic reachable DNS before
  Docker builds. Over serial, ttyS0 is a login prompt; detached installers must
  not read the tty. After an interrupted `provision-root.sh build`, unmount
  `/mnt/debian` recursively before running it again.
- Treat a successful rehearsal as evidence only after restore verification,
  targeted endpoint checks, host health, and drift all pass.

## On-demand Windows VM

- Read `scripts/vm.sh`, `stacks/windows/compose.yaml`, and the Windows row in
  `docs/services.md`. The `.on-demand` marker intentionally excludes it from
  deploy-all, maintenance refresh, drift failures, and health paging.
- Use `scripts/vm.sh on|off|logs|console` for normal control. Compose expands
  required Windows credentials for every subcommand, including `off` and `ps`;
  run all `vm.sh` Compose subcommands through the stack's SOPS environment, or
  use `docker ps` for a read-only container check.
- After enabling Windows features (Hyper-V, WSL), in-guest restarts can hang
  at the UEFI boot-manager screen; recover with a graceful container
  stop/start (full VM power cycle) instead, and verify SSH before continuing.
- Docker Desktop inside the guest needs an interactive-session start, bounded
  `docker info` polling, and console-context pulls of public base images —
  its credential helper fails over SSH.
- Elevated Windows accounts read `administrators_authorized_keys`, not the
  per-user file; provision both key locations before demoting a temporary
  admin. Write guest SCP destinations with forward slashes; keep PowerShell
  paths native.
- `scripts/vm.sh destroy` deletes the VM disk and requires explicit approval.
  Do not equate “turn it off,” “reset a service,” or “remove a temporary user”
  with permission to destroy the VM.
- Let a temporary Windows user's first password login create its profile before
  adding `authorized_keys`. Pre-creating the profile path can produce a suffixed
  profile; if a deleted user's profile hive remains loaded, reboot the disposable
  VM before CIM cleanup.
