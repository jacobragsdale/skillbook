---
name: write-diataxis-docs
description: "Write Diátaxis documentation: tutorials, how-tos, reference, and explanation. Use whenever the user creates, restructures, or audits technical docs—even if they don't name Diátaxis. Not for formatting-only edits."
---

# Write Diátaxis documentation

Classify documentation by the user's need, then create or improve content whose
purpose, form, and language consistently serve that need.

## Workflow

### 1. Establish the documentation truth

- Inspect the product, code, schemas, commands, existing docs, and repository
  conventions that govern the requested content. Treat them as the factual
  source of truth; never invent product behavior to complete a document.
- Identify the intended reader, their assumed competence, what they need at
  this moment, and the outcome the documentation must produce.
- Ask only when an unresolved audience or outcome choice would materially
  change the document. Otherwise state the assumption and proceed.

### 2. Classify before drafting

Ask the Diátaxis compass questions:

1. Does the reader need action or cognition?
2. Are they acquiring skill through study or applying skill in their work?

| User need | Mode |
|---|---|
| Action + acquisition | Tutorial |
| Action + application | How-to guide |
| Cognition + application | Reference |
| Cognition + acquisition | Explanation |

Choose one primary need for each content unit. Apply the compass at page,
section, or sentence level when the material is mixed. Do not classify by title
alone: a page named "guide" or "overview" can belong to any mode.

If the requested document type conflicts with the reader's actual need, name
the mismatch and recommend the appropriate mode. Follow an explicit user choice
after making the trade-off clear.

### 3. Write to one mode

Read [references/framework.md](references/framework.md) before drafting,
restructuring, or reviewing documentation. Use its playbook and checklist for
the selected mode.

- Keep every section loyal to its primary mode.
- Move substantial material serving another need into its own page or section,
  then cross-link it at the point where the reader might need it.
- Retain only the minimum inline context required to continue safely. A brief
  reason in a tutorial or a small usage example in reference does not change
  the mode; a developed digression does.
- Use the local documentation system's established terminology, markup, and
  navigation conventions unless the user asks to change them.

### 4. Organize around needs

- Treat Diátaxis as an authoring and analysis method, not a demand for exactly
  four top-level folders. Let the information architecture reflect audience,
  product, and topic boundaries while keeping the four purposes distinct.
- Structure reference material in sympathy with the machinery it describes.
- Structure tutorials around a coherent learning journey, how-to guides around
  real user goals, and explanations around bounded topics or questions.
- When improving an existing documentation set, prefer the smallest publishable
  improvement that clarifies a user need. Do not create empty category pages or
  propose a wholesale migration unless the user requests one.

### 5. Verify the result

Use the relevant type checklist in `references/framework.md`, then check:

- **Truth:** commands, examples, outputs, links, prerequisites, versions, and
  warnings agree with current authoritative sources.
- **Purpose:** each content unit serves one identifiable user need and contains
  no avoidable drift into another mode.
- **Findability:** titles state the task, object, or topic precisely; navigation
  and cross-links let readers move to other needs without interrupting this one.
- **Functional quality:** the content is accurate, complete for its stated
  scope, consistent, useful, precise, and maintainable.
- **Deep quality:** the sequence and presentation fit the reader's situation,
  anticipate likely questions, and feel natural to use.

Execute documented procedures in a safe representative environment when
possible. If execution is unavailable, say exactly what remains unverified;
never present an unrun tutorial or command sequence as proven reliable.

For an audit, report `location → current need → current mode → problem → smallest
repair`. For authored content, deliver the document plus only the assumptions,
verification limits, or companion pages the user needs to act on.

## Example

**Input:** “Write a getting-started guide that teaches a first-time user to run
the service, lists every CLI flag, and explains why the architecture uses a
worker queue.”

**Classification and output:** Make the requested getting-started document a
tutorial: lead the learner through one controlled, successful run; show expected
results after each step; and give only the minimal queue rationale needed to
continue. Put the complete flag list in CLI reference and the architectural
rationale in an explanation page. Link both from the tutorial instead of
interrupting its learning flow.

## Bundled resources

- `references/framework.md` — **read** before writing or auditing; use the
  compass, mode playbooks, boundary tests, output patterns, and quality checks.
- `evals/trigger_queries.json` — **read** when testing automatic routing.
- `evals/evals.json` — **read** when forward-testing output quality.
