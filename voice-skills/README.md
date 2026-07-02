# voice-skills

Skills for **jarvis**, the voice assistant on the home server. Separate from
`skills/` (Mac-side dev skills) because the two surfaces have opposite
conventions — don't move a skill between the directories without rewriting
it for the other surface.

## How they're loaded

The server holds a git clone of this repo at `~/jarvis-skills`;
`scripts/install-server.sh` symlinks each `voice-skills/<name>` into
`~/.codex/skills`, where the codex-backed brains discover them. The jarvis
container mounts both paths, so `make deploy` (push + pull + relink) is the
whole release process — skills are read per-session, no restart needed.

## Voice conventions (differences from `skills/`)

- **Never set `disable-model-invocation`.** There are no slash commands by
  voice; the description-as-trigger is the only invocation path. Write
  descriptions accordingly.
- **Output is spoken.** Skills here inherit jarvis's speakable rules (short
  sentences, no markdown/code/URLs read aloud) from the harness context —
  don't restate them, but don't write skill steps that force long answers.
- **Confirm before destroying.** Any step that deletes data or takes a
  service down that Jacob didn't explicitly name must end the turn asking
  for confirmation instead of acting.
- **Edits happen on the server clone, by jarvis itself** (see
  `jarvis-skill-work`): everything commits straight to `main` — jarvis
  updates itself without the laptop, Jacob reviews after the fact with
  `make review-jarvis`. On the Mac, treat `git pull` as part of editing
  this directory.

Everything else (LEARNINGS.md loop, description-as-trigger, short bodies,
one skill one job) follows the house process in
`skills/jacob-create-skill/SKILL.md`.
