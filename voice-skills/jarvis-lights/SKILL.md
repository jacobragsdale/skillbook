---
name: jarvis-lights
description: "Control or check Jacob's apartment lights (Kasa bulbs, all as one group): on/off, brightness, color, current state. Use when a task involves the lights, lighting scenes, or the lights API."
---

# Apartment lights

The personal site on the server owns the bulbs (native Kasa LAN protocol)
and exposes them as one group at `http://100.103.224.99:8080`:

```
GET  /api/lights/state                      # cached, instant
POST /api/lights/power/on
POST /api/lights/power/off
POST /api/lights/color       {"hsv": [30, 15, 100]}   # hue 0-360, sat/val 0-100
POST /api/lights/brightness  {"brightness": 60}       # 0-100
```

Example: `curl -s -X POST http://100.103.224.99:8080/api/lights/color -H 'Content-Type: application/json' -d '{"hsv":[0,100,100]}'`

- Commands answer `{"ok":true,"message":"... (8 bulbs)"}`; treat `ok:false`
  or a connection error as "the lights aren't responding" and say so.
- `state` reports `on_count`/`total`, consensus `hsv`/`brightness`, and
  `mixed:true` when bulbs disagree.
- Warm white is hue 30, saturation 10-20, value 100 — not color-wheel
  yellow. There is no per-bulb or per-room control; don't promise any.
- The fast brain handles plain "turn the lights red" itself; this skill is
  for deep-brain tasks that involve the lights (scenes, checks, scripts).

## Improving this skill

Before executing, read `LEARNINGS.md` in this skill's folder — entries there
override the instructions above. After use, if the user corrected you or the
outcome surprised you, append one dated line to `LEARNINGS.md`:
`- YYYY-MM-DD: <what happened> → <what to do instead>`. Do not edit SKILL.md
directly; lessons are folded in deliberately, not on the fly.
