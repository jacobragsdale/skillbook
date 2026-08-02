# Mermaid diagram design for engineering managers

This reference turns system facts into views that help engineering managers
explain architecture, delivery, behavior, ownership, data, and decisions. It was
reviewed against Mermaid 11.16.0 and the current Diátaxis guidance on 2026-08-02.

## Contents

- Fit the diagram to the documentation need
- Establish truth and scope
- Select the diagram type
- Compose the view
- Write for scanning
- Use theme and color deliberately
- Design for accessibility
- Inspect the rendered result
- Freshness and primary sources

## Fit the diagram to the documentation need

Choose the reader's need before choosing Mermaid syntax:

| Need | Diagram's job | Include | Exclude |
|---|---|---|---|
| Tutorial | Help a learner complete one controlled path | Starting point, ordered actions, visible results | Alternative branches and exhaustive internals |
| How-to | Help a practitioner achieve a goal | Decisions, ownership, hazards, recovery, final check | Introductory teaching and unrelated architecture |
| Reference | Let a practitioner consult exact facts | Boundaries, contracts, cardinality, states, precise labels | Narrative rationale and speculative behavior |
| Explanation | Build a useful mental model | Selected relationships, constraints, trade-offs, consequences | Every implementation detail and step-by-step instructions |

Keep each diagram loyal to one primary need. A diagram can support a page in any
mode; do not create one diagram for each mode by default.

## Establish truth and scope

Write a one-line brief before drawing:

`For <audience>, show <scope> so they can answer <one question>, using <sources>.`

Then inventory only facts needed for that question:

- components or actors;
- relationships and their direction;
- ordering, branching, or concurrency;
- ownership, deployment, or trust boundaries;
- data stores, contracts, and cardinality;
- states, triggers, and terminal outcomes;
- dates, dependencies, status, or quantitative values.

Trace facts to code, schemas, infrastructure, product behavior, or maintained
documentation. If a relationship is inferred, label it as inferred in nearby
prose or omit it. Visual polish must never turn uncertainty into apparent fact.

## Select the diagram type

Use this table from top to bottom. If two rows fit, choose the first one that
answers the question without losing essential semantics.

| Viewer question | Type | Declaration | Engineering-manager use |
|---|---|---|---|
| What happens next, and where does it branch? | Flowchart | `flowchart LR` or `TB` | Operating process, decision tree, data flow, portable architecture fallback |
| Who calls whom, in what order, and where does failure return? | Sequence | `sequenceDiagram` | Request lifecycle, incident path, integration contract |
| Who uses the system, and which systems or containers exist? | C4 | `C4Context` or `C4Container` | Context and container views for architecture communication |
| Which cloud or CI/CD resources connect through which ports? | Architecture | `architecture-beta` | Deployment and infrastructure topology |
| Which states exist and what events move between them? | State | `stateDiagram-v2` | Order, job, release, or incident lifecycle |
| What data entities exist and how are they related? | Entity relationship | `erDiagram` | Data ownership, domain shape, schema review |
| What work spans dates, depends on other work, or forms the critical path? | Gantt | `gantt` | Delivery plan, migration, release train |
| What milestones happened or are expected in chronological order? | Timeline | `timeline` | Roadmap or incident chronology without task duration |
| What does a user do, who participates, and where is the experience weak? | User journey | `journey` | Customer or operator experience across stages |
| How do options compare on two decision criteria? | Quadrant | `quadrantChart` | Prioritization, risk, build-versus-buy discussion |

Decision rules:

- Use a flowchart instead of C4 when portability matters more than formal C4
  semantics or the host's Mermaid version is unknown.
- Use sequence for one important runtime scenario; use C4 or flowchart for the
  static landscape. Do not combine both questions in one crowded view.
- Use architecture only for resource topology. It is not a general replacement
  for C4 or flowcharts.
- Use state for allowed transitions, not for a one-time procedural path.
- Use Gantt for duration and dependency; use timeline for chronology alone.
- Use a real charting tool instead of quadrant, journey, or Gantt when the user
  needs statistical analysis, interactive exploration, or live operational data.

C4 remains experimental, `architecture-beta` is version-sensitive, and timeline
syntax is documented as experimental in Mermaid 11.16.0. Confirm the target
renderer before choosing them.

## Compose the view

1. Place the main story on one obvious reading path.
2. Put external actors or inputs at the edge; keep internal elements inside a
   labeled boundary.
3. Order declarations to keep related elements adjacent. Mermaid layout is
   automatic, but source order still influences crossings and emphasis.
4. Show the happy path first, then the failure or alternate path closest to the
   decision that creates it.
5. Group by a meaning the reader needs: owner, trust zone, deployment unit,
   lifecycle stage, or domain. Do not group by visual convenience alone.
6. Split when labels must shrink, edges repeatedly cross, an overview exposes
   implementation details, or the title needs the word "and" to describe two
   independent questions.

Use progressive disclosure for complex systems:

- context: people, external systems, and the system boundary;
- container or service view: deployable units and data stores;
- scenario: one runtime interaction or failure path;
- detail: state, schema, or delivery plan for one bounded area.

Link the views in surrounding documentation instead of forcing every level into
one canvas.

## Write for scanning

- Title the conclusion or scope: “Checkout authorization and failure return,”
  not “Sequence diagram.”
- Use recognizable product and team terminology. Expand uncommon acronyms once.
- Name entities with nouns and edges with verbs. “API → Queue: publishes order”
  is clearer than “API → Queue.”
- Keep node labels short enough to scan. Put detailed rules in nearby prose,
  notes, or linked reference material.
- Give edge direction one meaning within a view. If arrows mean both calls and
  ownership, split the view or distinguish them with labels and a legend.
- Add a legend only for conventions a first-time viewer cannot infer.

## Use theme and color deliberately

Fix information structure before styling.

- Preserve the host theme for embedded documentation unless local conventions
  require a fixed theme.
- For a standalone artifact on a confirmed Mermaid 11.16 renderer, test the
  built-in `neo` look and `redux` or `neutral` theme before defining custom
  colors. Frontmatter configuration is preferred; directives are deprecated.
- Use one neutral base, one primary accent, and semantic warning or failure
  colors only when needed. Do not assign a unique color to every service.
- Repeat semantics across diagrams: external, owned, data, warning, and failure
  must not change color casually.
- Check light and dark destinations separately when the artifact will appear in
  both. Use text, shape, line style, or labels in addition to color.

## Design for accessibility

- Add a visible title and surrounding prose that states why the diagram matters.
- Use `accTitle` for a short accessible name and `accDescr` for the main reading
  order or conclusion when the selected diagram type and renderer accept them.
- Do not repeat every visible label in `accDescr`; provide an equivalent mental
  model.
- Preserve readable text size and contrast at the intended embed width.
- Never encode success, failure, ownership, or risk with color alone.

## Inspect the rendered result

Syntax validation is necessary but insufficient. Inspect the actual SVG or PNG
at the target display size and ask:

- Can a new viewer state the diagram's question and answer within a few seconds?
- Is the first reading path obvious?
- Are labels, arrowheads, cardinalities, dates, and boundary titles legible?
- Are any nodes clipped, compressed, or pushed far from related elements?
- Do crossings or bidirectional edges create a false relationship?
- Does a failure, external dependency, or terminal state disappear visually?
- Is the aspect ratio appropriate for the page, slide, or image?
- Does the view still communicate in grayscale and without its surrounding
  author present?

Repair content and composition first: shorten a label, reorder declarations,
change direction, move a boundary, or split the view. Re-render after each
change. Add styling only when those repairs cannot express the distinction.

## Freshness and primary sources

The target renderer is authoritative for supported syntax. This synthesis was
verified against Mermaid 11.16.0; recheck current docs when a different version
is installed or a declaration fails.

- <https://mermaid.js.org/intro/syntax-reference.html>
- <https://mermaid.js.org/config/configuration.html>
- <https://mermaid.js.org/config/theming.html>
- <https://mermaid.js.org/config/accessibility.html>
- <https://mermaid.js.org/config/layouts.html>
- <https://mermaid.js.org/config/mermaidCLI.html>
- <https://github.com/mermaid-js/mermaid/releases/tag/mermaid%4011.16.0>
- <https://diataxis.fr/>
