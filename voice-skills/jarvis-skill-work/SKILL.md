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

## Corrections and lessons → main, immediately

For "the X skill got Y wrong" or "remember that Z": append one dated line
to that skill's `LEARNINGS.md` — never edit SKILL.md for a one-off:

```
ssh jacob@100.103.224.99 'cd ~/jarvis-skills \
  && echo "- $(date +%F): <what happened> → <what to do instead>" >> voice-skills/<name>/LEARNINGS.md \
  && git add -A && git commit -m "learn(<name>): <short summary>" \
  && git push origin main'
```

If the push is rejected, `git pull --rebase origin main` and push again.
Then tell Jacob it's saved and takes effect on his next request.

## New skills and rewrites → the `jarvis` branch for review

Bigger changes (a new skill, restructuring a SKILL.md) don't go live
unreviewed. Work on the `jarvis` branch and **always leave the clone on
main** — the working tree is what's live:

```
ssh jacob@100.103.224.99 'cd ~/jarvis-skills \
  && git checkout -B jarvis origin/main'
# ... edit under voice-skills/<name>/ (heredocs or a script via ssh) ...
ssh jacob@100.103.224.99 'cd ~/jarvis-skills \
  && git add -A && git commit -m "skill(<name>): <what and why>" \
  && git push -u origin jarvis --force-with-lease \
  && git checkout main'
```

Then tell Jacob the skill is on the jarvis branch waiting for his review on
the Mac. Keep new skills small: description written as a trigger ("Use
when …"), body only what an agent would otherwise get wrong, a LEARNINGS.md
seeded empty, and no `disable-model-invocation` — voice skills must
auto-trigger.

## Improving this skill

Before executing, read `LEARNINGS.md` in this skill's folder — entries there
override the instructions above. After use, if the user corrected you or the
outcome surprised you, append one dated line to `LEARNINGS.md`:
`- YYYY-MM-DD: <what happened> → <what to do instead>`. Do not edit SKILL.md
directly; lessons are folded in deliberately, not on the fly.
