# Learnings

Dated corrections from real use of this skill. Read before executing;
fold recurring/confirmed entries into SKILL.md and delete them here.

Format: `- YYYY-MM-DD: <what happened> → <what to do instead>`

- 2026-07-01: Web research delivered a stale diagnostic-rule name (reportPossiblyUnbound vs the real reportPossiblyUnboundVariable); running the bundled script against the actual tool caught it → when a skill encodes tool-specific identifiers (rule names, flags, config keys), execute the tool once during creation to reconcile them, and make scripts degrade gracefully on unknown identifiers since they drift between versions.
