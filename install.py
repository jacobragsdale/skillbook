#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Symlink each skill in this repo's skills/ into agent skill directories.

Creates per-skill symlinks (never links the whole directory — Claude Code
writes internal files into its skills dir, which breaks a dir-level symlink):

    ~/.agents/skills/<name>  -> <repo>/skills/<name>   (Cursor)
    ~/.claude/skills/<name>  -> <repo>/skills/<name>   (Claude Code)

Edits in the repo take effect everywhere immediately. Re-run after adding a
skill; use --uninstall to remove only symlinks that point into this repo.
"""

import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parent
SKILLS = REPO / "skills"
TARGET_ROOTS = [Path.home() / ".agents" / "skills", Path.home() / ".claude" / "skills"]


def repo_skills() -> list[Path]:
    return sorted(d for d in SKILLS.iterdir() if (d / "SKILL.md").is_file())


def install(dry_run: bool, force: bool) -> int:
    problems = 0
    for skill in repo_skills():
        for root in TARGET_ROOTS:
            link = root / skill.name
            if link.is_symlink() and link.resolve() == skill:
                print(f"ok        {link}")
                continue
            if link.exists() or link.is_symlink():
                if not force:
                    print(f"CONFLICT  {link} exists and is not a link to this repo (use --force)")
                    problems += 1
                    continue
                if dry_run:
                    print(f"replace   {link} -> {skill}")
                    continue
                if link.is_symlink():
                    link.unlink()
                else:
                    print(f"CONFLICT  {link} is a real file/dir — refusing to delete even with --force")
                    problems += 1
                    continue
            if dry_run:
                print(f"link      {link} -> {skill}")
                continue
            root.mkdir(parents=True, exist_ok=True)
            link.symlink_to(skill)
            print(f"linked    {link} -> {skill}")
    return 1 if problems else 0


def uninstall(dry_run: bool) -> int:
    for root in TARGET_ROOTS:
        if not root.is_dir():
            continue
        for link in sorted(root.iterdir()):
            if link.is_symlink() and SKILLS in link.resolve().parents:
                if dry_run:
                    print(f"would remove  {link}")
                else:
                    link.unlink()
                    print(f"removed       {link}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print actions without making changes")
    parser.add_argument("--force", action="store_true", help="replace existing symlinks that point elsewhere")
    parser.add_argument("--uninstall", action="store_true", help="remove symlinks pointing into this repo")
    args = parser.parse_args()

    if args.uninstall:
        return uninstall(args.dry_run)
    return install(args.dry_run, args.force)


if __name__ == "__main__":
    raise SystemExit(main())
