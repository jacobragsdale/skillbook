# Diátaxis authoring reference

This reference distills the current English Diátaxis framework into decisions
and checks for documentation work. It was reviewed against the complete
published source corpus on 2026-08-01. Recheck <https://diataxis.fr/> when the
user needs the latest framework wording or when this synthesis conflicts with
the primary source.

## Contents

- The compass
- Tutorial playbook
- How-to guide playbook
- Reference playbook
- Explanation playbook
- Boundary tests
- Mixed content and information architecture
- Authoring and audit patterns
- Quality and verification
- Primary sources

## The compass

Classify the user need along two axes:

| Content | Reader relationship | Mode | Core question |
|---|---|---|---|
| Informs action | Acquiring skill through study | Tutorial | Can you teach me to...? |
| Informs action | Applying skill at work | How-to guide | How do I...? |
| Informs cognition | Applying skill at work | Reference | What is...? |
| Informs cognition | Acquiring skill through study | Explanation | Why...? |

Use the axes, not keywords, as the decision. “Install the agent” could be a
tutorial for a novice learning the system, a how-to for a competent operator
with a real deployment goal, or reference describing an install command.

Classify at the smallest useful level. If a page resists classification, inspect
its sections and sentences for competing needs rather than forcing a label onto
the whole page.

## Tutorial playbook

### Purpose and reader

Provide a meaningful, practical learning experience for a learner acquiring
basic competence. The learner follows the tutor's controlled path; the author
is responsible for making that path safe, coherent, and successful.

### Required shape

1. State what the learner will make or accomplish, not what they are guaranteed
   to learn.
2. Declare or provide a controlled starting state and exact prerequisites.
3. Lead through one concrete path in small, logical steps.
4. Produce visible, comprehensible results early and often.
5. State what to expect before or after each consequential action.
6. Point out what the learner should notice so action becomes learning.
7. Finish with a meaningful accomplishment and suggest a safe next step.

### Writing rules

- Use direct instructions and, where natural, a tutor-and-learner “we”.
- Prefer concrete actions and results over abstractions.
- Remove options and alternatives from the main path.
- Minimize explanation to the reason needed to proceed; link to a separate
  explanation for depth.
- Make steps repeatable or reversible where possible.
- Test the complete journey from the declared starting state. Treat a missed
  expected result as a defect in the tutorial, not a reader failure.

### Tutorial check

- Does the learner know what they will accomplish?
- Can a learner with only the declared prerequisites complete every step?
- Does every important action have an observable expected result?
- Is the path single, safe, concrete, and free of distracting choices?
- Does the experience build confidence and familiarity rather than merely
  produce an artifact?

## How-to guide playbook

### Purpose and reader

Help an already-competent practitioner accomplish a specific real-world goal or
solve a real problem. Define the guide around the human project, not around a
tour of a tool's features.

### Required shape

1. Title the page “How to <achieve a specific result>” when that form is natural.
2. State the situation, goal, prerequisites, and important constraints.
3. Give an executable, logically ordered route to the result.
4. Add conditional branches where real-world variation requires judgment.
5. Include safety checks, failure signals, and recovery directions that matter
   to the task.
6. End at a meaningful result and show how to verify it.

### Writing rules

- Assume familiarity with the tools and domain concepts.
- Keep focus on action; link to reference or explanation rather than embedding
  exhaustive options or background discussion.
- Prefer practical usability to completeness. Start and end at meaningful
  points, allowing the user to join the guide to their own work.
- Sequence steps to match the user's activity and thinking, minimizing context
  switching and unresolved mental state.
- Generalize enough for realistic cases, but do not expand an achievable task
  into an open-ended domain such as “build a web application”.

### How-to check

- Is the goal a specific user outcome rather than a product operation?
- Does the guide assume competence instead of teaching basics?
- Can the user adapt the route to realistic variations?
- Are branches, hazards, verification, and recovery included where needed?
- Have digressions, exhaustive reference, and teaching been removed?

## Reference playbook

### Purpose and reader

Provide authoritative facts that a practitioner consults while working. Describe
the machinery accurately, completely for the stated scope, neutrally, and in an
order that makes facts easy to locate.

### Required shape

1. Define the documented object and scope.
2. Mirror the product's logical structure where that helps readers navigate.
3. Use stable, repeated patterns for equivalent objects.
4. State signatures, fields, types, defaults, constraints, behavior, outputs,
   errors, limitations, compatibility, and warnings as applicable.
5. Add concise usage examples when they illuminate facts without becoming a
   task guide.
6. Link to tutorials, how-tos, and explanations for other needs.

### Writing rules

- Describe and only describe; avoid teaching, persuasion, opinion, and extended
  rationale.
- Prefer precision, consistency, and scanability over narrative flair.
- Derive facts from authoritative artifacts or generated sources when possible.
- Treat omissions and ambiguity as defects because users seek truth and
  certainty from reference.

### Reference check

- Is every claim traceable to the product, schema, code, or another authority?
- Can readers predict where equivalent facts will appear?
- Does the organization correspond usefully to the thing described?
- Are facts complete for the declared scope and free of interpretation?
- Are examples illustrative rather than instructional?

## Explanation playbook

### Purpose and reader

Deepen and broaden understanding through reflection. Bound the page around a
topic or a real or imagined “why” question, then illuminate it from useful
perspectives.

### Required shape

1. Name the bounded topic or question.
2. Establish the context and the concepts the reader needs.
3. Connect the topic to related ideas, constraints, history, or consequences.
4. Explain reasons, design decisions, trade-offs, and implications.
5. Consider alternatives, counterexamples, or legitimate perspectives.
6. Close by consolidating the reader's mental model, not by prescribing steps.

### Writing rules

- Permit reasoned opinion and perspective; distinguish them from verified fact.
- Use examples and analogies to clarify connections.
- Prefer discursive prose to procedural steps or exhaustive fact tables.
- Keep the topic deliberately bounded. Move instructions to how-to guides and
  technical descriptions to reference.

### Explanation check

- Does the page answer why, provide context, or make connections?
- Is the topic bounded tightly enough to reach a meaningful conclusion?
- Are reasons, constraints, alternatives, and implications made explicit?
- Are opinions framed as perspectives rather than neutral facts?
- Have action sequences and reference dumps been moved elsewhere?

## Boundary tests

### Tutorial or how-to guide?

Ask whether the reader is studying or working:

| Tutorial | How-to guide |
|---|---|
| Builds basic competence | Applies existing competence |
| Author owns learner success | User owns the real-world outcome |
| Controlled, repeatable setting | Uncontrolled real-world setting |
| One safe path without choices | Branches and alternatives as needed |
| Explicit about basic actions | Assumes familiar, embodied knowledge |
| Concrete case teaches general skill | General guidance solves a particular case |

Do not infer the type from the presence of steps; both modes guide action.

### Reference or explanation?

Ask whether the reader consults it during work or studies it to understand:

| Reference | Explanation |
|---|---|
| Neutral facts | Context and interpretation |
| Product-defined scope | Topic- or question-defined scope |
| Standard, scannable patterns | Discursive connections |
| Answers what | Answers why |
| Consulted while working | Read reflectively, often away from work |

Examples can exist in reference, but develop them into a separate explanation
when they begin exploring reasons, alternatives, or implications.

## Mixed content and information architecture

- Separate substantial mixed-mode content; do not delete a valid user need just
  because it appears in the wrong place.
- Cross-link at the moment the adjacent need could arise. Keep link labels
  explicit about what the destination provides.
- Do not require four top-level sections. In complex products, audience, topic,
  platform, or product boundaries may be the primary navigation axis, with the
  four modes repeated or distributed beneath it.
- Make landing pages human overviews, not unexplained link dumps. Group long
  lists into meaningful, navigable sets.
- Let user needs determine architecture. Product-team ownership or internal
  component boundaries matter only when they also help the reader.
- When remediating existing docs, classify and repair one small unit at a time.
  Do not create empty category structures or delay useful improvements until a
  complete migration is designed.

## Authoring and audit patterns

### New-document brief

Record before drafting:

- Reader and assumed competence
- Reader's current situation: study or work
- Needed content: action or cognition
- Selected mode and desired outcome
- Authoritative sources and freshness requirements
- Scope, prerequisites, risks, and verification method
- Companion content that belongs in another mode

### Existing-document audit

Report each actionable finding as:

| Location | User need | Current mode | Problem | Smallest repair |
|---|---|---|---|---|
| Section or line | Action/cognition + acquisition/application | Observed mode | Concrete mismatch or quality lapse | Move, remove, add, split, rename, reorder, or verify |

Prioritize wrong or unclear user purpose before cosmetic consistency. Preserve
useful content by relocating it to the mode where it can do its job.

## Quality and verification

Diátaxis helps documentation fit user needs and exposes defects, but it does not
guarantee factual quality, visual design, accessibility, or usability.

Verify two layers:

1. **Functional quality:** accuracy, completeness for scope, consistency,
   usefulness, precision, valid examples and links, and maintainability.
2. **Deep quality:** flow, fit to the reader's situation, anticipation of needs,
   navigability, and the overall experience of use.

Functional quality is a prerequisite for deep quality. Use objective checks for
facts and execution; use informed human judgment or representative user
observation for flow and fit.

For runnable documentation:

- Start from the declared prerequisites in a clean or representative
  environment.
- Execute steps exactly as written and compare actual with promised results.
- Test meaningful branches, warnings, rollback, or recovery where applicable.
- Record version and environment assumptions.
- State any unverified behavior plainly.

## Primary sources

- <https://diataxis.fr/start-here/>
- <https://diataxis.fr/tutorials/>
- <https://diataxis.fr/how-to-guides/>
- <https://diataxis.fr/reference/>
- <https://diataxis.fr/explanation/>
- <https://diataxis.fr/compass/>
- <https://diataxis.fr/how-to-use-diataxis/>
- <https://diataxis.fr/foundations/>
- <https://diataxis.fr/map/>
- <https://diataxis.fr/quality/>
- <https://diataxis.fr/tutorials-how-to/>
- <https://diataxis.fr/reference-explanation/>
- <https://diataxis.fr/complex-hierarchies/>
- <https://github.com/evildmp/diataxis-documentation-framework>
