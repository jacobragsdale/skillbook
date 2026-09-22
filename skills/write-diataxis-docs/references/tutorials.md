# Tutorials

A tutorial is a lesson. It gives a learner a meaningful, practical experience
of success with the product, and in doing so builds the basic competence and
confidence they need before they can work on their own. The author owns the
learner's success: if a step fails for someone who has only the declared
prerequisites, the tutorial is broken.

## Required shape

1. Say what the learner will make or do. Do not promise what they will learn.
   "In this tutorial, we will build…" is right. "In this tutorial you will
   learn…" presumes an outcome the author cannot guarantee.
2. Declare a controlled starting state and exact prerequisites, or provide
   them yourself, for example as a sample project or a container.
3. Lead through one concrete path in small steps, each producing a visible
   result. Get the learner to a first result early.
4. Before any consequential action, say what should happen. After it, show
   what the learner should see.
5. Point out what to notice, so that the action becomes learning.
6. End on the accomplishment, and link to where the learner can go next.

## Don't try to teach

The main discipline in a tutorial is resisting four temptations, each of which
feels helpful and each of which pulls the learner out of the experience:

- **Abstraction:** Show one concrete case. Do not generalize.
- **Explanation:** Give no more reason than the learner needs to keep going.
  "We're using HTTPS because it's more secure" is enough. Link to an
  explanation page for the rest.
- **Choices:** Give one path. Leave out alternatives, options, and "you could
  also".
- **Information:** Skip anything the learner does not need for the next step,
  even if it is true and relevant.

Do tell the learner the signs of going wrong: "If the output doesn't show
`Listening on :8080`, you probably skipped the `--port` flag in step 3." Warn
them before output that would otherwise alarm them, such as a wall of
dependency warnings.

## Language

- "In this tutorial, we will create…"
- "First, do x. Now, do y. Now that you have done y, do z."
- "We must always do x before we do y because…" (one clause, then move on)
- "The output should look something like this:"
- "Notice that… Remember that… Let's check…"
- "You have built a…" (at the end, name what they made)

The tutor-and-learner "we" belongs here and nowhere else.

**Title:** name what the learner builds or does ("Deploy your first
service"), not "Introduction to…" or a bare feature name.

## Check

- Can someone with only the declared prerequisites finish every step? Run the
  whole tutorial to confirm.
- Does every consequential action have an expected result the learner can
  see?
- Is the path free of choices, generalizations, and optional detours?
- Is every explanation cut to the minimum and linked out?
- Does the page end on an accomplishment rather than a summary?

## Skeleton

````markdown
# Build <thing>

In this tutorial, we will build <thing> that <does something visible>.

Before you start, you need <exact prerequisites, with versions>.

## Create <first piece>

<Instruction.>

```sh
<command>
```

You should see:

```text
<real output>
```

Notice that <the thing worth noticing>.

## <Next concrete step>

…

## Next steps

You have built <thing>. To <real-world goal>, see <how-to link>. To
understand <concept>, read <explanation link>.
````
