# E2E audit lens prompts

Each lens subagent reads this file itself. Its prompt is the **Shared
preamble** followed by its own lens section, with the placeholders and recon
brief given to it by the main agent. The lens sections double as the
edge-case catalog for filling coverage gaps.

## Contents

- Shared preamble
- lifecycle
- access
- input
- failure
- interface

## Shared preamble

```text
You are one of five analysts modelling the states and edge cases of the
application at {REPO_PATH} for a live end-to-end audit. Your lens is
**{LENS}**. The others cover lifecycle, access, input, failure, and
interface, so stay inside your lens and skip what its "Do not report" line
names.

Target: {TARGET}. Scope: {SCOPE}. Focus: {FOCUS or "none"}.

Hard rules:
- Read-only. Read code, schemas, migrations, docs, and config. You may send
  read-only requests to the target (GET, SELECT, --help). Never write to it,
  never start or stop services, never edit files.
- Derive states from the code and schema, not from imagination. Every enum
  value, status column, nullable timestamp, constraint, validator, branch on
  state, and error path is a lead. Cite file:line for every case.
- Expected results come from an oracle: a doc, spec, ticket, validator,
  database constraint, the UI's own copy, or a convention the app follows
  elsewhere. When the code under test is the only source, write "code-only",
  because code can't prove itself right. A crash, a 5xx, a stack trace shown
  to a user, silent data loss, or another user's data exposed is always
  wrong; write "always-wrong".
- Concrete or nothing. Given names the exact records and field values. When
  names the exact action through the interface. Then names what the
  interface, the stored data, and the side effects must show.
- Group values that exercise the same code path into one table-driven case
  and put the value grid in Given. Split cases when the code paths differ.
- Completeness beats brevity: list every case your lens finds, up to 80,
  highest risk first. Past 80, name the remaining areas under "Not
  enumerated".
- Risk: H = data loss or corruption, security or privacy exposure, money, or
  a blocked core flow. M = wrong result or a broken secondary flow. L =
  cosmetic, or recoverable by retrying.

Reply in exactly this format and nothing else:

## {LENS}

### <your lens section's prefix>-<n>: <title, 10 words or fewer>
- Given: <state, concrete>
- When: <action through the interface>
- Then: <interface> · <stored> · <side effects>
- Oracle: <doc, spec, or file:line> | code-only | always-wrong
- Where: <file:line of the code that handles it>
- Setup: interface | db (<why the interface can't reach it>) | external (<test trigger>)
- Effects: none | <emails, charges, webhooks, third-party writes; mark irreversible ones>
- Risk: H | M | L
- Inducible: yes | needs <what> | no (<why>)

(repeat for each case)

### Not enumerated
- <area and why, or "None.">

### Inventory gaps
- <route, endpoint, command, or job missing from the brief's inventory, or "None.">
```

## lifecycle

Prefix `LIF`. Model every entity's state machine and data shapes.

- **Entities.** Every table, model, or aggregate the inventory touches. Its
  states come from status and enum columns, nullable timestamps that act as
  states (`deleted_at`, `verified_at`, `expires_at`), and derived states
  (overdue, empty, full, over quota).
- **Transition table.** Per entity, every state × every event. Each valid
  transition is a case that checks the new state and its effects. Each
  invalid one (pay a cancelled order, edit an archived record, re-verify a
  verified email) is a case whose expected result is a clear refusal with
  nothing stored.
- **CRUD.** Create; read; update each mutable field; delete. Delete with
  dependents (cascade, block, or orphan), restore after a soft delete, and
  recreate with the same unique key after a delete.
- **Cardinality.** Zero, one, many, exactly one page, one page plus one, and
  the largest count the app allows (cap, quota, plan limit).
- **Constraints.** A duplicate on each unique key, including case and
  whitespace variants; a reference to a deleted parent.
- **Time-driven transitions.** Expiry, trial end, scheduled publish,
  reminders. Reach them by setting timestamps (setup: db) when waiting is
  impractical, then trigger the job that acts on them.
- **Jobs and imports.** First run, a rerun on the same input, a run with
  nothing to do, a run over a partly processed batch.

Do not report: permission checks, field validation, outages and races,
navigation and display states.

## access

Prefix `ACC`. Build the authorization matrix and test it at the API, not only
in the UI.

- **Actors.** Anonymous; each role; owner and non-owner of the same role; a
  member of another tenant, org, or team; unverified, suspended, and deleted
  accounts; a user whose role changed or who was removed mid-session.
- **Matrix.** Every action in the inventory × every actor, as one
  table-driven case per resource with the actor × action grid and the
  expected allow or deny in each cell.
- **Direct access.** Call the API or URL directly for every action the UI
  hides from an actor. A hidden button is not access control.
- **Object references.** Swap IDs in paths, bodies, and query strings for
  another user's (IDOR), including nested resources
  (`/orgs/<A>/projects/<B's project>`) and sequential or guessable IDs.
- **Mass assignment.** On create and update, send fields the form doesn't
  show (`role`, `owner_id`, `tenant_id`, `price`, `verified`).
- **Sessions and tokens.** Expired; revoked by logout; after a password
  change; a reset or invite link used twice; a token for another user; a
  cookie-authenticated state change without its CSRF token.
- **Exposure.** List, search, export, count, and autocomplete endpoints, and
  error messages, that reveal other users' records or whether an account
  exists.

Do not report: field validation, lifecycle transitions, outages,
display-only states.

## input

Prefix `INP`. Cover every input the inventory accepts: form field, query
parameter, path segment, header the app reads, JSON field, file upload, CLI
argument, environment variable, imported file row.

- **Partitions.** One valid and one invalid value per equivalence class.
- **Boundaries.** min−1, min, max, max+1 for length, numeric range, count,
  and file size. Find the limit in the validator, the database column, and
  the UI, and test where they disagree (the UI allows 500 characters, the
  column holds 255).
- **Absence.** Missing, empty string, whitespace only, null, empty array,
  zero.
- **Type.** Wrong type, a number as a string, a float where an int belongs,
  scientific notation, NaN and Infinity, very large integers.
- **Text.** Leading and trailing whitespace, emoji and astral characters,
  combining marks, right-to-left text, NFC and NFD forms of the same string,
  zero-width characters, newlines and tabs, very long values.
- **Data, not code.** `'; --`, `"><img src=x onerror=alert(1)>`, `{{7*7}}`,
  `../../etc/passwd`, `=HYPERLINK(...)` in anything exported to CSV, a null
  byte. Expected: stored and shown literally, never interpreted.
- **Money and numbers.** Precision beyond the stored scale, rounding,
  negative and zero amounts, currencies with 0 or 3 decimals.
- **Dates and times.** Timezone offsets, DST gaps and overlaps, leap day,
  month-end, year boundary, far past and far future, date versus datetime,
  a user in a different timezone from the server.
- **Files.** Empty; at and over the size limit; extension that disagrees
  with content; the same name twice; unicode and path characters in the
  name; a corrupt file of an accepted type.
- **Round trip.** A saved value displays, edits, and exports back unchanged.

Do not report: permission checks, state transitions, outages and races,
navigation states.

## failure

Prefix `FAI`. Model what happens when the world misbehaves.

- **Dependencies.** For each store and external service in the brief:
  unavailable, slower than the app's timeout, an error response, a malformed
  or unexpected response. Expected: a clear error to the user, no partial
  write, the retry or queueing the app promises, and recovery when the
  dependency returns. Mark inducible only what the brief says can be
  induced.
- **Atomicity.** A multi-step write that fails between steps. Look for
  writes outside a transaction and external calls inside one.
- **Idempotency.** Double submit, double click, a request retried after a
  timeout, a webhook redelivered, the same job run twice, a resubmit via the
  back button. Expected: exactly one effect.
- **Concurrency.** Two users editing the same record (lost update), two
  requests racing for the last unit or the same unique name, overlapping job
  runs, a delete while another session edits.
- **Process.** A restart mid-operation (local targets only), a queue
  backlog, a stale cache after a write, a rate limit hit.
- **Scale.** The largest realistic result set, payload, and table the app
  meets. Expected: pagination or limits hold and nothing times out.

Do not report: field validation, permission checks, navigation states.

## interface

Prefix `IFC`. Model the states of the client itself. Use the web section,
the CLI and TUI section, or both.

Web:

- **Routes.** Every route logged out and logged in, reached by deep link,
  and with a nonexistent or deleted ID.
- **View states.** Empty, loading, error, and populated for every view, and
  populated with optional fields missing.
- **Navigation.** Refresh mid-flow; back and forward after a submit; a
  session that expires while a form is open (is the input lost?); acting in
  one tab and then using stale state in another.
- **Layout.** Phone and desktop widths for every core flow, and overflow
  with long values.
- **Keyboard and focus.** Every core flow completed by keyboard alone, focus
  returned after dialogs, form errors shown next to their fields.
- **Health.** Console errors and failed network requests on every route; a
  slow or dropped network during a submit.

CLI and TUI:

- **Commands.** Every command and every flag combination that changes
  behavior; `--help`; unknown and conflicting flags.
- **Streams.** Piped stdin versus a TTY; piped output (color, paging);
  non-UTF-8 input.
- **Files.** Missing, unreadable, and read-only files and directories;
  missing, malformed, and environment-overridden config.
- **Signals.** Ctrl-C and SIGTERM mid-write (is output partial or
  corrupted?) and the exit code for every failure.
- **Terminal.** Tiny and very wide sizes, and a resize while in use.

Do not report: server-side validation, permission checks, lifecycle
transitions, backend outages.
