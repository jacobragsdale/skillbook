---
name: jarvis-skill-work
description: "Create a new jarvis voice skill, or record a correction, fix, or improvement to an existing one, when Jacob asks by voice. Use when a task says a skill got something wrong, should behave differently, or that jarvis needs a new capability or skill."
---

# Working on voice skills

The skills you run with live in the git clone `~/jarvis-skills` on the host
(this container sees it read-only). All edits and git commands go through
ssh:

```
ssh jacob@100.103.224.99 'git -C ~/jarvis-skills status'
```

Voice skills are `voice-skills/<name>/SKILL.md` (+ `LEARNINGS.md`);
conventions are in `voice-skills/README.md` — read it before writing a
skill. Never touch `skills/` (Jacob's Mac-side dev skills).

## Every change → main, immediately

All voice-skill work — corrections, new skills, rewrites — commits to
`main` and goes live at once; Jacob reviews after the fact
(`make review-jarvis` on his Mac). Pull first, push when done:

```
ssh jacob@100.103.224.99 'cd ~/jarvis-skills \
  && git pull --rebase origin main \
  && <edits under voice-skills/ — heredocs or a script via ssh> \
  && git add -A && git commit -m "<type>(<name>): <what and why>" \
  && git push origin main'
```

Commit types: `learn(<name>)` for LEARNINGS.md appends, `skill(<name>)`
for new or changed skills. If the push is rejected, `git pull --rebase
origin main` and push again. Then tell Jacob it's saved and takes effect
on his next request.

Rules that keep auto-merge safe:

- For "the X skill got Y wrong" or "remember that Z": append one dated
  line (`- YYYY-MM-DD: <what happened> → <what to do instead>`) to that
  skill's `LEARNINGS.md` — never edit SKILL.md for a one-off.
- Only touch `voice-skills/`. Never `skills/`, `install.py`, the Makefile,
  or `scripts/` — if a task needs that, say it needs Jacob's Mac.
- Keep new skills small: description written as a trigger ("Use when …"),
  body only what an agent would otherwise get wrong, a LEARNINGS.md seeded
  empty, and no `disable-model-invocation` — voice skills must
  auto-trigger.
- Commit messages carry the why — they're Jacob's review trail.

## Improving this skill

Before executing, read `LEARNINGS.md` in this skill's folder — entries there
override the instructions above. After use, if the user corrected you or the
outcome surprised you, append one dated line to `LEARNINGS.md`:
`- YYYY-MM-DD: <what happened> → <what to do instead>`. Do not edit SKILL.md
directly; lessons are folded in deliberately, not on the fly.
