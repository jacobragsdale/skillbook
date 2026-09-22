# Reference

Reference is technical description that a practitioner looks up while working.
It must be accurate, complete for its declared scope, neutral, and laid out so
that facts are easy to find. Users come to reference for certainty, so a gap or
an ambiguity is a defect. Describe, and only describe.

## Required shape

1. Name the object and the scope, for example "All `deploy` subcommands
   and flags as of v3.2."
2. Structure the page to mirror the thing described: one section per command,
   endpoint, class, or config block, in the product's own order or
   alphabetically.
3. Repeat the same pattern for equivalent objects, so readers can predict where
   a fact will be.
4. For each object, give whichever of these apply: signature or syntax, fields
   or parameters, types, defaults, allowed values, constraints, behavior,
   return values or output, errors, side effects, limits, compatibility or
   version added, and deprecations.
5. Add a short example when it shows usage more clearly than prose. Keep the
   example illustrative, not a procedure.
6. Link to how-to guides and explanation pages for other needs.

## Writing rules

- Leave out advice, persuasion, opinion, and rationale. Move "why" to an
  explanation page. Move "how to accomplish" to a how-to guide.
- Spend words on what the name does not reveal. "`timeout`: the timeout"
  tells the reader nothing. "`timeout`: seconds before the request is
  aborted; `0` disables it; default `30`" is reference.
- Generate from the source of truth wherever possible, such as OpenAPI,
  `--help`, docstrings, or schemas. Hand-write only what generation cannot
  capture: cross-object behavior, constraints, and caveats. Generated
  reference is necessary but is not the whole documentation set.
- Use tables for attributes that line up across rows. For objects with long
  descriptions, use repeated heading-and-field blocks instead.
- State constraints as rules: "You must set `region` before `zone`. Never
  set both `token` and `password`."

A dry page is fine: reference that is boring and unmemorable is doing its job.

## Language

- "`sync` accepts the following flags:"
- "Sub-commands are: `init`, `plan`, `apply`."
- "You must use a. You must not apply b unless c."
- "Returns `null` if the key does not exist."

## Title

Name the object: "`deploy` command", "Configuration file", "Events API". Do not
use a task title or a question.

## Check

- Can every claim be traced to code, a schema, `--help`, or another authority?
- Is every item within the declared scope covered?
- Do equivalent objects use an identical pattern?
- Does the page's organization mirror the product's?
- Are there any recommendations, justifications, or task sequences that
  should move out?

## Skeleton

````markdown
# `<command>` command

`<command>` <does what, in one neutral sentence>.

```text
<command> [OPTIONS] <ARG>
```

## Arguments

| Name | Type | Required | Description |
|---|---|---|---|
| `ARG` | path | yes | <What it is, constraints.> |

## Options

| Flag | Type | Default | Description |
|---|---|---|---|
| `--port` | int | `8080` | <Behavior, allowed range.> |

## Exit status

| Code | Meaning |
|---|---|
| `0` | <…> |

## Example

```sh
<command> --port 9000 ./site
```

Related: <how-to link>, <explanation link>.
````
