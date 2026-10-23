---
name: grilling
description: "Grill the user relentlessly on a plan, design, or decision, a round at a time. Use when the user says grill me, wants a plan stress-tested, or wants to be interviewed before building \u2014 even if they only say poke holes in this."
license: "MIT, adapted from mattpocock/skills. See LICENSE.txt"
---

# Grilling

Interview the user relentlessly until you reach a shared understanding. Map
this as a **design tree**: every decision branches into the decisions that
hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose
prerequisites are already settled: the questions you can ask _now_ without
guessing at answers you haven't heard yet. Ask the whole frontier in one
round: number each question and give your recommended answer. Then wait for
the user's answers before the next round.

Format a round like so:

```
❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>

---

❓ **Q2** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>
```

Word each question so "yes" accepts your recommended answer.

Each round the user answers reshapes the tree: settled decisions push the
frontier outward and unblock questions that depended on them. Recompute the
frontier and ask the next round. A question whose answer depends on another
question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs
a fact from the environment (code, files, tools, services), look it up
instead of asking, in a subagent when the harness has one so the round
doesn't wait on it. A running lookup is an unsettled prerequisite: only the
questions downstream of it wait; ask the rest of the frontier now. The
_decisions_ are the user's: put each to them and wait.

Some decisions need knowledge the user doesn't hold: a business owner's rule,
another team's system, a vendor's limit. When the user answers "I don't know"
or "I'd have to ask X", mark that branch **parked**, note who can answer it,
and keep grilling the rest of the tree. At the end, offer the
`to-questionnaire` skill for the parked questions, one questionnaire per
person.

The session is done when the frontier is empty: every branch visited or
parked, nothing left silently assumed. Do not act on it until the user
confirms you have reached a shared understanding.
