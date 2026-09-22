# Style for technical docs

These are the defaults for when the repository has no conventions of its own.
Existing local style always wins. The rules are distilled from the Google and
Microsoft developer style guides, the GitLab docs style guide, Wikipedia's
catalogue of AI-writing tells, and technical writers' critiques of generated
docs (see Sources). They were reviewed 2026-09-22.

## Contents

- Tells of generated prose, and their fixes
- Voice and grammar
- Headings, lists, tables, and callouts
- Code, commands, and placeholders
- Links
- Global audience and accessibility
- Testing docs as code
- Docs that agents also read
- Sources

## Tells of generated prose, and their fixes

Readers recognize these patterns and stop trusting the page. Search for them in
the cut pass.

| Tell | Fix |
|---|---|
| Announcing the page: "In this guide, we'll explore…", "This section describes…" | Start with the content. |
| A first sentence that restates the heading | Make it add a fact, the goal, or the answer. |
| A closing "Summary", "Conclusion", or "Key takeaways" that repeats the page | Delete it, or replace it with next-step links. |
| Significance padding: "plays a crucial role", "it's important to note", "it's worth mentioning" | State the fact. |
| Marketing words: seamless, powerful, robust, cutting-edge, leverage, empower | Say what it does, with numbers if you have them. |
| Ease words: simply, just, easily, obviously, of course | Delete them. They insult a reader who is stuck. |
| Dodging "is": "serves as", "stands as", "boasts" | Use "is" or "has". |
| "Not just X, but Y", "It's not X, it's Y" | State Y. |
| Reflexive groups of three | List what actually exists. |
| A tail of "-ing" words: "…, ensuring reliability and highlighting flexibility" | Cut the tail, or make it a checked claim. |
| Hedging with no real uncertainty: "may potentially", "generally tends to" | Commit, or name the specific condition. |
| Vague attribution: "experts recommend", "it is widely considered" | Cite the source, or cut the claim. |
| Time-bound words: new, now, currently, recently, "as of this writing" | Write timelessly, or give the version. |
| Promised future features | Link to the tracking issue, or leave it out. |
| Bold used for emphasis, emoji, horizontal rules between sections | Remove them. Bold is for UI labels. |
| Em dashes in every paragraph | Use commas, parentheses, or two sentences. |
| Headings over a single paragraph, or a heading for every thought | Merge them into prose under a broader heading. |
| Bullet fragments where the reasoning should connect | Write sentences in a paragraph. |
| Tables of items that have only one attribute | Use a list or a sentence. |
| Invented flags, options, or APIs, or bugs documented as features | Check against source; mark `TODO: verify`. |
| `foo`/`bar`/`example.com` examples in a real codebase | Use real-shaped values from the project. |
| Documenting what the name already says ("`getName()` gets the name") | Document constraints, side effects, and failure modes. |
| Unfilled template text | Fill it in, or delete the section. |

## Voice and grammar

- Address the reader as "you". Use the imperative for instructions.
- Use active voice and present tense: "The server returns 404", not "A 404
  will be returned".
- Use contractions if the local docs do.
- Put the verb early. Cut unneeded "you can", "there is", and "there are".
- Prefer plain words:
  - "lets you" over "allows you to"
  - "to" over "in order to"
  - "for example" over "e.g."
  - "earlier" or "later" over "above" or "below"
- Avoid "please", "etc.", and Latin abbreviations.
- Use one term per concept, matching the product's UI and code. Define an
  abbreviation at its first use on each page.
- Replace a pronoun with its noun when the noun is more than a sentence away.

## Headings, lists, tables, and callouts

- Use sentence-case headings. Do not skip levels. Do not stack a heading
  directly under another heading with nothing between them.
- Put a heading's keyword in its first two words. Readers scan the left edge.
- Use numbered lists for sequences, and bullets for three or more parallel
  items with parallel grammar. Introduce a list with a complete sentence or
  with "To <goal>:".
- Use tables when each row has two or more attributes. Keep cell text short;
  a cell that needs a paragraph belongs in a heading-and-field block.
- Callouts (note, warning, tip): at most one per screen. A warning is for data
  loss, security exposure, or irreversible actions. Never put a required step
  or prerequisite in a callout.

## Code, commands, and placeholders

- Put every command, path, flag, key, and literal value in code formatting.
- Tag every fence with its language (`sh`, `python`, `yaml`, `text` for
  output).
- Put the command and its output in separate blocks. Show output only when the
  reader needs something from it.
- Don't show a prompt symbol (`$`) unless the local docs do. It breaks
  copy-paste.
- Name placeholders in `UPPER_SNAKE_CASE`, without a `MY_` or `YOUR_` prefix.
  Define them right after the block, with a "Replace the following:" list.
- Mark omitted code with a comment in the block's own language. A bare "…"
  won't parse.
- Examples must run as shown. Keep them minimal but complete: include imports
  and setup the reader cannot guess.

## Links

- Write link text that makes sense out of context. Use the destination's
  title or the task it covers. Never use "click here", "this page", or a bare
  URL.
- Introduce cross-references with "For more information, see <link>". Link
  each target once per page, at its first relevant mention.
- Link to the specific section anchor, not just the top of a long page.

## Global audience and accessibility

- Write short sentences. Leave out idioms, humor, and cultural references.
- Stack no more than two nouns as modifiers.
- Keep the optional "that" where it makes the grammar easier to follow.
- Write dates unambiguously (`2026-09-22` or "22 September 2026").
- Give every image alt text that conveys its information. Never let an image
  or screenshot be the only place a fact lives.
- Never rely on color or position alone ("the green button", "the box on the
  right").

## Testing docs as code

Choose these checks in this order: run what the repo already uses, then add the
smallest check that proves the change.

- **Code samples:**
  - `doctest` for Python docstrings.
  - `pytest-markdown-docs` or `mktestdocs` for Python fences in Markdown.
  - The project's own test runner for any other language.
- **Links:** `lychee` checks URLs and anchors across Markdown and HTML.
- **Prose:** Vale, configured with `.vale.ini` plus the Google or Microsoft
  package and a project vocabulary. Run it only if the repository already
  uses it.
- **Freshness:** Keep docs next to the code they describe, and update them in
  the same change. A wrong doc is worse than a missing one.

## Docs that agents also read

- Self-contained sections with explicit subjects serve both retrieval and
  humans. This is the "readers land mid-page" rule in `SKILL.md`.
- `llms.txt` at the site root is a Markdown index: an H1, a one-paragraph
  summary in a blockquote, then H2 sections that list links with one-line
  descriptions. Add it only when asked, or when the site already publishes
  one.
- `AGENTS.md`, `CLAUDE.md`, and similar files are how-to and reference for a
  competent reader: build, test, and style commands, plus project rules.
  Never write them as a tutorial.

## Sources

- https://developers.google.com/style/highlights
- https://developers.google.com/style/procedures
- https://developers.google.com/style/placeholders
- https://developers.google.com/style/code-samples
- https://developers.google.com/style/link-text
- https://developers.google.com/style/notices
- https://developers.google.com/tech-writing/two/llms
- https://learn.microsoft.com/en-us/style-guide/top-10-tips-style-voice
- https://docs.gitlab.com/development/documentation/styleguide/
- https://docs.gitlab.com/development/documentation/topic_types/
- https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing
- https://passo.uno/whats-wrong-ai-generated-docs/
- https://www.smcmaster.com/blog/impressive-but-wrong-the-hidden-risk-of-llm-generated-documentation
- https://www.nngroup.com/articles/first-2-words-a-signal-for-scanning/
- https://www.writethedocs.org/guide/writing/docs-principles/
- https://llmstxt.org/
- https://agents.md/
