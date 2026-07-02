---
name: jarvis-server-ops
description: "Diagnose and operate Jacob's home server from inside the jarvis container: container/stack health, service logs, restarts, disk usage, the media stack, jellyfin, postgres, the personal site. Use when a task touches the server, docker, or a misbehaving service."
---

# Home server operations

You are inside the `jarvis` container on the server (`desktop`, Arch).
Everything host-side runs through ssh — the key is installed:

```
ssh jacob@100.103.224.99 'docker ps --format "{{.Names}} {{.Status}}"'
```

`jacob` has passwordless sudo on the host.

## What runs (stack → containers)

- `media-stack` → gluetun (VPN), transmission (UI :9091)
- `jellyfin` → jellyfin (:8096)
- `postgres` → postgres (:5432), drizzle-studio (:4983)
- `dozzle` → dozzle (log viewer, :9999)
- `jacob-personal-site` → jacob-personal-site (:8080, also the lights API)
- `jarvis` → jarvis (you; restarting it kills you mid-sentence — warn first)

Intent lives in `~/home-server/docs/services.md` on the host; live truth:

```
ssh jacob@100.103.224.99 'bash ~/home-server/host/scripts/healthcheck.sh'
ssh jacob@100.103.224.99 'docker logs --tail 50 <container>'
```

## Hard rules

- **Never edit anything under `~/home-server` on the host.** It's a deployed
  copy — the next deploy from Jacob's Mac silently wipes server-side edits.
  Config, compose, or script changes need a deploy from the Mac: say so
  plainly and stop.
- Reading, health checks, `docker restart <container>`, and journal/log
  inspection are fair game when the task calls for them.
- Destructive or disruptive actions — deleting anything, `compose down`,
  reboots, stopping a service Jacob didn't name — need explicit
  confirmation. Ask in your final message; a follow-up task will say go.
- Data directories (`~/media`, `~/torrent`, `~/jellyfin`, `~/file-share`,
  `~/Downloads/complete`) are never cleanup targets, whatever `df` says.

## Improving this skill

Before executing, read `LEARNINGS.md` in this skill's folder — entries there
override the instructions above. After use, if the user corrected you or the
outcome surprised you, append one dated line to `LEARNINGS.md`:
`- YYYY-MM-DD: <what happened> → <what to do instead>`. Do not edit SKILL.md
directly; lessons are folded in deliberately, not on the fly.
