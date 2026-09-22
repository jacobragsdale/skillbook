# How-to guides

A how-to guide helps a competent user achieve a specific real-world goal or
solve a real problem. The user owns the outcome and brings their own context.
The guide gives a reliable route and trusts the user's judgment. It is
organized around what the user is trying to get done, not around a tour of the
product's features.

## Required shape

1. State the goal, and the situation it applies to, in the first sentence or
   two.
2. List prerequisites: permissions or roles first, then tools, versions, and
   required state.
3. Give the steps in the order the user will think about and perform them,
   minimizing context switches.
4. Branch where real situations differ: "If you use PostgreSQL, do x. If you
   use SQLite, skip to step 5."
5. After a step that can fail badly, say what failure looks like and how to
   recover (house rule).
6. End at the result, with a way to confirm it worked.

## Not just a procedure

A how-to guide can fork, overlap other guides, and have more than one entry or
exit point. It can cover basic procedures: "basic" versus "advanced" is not what
separates it from a tutorial. Leave out what any competent user already knows,
such as how to open a terminal or what a commit is. Keep the task achievable.
"How to add OAuth login" is a guide. "How to build a web application" is a
domain. Put option lists in reference and background in explanation, and link
to them.

## Procedure mechanics

- Put the condition or location before the action: "If the build fails,
  run…"; "In **Settings > Tokens**, select **Create**."
- Give one action per numbered step. Put that step's visible result, if there
  is one, in the same step.
- Document the primary method. Mention another method only when readers
  really split between them.
- A single-step procedure is a sentence or a bullet, not a numbered list.
- Mark optional steps with "Optional:" at the start.
- Introduce the steps with "To <goal>:". Do not add an "Overview" heading.

## Troubleshooting guides

Troubleshooting is a how-to guide whose goal is getting a failure fixed. Title
it with the symptom or the exact error text, so that readers pasting the error
into search can find it. Structure the body as:

1. Symptom: what the user sees, with the exact message.
2. Cause: why it happens, in one or two sentences.
3. Resolution: numbered steps. Label a temporary workaround as a workaround.

Put a catalogue of error codes in reference and link to it.

## Language

- "This guide shows you how to…"
- "If you want x, do y. To achieve w, do z."
- "Refer to the x reference for a full list of options."

**Title:** state the goal, such as "How to rotate the signing key". A gerund
with no goal ("Rotating keys") is weak, and a bare noun ("Signing keys") is
worst. Drop "How to" only when the section already implies it.

## Check

- Is the goal a real user outcome rather than a product operation?
- Does the guide assume competence instead of teaching basics?
- Can the user adapt the steps to realistic variations?
- Are hazards, verification, and recovery included where a step can fail?
- Have teaching, option dumps, and background been moved out and linked?

## Skeleton

````markdown
# How to <achieve goal>

<One or two sentences: the goal and when you'd want it.>

Prerequisites:

- <Role or permission>
- <Tool and version>

To <achieve goal>:

1. <Action>.
2. <If condition, action.>

   <Expected result or failure signal.>

3. <Action>.

To confirm it worked, <check>.

For all options, see <reference link>. For why <x>, see <explanation link>.
````
