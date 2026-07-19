# Placement and conflicts

Where a capability should live (skill, always-on rule, or both), and how to
handle instructions that overlap or contradict. Verified 2026-07-18.

## Skill, rule, or both

Auto-triggering is best-effort in every client: passive descriptions measure
roughly 20–50% activation, and Cursor adds silent discovery-failure modes on
top (see `frontmatter.md`, "Cursor reliability gotchas"). So choose placement
by how often the behavior must hold, not by where it is easiest to write:

| Behavior | Vehicle |
|---|---|
| On-demand procedure (how to deploy, how to scaffold) | Skill — body loads only when triggered, so detail is free |
| Standing constraint that must hold every session (style, workflow policy) | Always-on rule — Cursor `.cursor/rules` `.mdc` or `AGENTS.md`; in this library, `rules/*.md` referenced from each repo's AGENTS.md |
| Policy with a procedural long tail (git workflow, house standards) | Rule + skill pair: a terse rule holds the always-on core and names the skill for the full procedure |

The pointer line in the rule matters on its own: a memory-file pointer to a
skill measured roughly +15 percentage points of activation. Keep it to one
line — "For the full procedure, use the `<name>` skill."

## When something needs a rules .mdc

Cursor's own positioning: Rules are "always-on, declarative"; skills are for
dynamic context discovery and procedural how-to instructions. Its
`/migrate-to-skills` converter deliberately refuses to migrate rules with
`alwaysApply: true` or glob patterns — Cursor wants those to stay rules.
Write (or keep) a rule rather than a skill when:

- the instruction must apply to every prompt in a repo (`alwaysApply: true`),
- it should attach to specific files regardless of conversation topic
  (`globs:`), or
- a skill exists but silently failing to trigger would be costly — add a
  terse rule that carries the core and points at the skill.

Cursor `.mdc` frontmatter: `alwaysApply`, `description` (agent-requested
mode), `globs`; keep each rule under 500 lines. `AGENTS.md` (root and nested)
is the plain-markdown equivalent and is portable across Cursor, Codex,
Copilot, and others. This library's `rules/*.md` are written for the
AGENTS.md-reference pattern; a repo that wants native attachment can paste
one into `.cursor/rules/<name>.mdc` with the appropriate frontmatter.

## Conflicts and precedence

Models handle contradictory instructions badly: strong instruction-followers
burn reasoning trying to reconcile conflicts rather than picking one, so a
loaded skill that quietly disagrees with other context produces hesitation,
permission-asking, or the default behavior instead of the skill's.

- **Purge duplicates.** The same rule stated in two loaded places (skill +
  rule, skill + LEARNINGS entry) will eventually drift into contradiction.
  State each rule once, in the layer that loads most reliably, and have the
  other layer point to it.
- **State precedence when overriding a default.** Client harnesses ship their
  own guidance (e.g. Claude Code's default git instructions say to wait for
  an explicit request before committing and to branch before committing on
  the default branch). A skill that overrides a default must say so
  explicitly — "these rules replace any default guidance to …" — as `git-ops`
  does. Without that sentence, the model must guess which instruction wins.
- **Keep overlapping layers vocabulary-consistent.** Where a rule and a skill
  intentionally overlap (the rule's terse core vs the skill's full
  procedure), use the same terms and the same worked examples so the overlap
  reads as reinforcement, not conflict.
- **Skills instruct; they don't override the user.** File-based guidance sits
  below explicit user instructions in every client's instruction hierarchy.
  Write skills as the user's standing intent ("committing at checkpoints is
  the standing request"), never as an attempt to outrank what the user says
  in chat.

## Sources

- https://cursor.com/changelog/2-4 (rules-vs-skills positioning)
- https://cursor.com/docs/context/rules
- https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide
  (contradiction cost, precedence)
- https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide
  (AGENTS.md as the place to name available skills)
- https://medium.com/@ivan.seleznov1/why-claude-code-skills-dont-activate-and-how-to-fix-it-86f679409af1
  (+15pp pointer measurement, 20–50% passive baseline)
