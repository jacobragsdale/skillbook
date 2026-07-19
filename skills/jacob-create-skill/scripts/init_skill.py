#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Scaffold a new agent skill folder.

Creates <dir>/<name>/ with a SKILL.md template (valid frontmatter, house-rule
section placeholders, learnings-loop block), a seeded LEARNINGS.md, and optional
Codex metadata.
"""

import argparse
import json
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

SKILL_TEMPLATE = """\
---
name: {name}
description: {description}
{invocation_line}---

# {title}

<!-- TODO: One sentence stating the capability and its important boundary. -->

If `LEARNINGS.md` next to this SKILL.md has entries, read them first — they
override the instructions below.

## Workflow

<!-- TODO: Imperative steps. Put deterministic work in scripts, stable detail
     in references, output material in assets, and judgment here. State whether
     the agent should RUN or READ each bundled file. -->

## Validation

<!-- TODO: Define observable completion checks and the repair loop on failure. -->

## Example

<!-- TODO: One compact, realistic input -> output example. -->

## Bundled resources

<!-- TODO: Delete this comment and list only resources that exist.
     - `scripts/<x>.py` — run to ...
     - `references/<x>.md` — read when ... -->

## Improving this skill

After use, if the user corrected you or the outcome surprised you, append one
dated line to `LEARNINGS.md` next to this SKILL.md:
`- YYYY-MM-DD: <what happened> → <what to do instead>`. Do not edit SKILL.md
directly; lessons are folded in deliberately, not on the fly.
"""

LEARNINGS_TEMPLATE = """\
# Learnings

Dated corrections from real use of this skill. Read before executing;
fold recurring/confirmed entries into SKILL.md and delete them here.

Format: `- YYYY-MM-DD: <what happened> → <what to do instead>`

(no entries yet)
"""

DEFAULT_DESCRIPTION = (
    "TODO: write as a directive trigger, not a summary. First sentence "
    "(~80 chars) names the capability and top keywords; then 'Use when "
    "the user ...' with concrete phrases, an 'even if ...' clause, and an "
    "anti-trigger if the domain is high-frequency. Keep under 250 chars."
)

def codex_sidecar(title: str, explicit_only: bool) -> str:
    lines = ["interface:", f"  display_name: {title}"]
    if explicit_only:
        lines += ["policy:", "  allow_implicit_invocation: false"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "name", help="skill name: lowercase letters, digits, hyphens; max 64 chars"
    )
    parser.add_argument(
        "--dir",
        default="skills",
        help="skills root to create the folder in (default: ./skills)",
    )
    parser.add_argument(
        "--description",
        default=DEFAULT_DESCRIPTION,
        help="frontmatter description (trigger-style)",
    )
    parser.add_argument(
        "--explicit-only",
        action="store_true",
        help="add disable-model-invocation: true so the skill only runs via "
        "explicit /skill-name (house default is automatic triggering)",
    )
    parser.add_argument(
        "--strict-core",
        action="store_true",
        help="omit vendor frontmatter extensions so SKILL.md passes strict core validation",
    )
    parser.add_argument(
        "--codex",
        action="store_true",
        help="add agents/openai.yaml; with --explicit-only, disables Codex implicit invocation",
    )
    args = parser.parse_args()

    if not NAME_RE.match(args.name) or len(args.name) > 64:
        print(
            f"error: invalid name {args.name!r} — need ^[a-z0-9]+(-[a-z0-9]+)*$, max 64 chars",
            file=sys.stderr,
        )
        return 1

    skill_dir = Path(args.dir) / args.name
    if skill_dir.exists():
        print(f"error: {skill_dir} already exists", file=sys.stderr)
        return 1

    skill_dir.mkdir(parents=True)
    title = args.name.replace("-", " ").capitalize()
    invocation_line = (
        "disable-model-invocation: true\n"
        if args.explicit_only and not args.strict_core
        else ""
    )
    (skill_dir / "SKILL.md").write_text(
        # json.dumps produces a YAML-safe double-quoted scalar
        SKILL_TEMPLATE.format(
            name=args.name,
            description=json.dumps(args.description),
            title=title,
            invocation_line=invocation_line,
        ),
        encoding="utf-8",
    )
    (skill_dir / "LEARNINGS.md").write_text(LEARNINGS_TEMPLATE, encoding="utf-8")
    if args.codex:
        agents_dir = skill_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "openai.yaml").write_text(
            codex_sidecar(title, args.explicit_only), encoding="utf-8"
        )

    print(f"created {skill_dir}/")
    print("  SKILL.md      — fill in the TODO sections, keep the body under 300 lines")
    print("  LEARNINGS.md  — seeded empty")
    if args.strict_core:
        invocation = "client default (strict core has no portable invocation field)"
    elif args.explicit_only:
        invocation = "explicit in Cursor/Claude (disable-model-invocation: true)"
    else:
        invocation = "automatic (model-invocable; house default)"
    print(f"  invocation    — {invocation}")
    if args.codex:
        codex_state = (
            "Codex implicit invocation disabled"
            if args.explicit_only
            else "Codex implicit invocation enabled (default)"
        )
        print(f"  openai.yaml   — {codex_state}")
    print("next: draft, then validate with scripts/validate_skill.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
