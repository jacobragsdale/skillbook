#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Scaffold a new ratatui app from the rust-tui template.

Copies assets/template to DIR/NAME, renames the crate, its library path and
its environment variables, runs the checks the template's CI runs, and makes
the first commit. The result is a working two-pane directory browser whose
domain (worker.rs, the Entry type, the list columns) you then replace.
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "template"
DESCRIPTION = "A fast, mouse-first terminal app"
NAME = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", help="crate and binary name, kebab-case (e.g. log-tui)")
    parser.add_argument("--dir", type=Path, default=Path.home() / "dev", help="parent directory (default: ~/dev)")
    parser.add_argument("--description", default=DESCRIPTION, help="one line for Cargo.toml, README and --help")
    parser.add_argument("--no-check", action="store_true", help="skip cargo fmt/clippy/test and the replay smoke run")
    parser.add_argument("--no-git", action="store_true", help="skip git init and the first commit")
    args = parser.parse_args()

    if not NAME.match(args.name):
        return fail(f"`{args.name}` is not kebab-case: lowercase letters and digits, joined by single hyphens")
    dest = args.dir.expanduser().resolve() / args.name
    if dest.exists():
        return fail(f"{dest} already exists; pick another name or remove it")
    if not TEMPLATE.is_dir():
        return fail(f"template not found at {TEMPLATE}")

    shutil.copytree(TEMPLATE, dest, ignore=shutil.ignore_patterns("target", "frames"))
    replacements = {
        "tui-template": args.name,
        "tui_template": args.name.replace("-", "_"),
        "TUI_TEMPLATE": args.name.replace("-", "_").upper(),
        DESCRIPTION: args.description,
    }
    for path in sorted(p for p in dest.rglob("*") if p.is_file()):
        text = path.read_text(encoding="utf-8")
        new = text
        for old, value in replacements.items():
            new = new.replace(old, value)
        if new != text:
            path.write_text(new, encoding="utf-8")
    print(f"created {dest}")

    # A longer or shorter name moves line lengths; format before checking.
    subprocess.run(["cargo", "fmt", "--all"], cwd=dest, check=False)

    if not args.no_check:
        for command in (
            ["cargo", "clippy", "--all-targets", "--all-features", "--quiet", "--", "-D", "warnings"],
            ["cargo", "test", "--all-targets", "--quiet"],
            ["cargo", "run", "--quiet", "--", "--replay", "scripts/smoke.keys", "src"],
        ):
            print("$", " ".join(command))
            done = subprocess.run(command, cwd=dest, stdout=subprocess.DEVNULL if command[1] == "run" else None, check=False)
            if done.returncode != 0:
                return fail(f"`{' '.join(command)}` failed in {dest}; the copy is left for inspection")

    if not args.no_git:
        subprocess.run(["git", "init", "--quiet", "--initial-branch", "main"], cwd=dest, check=True)
        subprocess.run(["git", "add", "--all"], cwd=dest, check=True)
        message = f"Scaffold {args.name} from the rust-tui template"
        if subprocess.run(["git", "commit", "--quiet", "--message", message], cwd=dest, check=False).returncode != 0:
            return fail("git commit failed (is user.name/user.email set?); the files are staged")
        print(f"committed: {message}")

    print(f"next: cd {dest} && cargo run")
    return 0


def fail(message: str) -> int:
    print(f"new_tui.py: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
