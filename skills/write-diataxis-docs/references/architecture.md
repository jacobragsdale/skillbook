# Documentation architecture, audits, and quality

This file covers:
- how to split content into modes
- how to structure a docs set
- how to handle pages that fit no single mode
- how to improve docs iteratively
- what "quality" means

It was reviewed against diataxis.fr and its repository on 2026-09-22.

## Contents

- Mixed content
- Structure of a docs set
- Pages outside the four modes
- The improvement loop and audits
- Quality
- Sources and freshness

## Mixed content

- Classify at the smallest useful unit. If a page resists classification,
  look at its sections and then its sentences. Do not force one label onto the
  whole page.
- Relocate material that serves a valid need. Do not delete it just because
  it sits in the wrong mode.
- Link at the moment the adjacent need arises, with link text that says what
  the destination provides.
- Adjacent modes blur along a shared trait:
  - Tutorial and how-to guide both guide action.
  - How-to guide and reference both serve work.
  - Reference and explanation are both theory.
  - Explanation and tutorial both serve study.

  When two modes are blurring, ask which trait they do not share.

## Structure of a docs set

- Diátaxis does not require four top-level folders. In a complex product,
  audience, product, platform, or deployment target can be the primary
  navigation axis, with the modes repeated or spread beneath it.
- Let reader needs drive the structure. Team ownership or internal component
  boundaries matter only when they also match how readers look for
  information.
- Write landing and index pages as short overviews in prose that orient the
  reader and say what each group is for. A bare list of links is not an
  overview. Break lists of more than about seven items into named groups.
- Reference structure mirrors the machinery. Tutorials follow a learning
  journey. How-to guides follow user goals. Explanation follows topics.

## Pages outside the four modes

Diátaxis claims completeness only for docs that serve practitioners of a craft.
Composite pages are fine when each section stays loyal to one mode.

- **README:** a landing page. Open with what the project is and who it is for,
  in one or two sentences. Then give install and a minimal working example (a
  compact tutorial or quick start), then links to the full docs by need, then
  how to contribute and the license. Keep option catalogues and design
  rationale on separate pages.
- **Quick start:** a short tutorial for readers who will skim. Keep it to one
  path with visible results, and link out for everything else.
- **Troubleshooting:** a how-to guide whose goal is getting a failure fixed:
  symptom, cause, then resolution. An error-code catalogue is reference. See
  `how-to-guides.md`.
- **Changelog and release notes:** a dated, neutral record, grouped as added,
  changed, deprecated, removed, fixed, and security. Put each breaking change
  first, with a link to a migration how-to guide. Follow the project's
  existing format, such as Keep a Changelog or conventional commits.
- **FAQ:** avoid starting one. Answer each question where readers look for it:
  a "how" in a how-to guide, a "what" in reference, a "why" in explanation. If
  an FAQ exists, keep the answers short and link to the page that owns each
  one.
- **Generated API reference:** necessary but not sufficient. Hand-write
  reference for cross-cutting behavior and constraints, and add how-to guides
  and explanation around it.
- **Agent instruction files (`AGENTS.md`, `CLAUDE.md`):** how-to and reference
  for a competent reader. No tutorial content.
- **Examples and cookbook galleries:** each example is a how-to guide when it
  solves a stated goal, or illustrative reference when it shows one feature.
  Title each one by its goal.

## The improvement loop and audits

Diátaxis prescribes small iterations over up-front plans. A docs set is
"complete, not finished": it is always usable, and it keeps growing.

1. Choose one piece of content, even at random.
2. Assess it:
   - What user need does it represent?
   - How well does it serve that need?
   - What can be added, moved, removed, or changed to serve it better?
   - Do its language and logic meet the requirements of its mode?
3. Decide the single next action that will produce an immediate improvement.
4. Make the change and publish it (commit it, if that is the unit).
5. Repeat.

Do not create empty section structures for content that doesn't exist yet.

For an audit report, give one row per actionable finding:

| Location | User need | Current mode | Problem | Smallest repair |
|---|---|---|---|---|
| Section, or file:line | Action/cognition + study/work | Observed mode | Concrete mismatch or quality lapse | Move, split, cut, add, rename, reorder, or verify |

Rank the rows with a wrong or unclear purpose first, then factual errors, then
structure, then style. For each fix, name the destination page, so that
relocated content does not simply vanish.

## Quality

Diátaxis improves how well docs fit their readers' needs. It does not by
itself guarantee accuracy, visual design, or accessibility.

- **Functional quality** is objective and comes first:
  - accurate
  - complete for its declared scope
  - consistent
  - precise
  - backed by examples and links that work
  - kept current with the code (house rule)
- **Deep quality** is subjective and builds on functional quality:
  - the flow fits the reader's situation
  - likely next questions are anticipated
  - the page is pleasant to use

  Judge deep quality with the fresh-reader test in `SKILL.md`, or by watching
  a representative reader.

For runnable docs:
- Start from the declared prerequisites in a clean or representative
  environment.
- Execute the steps exactly as written.
- Test the branches and recovery paths that matter.
- Record the versions and environment you used.
- State plainly anything you did not run.

## Sources and freshness

- https://diataxis.fr/start-here/
- https://diataxis.fr/tutorials/
- https://diataxis.fr/how-to-guides/
- https://diataxis.fr/reference/
- https://diataxis.fr/explanation/
- https://diataxis.fr/compass/
- https://diataxis.fr/map/
- https://diataxis.fr/tutorials-how-to/
- https://diataxis.fr/reference-explanation/
- https://diataxis.fr/how-to-use-diataxis/
- https://diataxis.fr/foundations/
- https://diataxis.fr/quality/
- The "complex hierarchies" page was removed from the site on 2026-08-03. Its
  guidance on landing pages and two-dimensional structures, kept above,
  survives in the repository history:
  https://github.com/evildmp/diataxis-documentation-framework
- The critiques behind "pages outside the four modes":
  - https://www.hillelwayne.com/post/problems-with-the-4doc-model/
  - https://developers.cloudflare.com/style-guide/documentation-content-strategy/content-types/
  - https://www.thegooddocsproject.dev/template

To check for framework changes since the review date, read
https://diataxis.fr/atom.xml.
