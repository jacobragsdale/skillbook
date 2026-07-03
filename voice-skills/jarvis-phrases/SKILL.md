---
name: jarvis-phrases
description: "Refresh, rewrite, or tune jarvis's canned spoken phrases — acknowledgments, confirmations, 'didn't catch that' lines, still-working updates. Use when a task says the phrases feel stale or repetitive, asks for a phrase refresh, or wants the assistant to sound different."
---

# Jarvis's phrase pools

Canned speech lives in pools drawn as shuffle bags. Built-ins are in
`/app/src/jarvis/phrases.py` (read it first — it documents each pool's
job); `/data/phrases.json` overrides any pool by key and **hot-reloads on
save** — no restart, tell Jacob it's live immediately.

Write the file directly (you run inside the jarvis container):

```json
{
  "ack": ["Sure.", "On it.", "..."],
  "didnt_catch": ["..."],
  "dispatch": ["..."],
  "lights_done": ["..."],
  "cancel": ["..."],
  "busy": ["..."],
  "nothing_to_report": ["..."],
  "narration": ["first update", "second update", "final update"]
}
```

Rules:

- Tone is **warm professional** — a great front-desk person: natural,
  brief, personable, never performative. No exclamation-mark enthusiasm,
  no butler-speak, no jokes that will grate on the fortieth hearing.
- Everything is spoken by TTS: no markdown, no emoji; short.
- "ack" lines must work for ANY request (question or command) — they play
  before jarvis knows what it will say. Two to five words. 8-15 of them.
- "narration" is an ordered escalation (spoken ~30s apart during a long
  task), not a pool: 2-4 entries, later entries acknowledging it's taking
  a while; the last should promise to speak up when done.
- Include only the keys you're changing — missing keys keep the built-ins.
  Malformed JSON is ignored (logged), so validate before writing.
- Read the current file first if it exists; evolve, don't clobber, unless
  Jacob asked for a full refresh.

## Improving this skill

Before executing, read `LEARNINGS.md` in this skill's folder — entries there
override the instructions above. After use, if the user corrected you or the
outcome surprised you, append one dated line to `LEARNINGS.md`:
`- YYYY-MM-DD: <what happened> → <what to do instead>`. Do not edit SKILL.md
directly; lessons are folded in deliberately, not on the fly.
