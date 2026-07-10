# Recovery, rehearsal, and the Windows VM

Read this file before restoring backups, rebuilding a host, rehearsing a
rebuild, or destroying/resetting the on-demand Windows VM.

## Backup and restore

- Read `host/scripts/backup.sh`, `host/scripts/restore.sh`, the backup section
  of `docs/services.md`, and the `bootstrap.sh` header before acting. The code is
  authoritative for current paths, retention, and prerequisites.
- Inspect snapshots before restoring. `restore.sh` is intentionally interactive,
  writes absolute paths under `/`, overwrites existing files, and verifies the
  restored data. Restoring configuration is a live destructive action; obtain
  explicit approval for the selected snapshot and target.
- Media and the Windows disk are intentionally outside the restic backup. Do not
  claim they are recoverable from B2. Confirm critical new service state was
  added to the backup path list before calling a deployment complete.
- A restore includes `/home/jacob/.ssh` and can replace `authorized_keys`. Use
  Jacob's production key for access and plan the connection around that change.

## Production rebuild

Follow the current `bootstrap.sh` header, not a memorized sequence. The durable
shape is: validate the destructive archinstall disk config → install Arch →
restore the age key → sync the Mac repo → run `bootstrap.sh` → restore the chosen
restic snapshot → deploy → complete router/Tailscale/cloud-console steps →
verify from both LAN and tailnet/public client paths.

Reconfirm the hostname, fixed Tailscale identity/IP, LAN reservation, disk
layout, age key, restic password, and SSH access before starting. Credentials
remain interactive or in a local uncommitted file.

## Rebuild rehearsal

- Set `REHEARSAL=1` on `bootstrap.sh`, `host/install.sh`, and every deploy or
  drift command pointed at the VM. Also set `SERVER=<vm-alias>`. This prevents a
  tailnet join, leaves timers disarmed, and scales cloudflare-ddns to zero.
- Never arm production timers on a rehearsal box. The backup timer executes
  `restic forget --prune` against the real B2 repository; health and cleanup
  timers can page the phone or delete rehearsal data.
- Compose binds the production Tailscale and LAN addresses. Add both as `/32`
  loopback addresses in the VM before deploy and re-add them after reboot.
- A fresh box has password-based sudo until the first `host/install.sh` run
  installs the validated NOPASSWD drop-in. Plan for the first prompt.
- For QEMU/slirp, disable IPv6 or provide deterministic reachable DNS before
  Docker builds. Over serial, ttyS0 is a login prompt; detached installers must
  not read the tty. After an interrupted archinstall, clear leftover chroot
  `gpg-agent` or nspawn processes before re-wiping.
- Treat a successful rehearsal as evidence only after restore verification,
  targeted endpoint checks, host health, and drift all pass.

## On-demand Windows VM

- Read `scripts/vm.sh`, `stacks/windows/compose.yaml`, and the Windows row in
  `docs/services.md`. The `.on-demand` marker intentionally excludes it from
  deploy-all, maintenance refresh, drift failures, and health paging.
- Use `scripts/vm.sh on|off|logs|console` for normal control. Compose may expand
  required Windows credentials even for `ps`; run status through the stack's
  SOPS environment or use `docker ps` for a read-only container check.
- `scripts/vm.sh destroy` deletes the VM disk and requires explicit approval.
  Do not equate “turn it off,” “reset a service,” or “remove a temporary user”
  with permission to destroy the VM.
- Let a temporary Windows user's first password login create its profile before
  adding `authorized_keys`. Pre-creating the profile path can produce a suffixed
  profile; if a deleted user's profile hive remains loaded, reboot the disposable
  VM before CIM cleanup.
