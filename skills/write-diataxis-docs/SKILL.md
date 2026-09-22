---
name: write-diataxis-docs
description: "Write or audit Diátaxis docs: tutorials, how-tos, reference, explanation. Use whenever the user drafts, restructures, or reviews a README, guide, or API/CLI reference—even if they don't name Diátaxis. Not for docstrings or formatting-only edits."
---

# Write Diátaxis documentation

Classify each piece of documentation by the reader's need, write it in the one
mode that serves that need, and verify it against the product. The user's
explicit instructions and the repository's established docs conventions take
precedence over this skill; this skill fills the gaps they leave.

Copy this checklist into your working notes and tick it off:

```text
- [ ] 1. Sources read, reader and outcome stated
- [ ] 2. Mode chosen per content unit; mode reference read
- [ ] 3. Drafted in the local voice
- [ ] 4. Cut pass done
- [ ] 5. Commands and examples run; reader test if required
- [ ] 6. Reported what remains unverified
```

## 1. Establish the documentation truth

Read the code, schemas, `--help` output, configs, and existing docs that govern
the content before writing a sentence. Every flag, option, environment
variable, config key, default, endpoint, error string, and version you name
must appear in a source you inspected. When you cannot find one, leave it out
or mark it `TODO: verify` in the draft and list it in your report. When code
behavior looks like a bug, flag it to the user instead of documenting it as
intended. Watch for similar names and acronyms that refer to different things.

State the reader, what they already know, what they are doing right now, and
the outcome the page must produce. Ask only when an unresolved audience or
outcome choice would change the document's mode or scope; otherwise state the
assumption and proceed.

Read two or three neighboring pages and adopt their heading case, person,
admonition syntax, code-fence languages, line wrapping, and terminology. Apply
[references/style.md](references/style.md) only where the repository is silent.

## 2. Classify before drafting

Ask two questions of each content unit (page, section, or sentence):

1. Does it inform the reader's action or their cognition?
2. Is the reader acquiring skill (study) or applying skill (work)?

| Need | Mode | Reader's question | Read before drafting |
|---|---|---|---|
| Action + study | Tutorial | "Can you teach me to…?" | [references/tutorials.md](references/tutorials.md) |
| Action + work | How-to guide | "How do I…?" | [references/how-to-guides.md](references/how-to-guides.md) |
| Cognition + work | Reference | "What is…?" | [references/reference.md](references/reference.md) |
| Cognition + study | Explanation | "Why…?" | [references/explanation.md](references/explanation.md) |

Read the reference for every mode you are writing, and no others. Each one
holds the required shape, the language patterns, the title form, a check, and
a skeleton.

Classify by need, not by title or surface form. Steps alone do not make a
tutorial: both tutorials and how-to guides give steps, and how-to guides can
cover basic procedures. The difference is whether the reader is learning in a
setting you control or getting real work done. Material that is dry and meant
to be looked up is reference. Material someone could read away from the
keyboard is explanation.

If the requested document type conflicts with the reader's need, name the
mismatch and recommend the right mode. Follow the user's explicit choice after
stating the trade-off.

## 3. Write to one mode

Keep every section loyal to its mode. Move substantial material that serves
another need into its own page or section and link to it at the point where
the reader would want it. A one-clause reason in a tutorial or a short usage
example in reference does not break the mode. A developed digression does.

Write in the language of the chosen mode, as described in its reference file.
A few defaults hold for every mode:

- **Lead with the point.** Open each page and section with the outcome, the
  fact, or the answer. The first sentence adds information beyond the heading.
- **Readers land mid-page.** People arrive from search, and agents from
  retrieval. Name the subject in each section rather than relying on "as
  mentioned above", or on a "this" or "it" that points across sections.
- **Say what the reader cannot see.** Spend words on constraints, defaults,
  side effects, failure modes, and reasons, not on what the name, signature,
  or UI already shows.
- **Format for the mode's job.**
  - Use numbered steps for sequences.
  - Use tables or repeated field blocks for reference facts.
  - Use paragraphs for explanation and connective text.
  - Use a bullet list only for three or more parallel, discrete items.
  - Headings name the task, object, or question. Never put a heading over a
    single short paragraph.
- **Examples are real.** Build commands and code from values in the codebase,
  not `foo`, `bar`, or `your-api-key-here`. Name placeholders in
  `UPPER_SNAKE_CASE` and define them right after the block. Put commands and
  their output in separate blocks.
- **Callouts are rare.** Write prerequisites, steps, expected results, and
  links as body text. Save a warning for data loss, security exposure, or an
  irreversible action.
- **Length matches scope.** Cover what this reader needs for this need, then
  stop.

## 4. Cut before delivering

Reread the draft once, only to delete:

- Openers that announce the page ("In this guide we will…", "This section
  describes…"), and closing summaries, conclusions, or takeaways that repeat
  the page.
- Significance padding ("plays a crucial role", "it's important to note").
- Marketing and ease words: seamless, powerful, robust, simply, just, easily.
- Hedges that express no real uncertainty.
- Emoji and bold used for emphasis.

Every sentence must carry information the page does not already give. For the
full list of tells and their fixes, see
[references/style.md](references/style.md).

## 5. Verify

Run every documented command, code sample, and procedure from the declared
prerequisites in a safe, representative environment. Compare the actual output
with what the page promises. If the result differs from the page, the page is
wrong, not the reader. Check that links and anchors resolve. When something
cannot be run, such as production-only steps, paid services, or destructive
operations, say exactly which parts are unverified. Never present an unrun
sequence as tested.

For a new tutorial or how-to guide, test it with a fresh reader when you can
spawn a subagent. Give the subagent only the page and the reader's declared
starting state. Ask it to list each place where it would have to guess, and
to answer three questions the target reader would ask. Fix the page wherever
the subagent guessed or answered wrongly.

## 6. Organize and deliver

Diátaxis is a way to analyze and write, not a four-folder layout. When changing
navigation, landing pages, READMEs, FAQs, changelogs, or pages that fit no
mode, or when auditing a docs set, read
[references/architecture.md](references/architecture.md) first.

Improve existing docs in small, publishable steps. Do not create empty category
pages or propose a wholesale migration unless the user asks for one.

For an audit, report one row per finding: `location → user need → current
mode → problem → smallest repair`. Order the rows so that a wrong or unclear
purpose comes before cosmetic issues. For authored content, deliver the
document plus only what the user needs to act on:
- the assumptions you made
- the `TODO: verify` items
- the unverified steps
- any companion pages you recommend

## Example

**Input:** "Write a getting-started guide that teaches a first-time user to run
the service, lists every CLI flag, and explains why the architecture uses a
worker queue."

**Output:** Write the getting-started page as a tutorial titled after what the
learner builds. It leads through one controlled run, with each step followed by
"You should see…" and the real output. The queue appears in a single clause:
"The job waits in the queue until a worker picks it up." The complete flag
list becomes CLI reference, generated from `--help`. The queue rationale
becomes an explanation page, "About the worker queue". The tutorial links to
both from its final "Next steps", not mid-path. The report lists the tutorial
as run end-to-end on a clean checkout, and says which flags `--help` did not
describe.

## Bundled resources

Read each file only when its trigger applies:

- `references/tutorials.md`, `how-to-guides.md`, `reference.md`,
  `explanation.md`: read the file for each mode you are writing or reviewing.
- `references/style.md`: read when the repository has no style conventions,
  or during the cut pass. It holds the list of tells, voice, procedure
  mechanics, code and link conventions, and docs-testing tools.
- `references/architecture.md`: read for navigation, landing pages, composite
  or out-of-mode pages, and audits. It holds the improvement loop, quality
  layers, and sources.
