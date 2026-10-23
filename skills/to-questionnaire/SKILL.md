---
name: to-questionnaire
description: "Turn questions the user can't answer into a questionnaire for someone who can. Use when a decision needs another person's knowledge (a business owner, another team, a vendor) \u2014 even if they only say they'll have to ask someone."
license: "MIT, adapted from mattpocock/skills. See LICENSE.txt"
---

# To questionnaire

Turn something the user can't answer alone into a **questionnaire**: a
Markdown document they hand to one person to fill in async, or fill out
together in a meeting. The recipient holds knowledge the user lacks; the
questionnaire pulls it out of them.

**Grill the send, not the subject.** Interview the user only about the
_send_, which they can always answer: who it goes to, and what they need
back. The questions in the document target the **gap** between what the
recipient knows and what the user needs.

## Workflow

1. **Who is it going to?** Ask, in one exchange, the recipient's role,
   expertise, and relationship to the user. This fixes the questionnaire's
   tone and how much context it must carry. Done when you know who the
   recipient is and what they know that the user doesn't.
2. **What do you need back?** Ask, in one exchange, the specific decisions
   or facts the user can't resolve alone and needs from this person. Done
   when you have a concrete list of what the user must walk away able to do
   or decide.

   Coming from `grilling`, the parked questions are this list and the person
   noted for them is step 1's answer: show both back for a yes instead of
   asking again. Write one questionnaire per recipient.
3. **Write the questionnaire.** Draft questions aimed at the gap from steps
   1–2, following the template below. Name the file
   `questionnaire-<slug>.md` (slug from the topic). Write it to the current
   directory, unless that directory is inside a git repository: then write it
   to the OS temp directory (`$TMPDIR`, else `/tmp`) so the repo stays clean.
   Report the absolute path. Done when the file exists and every item the
   user named in step 2 is covered by a question.

The document leaves the user's hands. Put no credentials in it, and no client
or account data the recipient doesn't already hold.

## Document structure

Frame the document as a **discovery questionnaire**: the user lacks context,
the recipient holds it. Order questions most-important-first, since async
means you may only get one pass, and group them under `##` headings by theme
once there are more than a handful. Write it using the template below.

<questionnaire-template>

# <Questionnaire title>

**Purpose:** why this questionnaire exists and the decision riding on it.

**From:** <the user>, **To:** <the recipient>, **How your answers will be used:** <where they go>

## Context

One paragraph orienting a recipient who wasn't in the user's head. Enough to answer well, not a page.

## How to answer

Deadline and rough effort. Partial answers and "I don't know" are useful: flag anything you're unsure of rather than skipping it.

## <Theme heading>

One `##` section per theme. Under each, its questions, most-important-first. Every question is one idea, never compound, with an answer stub directly beneath, and a one-line _why this matters_ only where the question could be misread or invite a throwaway answer.

<question-example>
### What load is the system expected to handle at launch?

_Why this matters: it decides whether we provision for burst traffic now or defer it._

>
</question-example>

## Anything else?

A closing catch-all: anything we didn't ask that we should know?

</questionnaire-template>
