---
name: typescript-standards
description: "Enforce strict TypeScript, Angular, ESLint, and runtime validation. Use when coding, reviewing, or configuring TypeScript, Angular, ESLint, templates, APIs, async code, or dependencies — even if unrequested. Not for test design."
---

# TypeScript house standard

Apply these rules to all first-party TypeScript and Angular code. Optimize for
explicit guarantees, then choose the simplest implementation that preserves
them.

## Inspect before changing tools

- Read `package.json`, the lockfile, Angular workspace configuration, every
  active `tsconfig`, and the existing ESLint and formatter configuration.
- Keep the repository's package manager and lockfile. Do not introduce a second
  package manager or upgrade Angular, TypeScript, Node.js, or the module target
  incidentally.
- Check the installed Angular compatibility range before changing TypeScript.
  Match the `angular-eslint` major version to Angular's major version.
- ESLint 10 accepts only flat config. Migrate a legacy TSLint or `.eslintrc`
  Angular project with the version-matched `angular-eslint` schematic rather
  than running both linters.
- TypeScript 7 is npm's `latest`, but `typescript-eslint` 8 and Angular 22
  support only `<6.1`. Install `typescript@~6.0` in a new setup; bare
  `typescript` breaks typed linting and the Angular compiler.
- Treat the bundled lint files as current flat-config baselines. If a
  version-matched older plugin does not expose one of their presets or rules,
  retain its generated compatible config, record the missing guarantee, and
  add it after a supported framework upgrade; do not upgrade Angular merely to
  make a rule name resolve.

## Types and state

- Enable TypeScript `strict` plus every additional check in
  `assets/tsconfig.strict.json`. Do not weaken the inherited config.
- Rely on inference only for locals whose resulting type remains precise.
  Explicitly type exported boundaries and function returns. Do not require
  redundant annotations on obvious local constants.
- Do not let `any` escape a dependency adapter. Receive uncertain values as
  `unknown`, then narrow with a type guard or runtime schema.
- Do not use `as`, angle-bracket assertions, postfix `!`, `@ts-ignore`, or
  double assertions to manufacture facts. If a library's types are wrong, add
  a typed adapter or an upstream-compatible declaration and give any necessary
  suppression an adjacent reason.
- Prefer `readonly` properties, readonly collections, immutable values, and
  discriminated unions. Represent loading, success, empty, and failure as
  complete tagged states instead of nullable partial objects.
- Keep type-checker fixes in the type domain. Do not add runtime branches or
  assertions solely to silence a diagnostic.

## Validate boundaries

- Treat HTTP and WebSocket data, `postMessage`, storage, parsed JSON, URL and
  route parameters, DOM attributes, runtime configuration, and untyped
  dependencies as I/O boundaries.
- Parse boundary input from `unknown` before domain or UI code consumes it.
  Reuse the project's schema library; when none exists, use Zod 4 and
  `z.strictObject` so unknown keys fail rather than disappear silently. Derive
  the TypeScript type from the schema instead of maintaining two definitions.
- Do not treat `HttpClient.get<T>()`, `response.json() as T`, `JSON.parse()`,
  generated API types, or a successful compile as runtime validation.
- Validate outbound payloads before another system receives them when malformed
  output can cause loss, corruption, or an irreversible action.
- Schema validation does not establish freshness, ordering, authorization,
  referential integrity, reconciliation, or trading risk limits. Enforce those
  invariants explicitly before acting.

## Angular

- Merge `assets/tsconfig.angular-strict.json` into Angular projects. Keep strict
  templates, injection parameters, input access modifiers, host bindings, and
  extended diagnostics at error severity.
- Enable `strictStandalone` only for a new or already fully standalone
  workspace. Do not make an NgModule-to-standalone migration incidental to
  unrelated work.
- Use the Angular ESLint asset so external and inline templates receive the
  same correctness and accessibility checks.
- Keep asynchronous work out of lifecycle method signatures because Angular
  does not await them. Start it from an explicit task with handled failure, or
  model it as an Observable or signal.
- Move calculations and allocations out of templates into typed computed
  values. Do not escape template checking with `$any()` or `!`.
- Keep the asset's OnPush, pure-pipe, signal, subscription-lifetime, template
  complexity, and image checks enabled. Suppress a rule only for a concrete
  framework limitation and state the reason beside the smallest possible
  scope.

## Tools

- For a TypeScript-only repository, copy
  `assets/eslint/typescript/eslint.config.mjs`. For Angular, copy
  `assets/eslint/angular/eslint.config.mjs`. Copy
  `assets/prettier.config.mjs` in either case; do not retype these files.
- Merge `assets/tsconfig.strict.json` into the root compiler configuration
  without replacing project-specific `target`, `module`, `lib`, paths, or emit
  settings. Angular projects also merge the Angular compiler asset.
- Install `eslint`, `@eslint/js`, `typescript-eslint`, `prettier`, and
  `eslint-config-prettier` as development dependencies with the existing
  package manager. Angular projects also install the version-matched
  `angular-eslint`; prefer its schematic when adding lint support.
- Run Prettier separately from ESLint. Keep width 200, remove trailing commas,
  and collapse object literals that fit rather than preserving comma-driven
  line breaks.
- Make typecheck, lint, format-check, and build each one package script with no
  prerequisite shell state. Run the same scripts in CI with a frozen lockfile.
- Require zero compiler, Angular compiler, ESLint, and formatter diagnostics.
  Keep unused suppression reporting enabled.

## Brownfield adoption

- Fix owned code instead of disabling a preset or converting errors to
  warnings. Exclude generated and vendored files rather than weakening checks
  for first-party code.
- When the full change is too large, stop and offer a checked-in, measurable
  baseline only when the user explicitly chooses staged adoption. New and
  changed files still meet the full standard, and the baseline may only shrink.
- Keep typed linting enabled. If performance is material, measure ESLint timing,
  correct `tsconfig` scope and duplicate program creation, and cache CI runs
  before removing type-aware rules.

## Verification

Before finishing TypeScript work, use the repository's package-manager
equivalents to run:

```text
frozen-lockfile install
tsc --noEmit                  # non-Angular TypeScript projects
ng build                     # Angular compiler and template checking
eslint . --max-warnings 0
prettier . --check
project tests
production build
```

Run every applicable command. A TypeScript-only project does not run `ng
build`; an Angular project does not treat plain `tsc` as a substitute for the
Angular compiler. After dependency changes, verify from a clean dependency
install and commit the updated lockfile.

## Example

Given an Angular service that trusts `http.get<Quote>()`, request `unknown` and
parse it:

```typescript
const quoteSchema = z
  .strictObject({
    symbol: z.string().min(1),
    priceTicks: z.number().int(),
    asOf: z.iso.datetime({ offset: true })
  })
  .readonly()

type Quote = z.infer<typeof quoteSchema>

public loadQuote(symbol: string): Observable<Quote> {
  return this.http
    .get<unknown>("/api/quote", { params: { symbol } })
    .pipe(map((payload) => quoteSchema.parse(payload)))
}
```

The generic describes the value only after parsing; extra fields, wrong types,
and invalid timestamps fail at ingress.

## Bundled resources

- `assets/eslint/typescript/eslint.config.mjs` — copy for TypeScript projects.
- `assets/eslint/angular/eslint.config.mjs` — copy for Angular projects.
- `assets/tsconfig.strict.json` — merge into every TypeScript compiler config.
- `assets/tsconfig.angular-strict.json` — merge into Angular compiler options.
- `assets/prettier.config.mjs` — copy to apply the house formatter choices.
