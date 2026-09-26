#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Capture test evidence into a pack: raw output, timestamps, exit code, hashes.

  run   Run one command and keep what it printed, byte for byte, in
        <pack>/runs/<seq>-<id>/ (command.txt, stdout.txt, stderr.txt,
        meta.json), then append the record to <pack>/log.jsonl. Prints a tail
        of the output and exits with the command's exit code.
  seal  Write <pack>/SHA256SUMS over every file in the pack. Reviewers check it
        with `sha256sum -c SHA256SUMS` (macOS: `shasum -a 256 -c SHA256SUMS`).

Put everything after `--` verbatim; wrap pipes or redirects in `sh -c '...'`.
Refuses commands that carry a password, token, or key inline: pass those
through environment variables or client config files, never argv.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

SECRET = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)\s*[=:]\s*[^\s;'\"]+"
    r"|://[^/\s:@]+:[^/\s@]+@"
)
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
TAIL_LINES = 30


def die(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(2)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_state() -> dict[str, str | bool] | None:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return {"head": head, "dirty": bool(dirty)}


def now() -> datetime:
    return datetime.now(UTC)


def tail(path: Path, label: str) -> None:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return
    shown = lines[-TAIL_LINES:]
    header = (
        f"--- {label}: last {len(shown)} of {len(lines)} lines ---"
        if len(lines) > len(shown)
        else f"--- {label} ---"
    )
    print(header)
    print("\n".join(shown))


def run(pack: Path, test_id: str, note: str, argv: list[str]) -> int:
    if not argv:
        die("nothing to run; put the command after `--`")
    if not SAFE_ID.match(test_id):
        die(f"--id {test_id!r} must be letters, digits, '.', '_' or '-' (max 64)")
    joined = " ".join(argv)
    if SECRET.search(joined):
        die(
            "the command carries a credential inline; it would be written into the "
            "evidence. Pass it via an environment variable or the client's config file."
        )
    log = pack / "log.jsonl"
    pack.mkdir(parents=True, exist_ok=True)
    seq = sum(1 for _ in log.open(encoding="utf-8")) + 1 if log.exists() else 1
    run_dir = pack / "runs" / f"{seq:03d}-{test_id}"
    run_dir.mkdir(parents=True)
    (run_dir / "command.txt").write_text(joined + "\n", encoding="utf-8")
    stdout_path, stderr_path = run_dir / "stdout.txt", run_dir / "stderr.txt"

    started = now()
    try:
        with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
            code = subprocess.run(argv, stdout=out, stderr=err, check=False).returncode
    except OSError as exc:
        stderr_path.write_text(f"capture: could not start command: {exc}\n", encoding="utf-8")
        code = 127
    finished = now()

    meta = {
        "seq": seq,
        "id": test_id,
        "note": note,
        "argv": argv,
        "cwd": str(Path.cwd()),
        "host": platform.node(),
        "user": getpass.getuser(),
        "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": finished.isoformat(timespec="seconds"),
        "duration_s": round((finished - started).total_seconds(), 3),
        "exit_code": code,
        "stdout_sha256": sha256(stdout_path),
        "stderr_sha256": sha256(stderr_path),
        "local_git": git_state(),
        "dir": str(run_dir.relative_to(pack)),
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(meta) + "\n")

    tail(stdout_path, "stdout")
    tail(stderr_path, "stderr")
    print(f"[{seq:03d} {test_id}] exit {code} in {meta['duration_s']}s -> {run_dir}")
    if (pack / "SHA256SUMS").exists():
        print("note: pack was sealed before this run; run `seal` again before attaching")
    return code


def seal(pack: Path) -> int:
    if not pack.is_dir():
        die(f"{pack} is not a directory")
    manifest = pack / "SHA256SUMS"
    files = sorted(p for p in pack.rglob("*") if p.is_file() and p != manifest)
    lines = [f"{sha256(p)}  {p.relative_to(pack).as_posix()}" for p in files]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"sealed {len(files)} files; SHA256SUMS sha256 {sha256(manifest)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="action", required=True)
    run_p = sub.add_parser("run", help="run a command and capture it as evidence")
    run_p.add_argument("--pack", type=Path, required=True, help="evidence pack directory")
    run_p.add_argument("--id", required=True, help="test case id, e.g. TC-03 (or PLAN, PREFLIGHT)")
    run_p.add_argument("--note", default="", help="one line on what this run proves")
    run_p.add_argument("argv", nargs=argparse.REMAINDER, help="-- command and its arguments")
    seal_p = sub.add_parser("seal", help="write SHA256SUMS over the pack")
    seal_p.add_argument("--pack", type=Path, required=True, help="evidence pack directory")
    args = parser.parse_args()
    if args.action == "seal":
        return seal(args.pack)
    argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
    return run(args.pack, args.id, args.note, argv)


if __name__ == "__main__":
    sys.exit(main())
