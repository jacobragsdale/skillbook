# Explanation

Explanation deepens and broadens understanding. It answers "why", gives
context, and connects the topic to other ideas. It is read reflectively, away
from the task. The test: someone could read it in the bath. Scope each page to
one topic, or to one real or implied "why" question.

## Required shape

1. Name the topic or question. The title should read naturally after an
   implied "About…".
2. Establish the context and the concepts the reader needs.
3. Give the reasons: design decisions, constraints, history, and trade-offs.
4. Connect the topic to neighboring ideas and consequences.
5. Weigh alternatives, counterexamples, or competing views where they exist.
6. Close by consolidating the reader's mental model, not with steps to follow.

## Writing rules

- Write in paragraphs. Use a list only for real parallel items such as
  alternatives compared on the same axis. An explanation written as bullets
  has usually dropped the reasoning that connects them.
- Opinion and perspective belong here. Frame them as such and keep them
  distinct from verified fact.
- Use examples and analogies when they clarify a connection. Do not use them
  as decoration.
- Keep the scope bounded so that the page reaches a conclusion. When it drifts
  into instructions, move those to a how-to guide. When it drifts into fact
  tables, move those to reference.

## Language

- "The reason for x is that, historically, y…"
- "W is better than z, because…"
- "An x in system y is analogous to a w in system z. However…"
- "Some users prefer w (because z). This can be a good approach, but…"
- "X interacts with y as follows…"

## Title

Name the topic or question so that it reads well after "About": "The worker
queue", "Why sessions are stateless", "Consistency and replication". Sections
of explanation pages are commonly called "Background", "Concepts",
"Discussion", or "Topics". Follow the local name.

## Check

- Does the page answer "why", give context, or make connections?
- Is the topic bounded tightly enough to reach a conclusion?
- Are the reasons, constraints, alternatives, and consequences explicit?
- Is opinion framed as perspective?
- Have steps and fact dumps been moved out and linked?

## Skeleton

````markdown
# <Topic or question>

<The short answer or central idea, in one paragraph.>

## <The context or constraint that drives it>

<Paragraphs.>

## <The trade-off or alternative>

<Paragraphs weighing options.>

## <Consequences for the reader>

<What this means in practice. Links to the how-to guides and reference that
apply it.>
````
