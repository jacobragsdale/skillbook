#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Digest a Claude Code or pi session transcript for a retro.

Prints one line per user message, assistant reply, tool call, and tool error,
each prefixed with its line number in the transcript, so a retro can read a
session without loading raw tool output. A footer lists counts, the largest
tool results (the expensive calls), and calls repeated verbatim.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

CLAUDE_ROOT = Path.home() / ".claude" / "projects"
PI_ROOT = Path.home() / ".pi" / "agent" / "sessions"
REMINDER_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)
INPUT_KEYS = ("command", "file_path", "path", "pattern", "url", "query", "description", "prompt")


@dataclass
class Digest:
    path: Path
    harness: str
    cwd: str = "?"
    lines: list[str] = field(default_factory=list)
    calls: dict[str, str] = field(default_factory=dict)  # tool call id -> "Name: input"
    results: list[tuple[int, int, str]] = field(default_factory=list)  # (chars, line, call)
    call_counts: Counter[str] = field(default_factory=Counter)
    users: int = 0
    errors: int = 0
    bad_lines: int = 0


def squash(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def summarize_input(name: str, args: object) -> str:
    if isinstance(args, dict):
        for key in INPUT_KEYS:
            if isinstance(args.get(key), str):
                return f"{name}: {args[key]}"
    return f"{name}: {json.dumps(args, ensure_ascii=False)}"


def block_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
    return ""


def detect_harness(path: Path) -> str:
    with path.open(encoding="utf-8") as fh:
        first = fh.readline()
    try:
        record = json.loads(first)
    except json.JSONDecodeError:
        return "claude"
    return "pi" if record.get("type") == "session" and "cwd" in record else "claude"


def session_cwd(path: Path, harness: str) -> str | None:
    with path.open(encoding="utf-8") as fh:
        for n, raw in enumerate(fh):
            if n >= 200:
                break
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(record.get("cwd"), str):
                return record["cwd"]
            if harness == "pi":
                break
    return None


def first_prompt(path: Path, harness: str) -> str:
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            message = record.get("message") or {}
            is_user = (
                record.get("type") == "user" and not record.get("isMeta")
                if harness == "claude"
                else record.get("type") == "message" and message.get("role") == "user"
            )
            if not is_user:
                continue
            text = REMINDER_RE.sub("", block_text(message.get("content"))).strip()
            if text and not (harness == "claude" and _only_tool_results(message)):
                return text
    return ""


def _only_tool_results(message: dict) -> bool:
    content = message.get("content")
    return isinstance(content, list) and all(
        isinstance(b, dict) and b.get("type") == "tool_result" for b in content
    )


def candidates(harness: str) -> list[tuple[float, Path, str]]:
    found: list[tuple[float, Path, str]] = []
    if harness in ("claude", "any") and CLAUDE_ROOT.is_dir():
        found += [(p.stat().st_mtime, p, "claude") for p in CLAUDE_ROOT.glob("*/*.jsonl")]
    if harness in ("pi", "any") and PI_ROOT.is_dir():
        found += [(p.stat().st_mtime, p, "pi") for p in PI_ROOT.glob("*/*.jsonl")]
    found.sort(reverse=True)
    return found


def matching_sessions(harness: str, cwd: str | None) -> list[tuple[float, Path, str]]:
    target = str(Path(cwd).resolve()) if cwd else None
    out = []
    for mtime, path, kind in candidates(harness):
        if target is None or session_cwd(path, kind) == target:
            out.append((mtime, path, kind))
    return out


def add(digest: Digest, line: int, kind: str, text: str, limit: int) -> None:
    digest.lines.append(f"{line:>6} {kind:<9} {squash(text, limit)}")


def record_call(digest: Digest, call_id: str, name: str, args: object, line: int, limit: int) -> None:
    summary = summarize_input(name, args)
    digest.calls[call_id] = summary
    digest.call_counts[squash(summary, 200)] += 1
    add(digest, line, "TOOL", summary, limit)


def record_result(
    digest: Digest, call_id: str, name: str, content: object, error: bool, line: int, limit: int
) -> None:
    text = block_text(content)
    call = digest.calls.get(call_id, name or "?")
    digest.results.append((len(text), line, call))
    if error:
        digest.errors += 1
        add(digest, line, "ERROR", f"{call.split(':', 1)[0]}: {text}", limit)


def parse_claude(digest: Digest, records: list[tuple[int, dict]], args: argparse.Namespace) -> None:
    for line, record in records:
        if record.get("isSidechain") and not args.sidechains:
            continue
        message = record.get("message") or {}
        content = message.get("content")
        if record.get("type") == "user":
            if isinstance(content, str):
                if not record.get("isMeta"):
                    _user(digest, line, content, args.max_chars)
                continue
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_result":
                    record_result(
                        digest, block.get("tool_use_id", ""), "", block.get("content"),
                        bool(block.get("is_error")), line, args.max_chars,
                    )
                elif block.get("type") == "text" and not record.get("isMeta"):
                    _user(digest, line, block.get("text", ""), args.max_chars)
        elif record.get("type") == "assistant":
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_use":
                    record_call(
                        digest, block.get("id", ""), block.get("name", "?"),
                        block.get("input"), line, args.max_chars,
                    )
                elif block.get("type") == "text" and not args.no_assistant:
                    add(digest, line, "ASSISTANT", block.get("text", ""), args.max_chars)


def parse_pi(digest: Digest, records: list[tuple[int, dict]], args: argparse.Namespace) -> None:
    for line, record in records:
        if record.get("type") == "session":
            digest.cwd = record.get("cwd", "?")
        if record.get("type") != "message":
            continue
        message = record.get("message") or {}
        role = message.get("role")
        content = message.get("content")
        if role == "user":
            _user(digest, line, block_text(content), args.max_chars)
        elif role == "assistant":
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "toolCall":
                    record_call(
                        digest, block.get("id", ""), block.get("name", "?"),
                        block.get("arguments"), line, args.max_chars,
                    )
                elif block.get("type") == "text" and not args.no_assistant:
                    add(digest, line, "ASSISTANT", block.get("text", ""), args.max_chars)
        elif role == "toolResult":
            record_result(
                digest, message.get("toolCallId", ""), message.get("toolName", "?"),
                content, bool(message.get("isError")), line, args.max_chars,
            )


def _user(digest: Digest, line: int, text: str, limit: int) -> None:
    text = REMINDER_RE.sub("", text).strip()
    if text:
        digest.users += 1
        add(digest, line, "USER", text, limit)


def digest_file(path: Path, args: argparse.Namespace) -> Digest:
    harness = detect_harness(path)
    digest = Digest(path=path, harness=harness)
    records: list[tuple[int, dict]] = []
    with path.open(encoding="utf-8") as fh:
        for line, raw in enumerate(fh, start=1):
            try:
                records.append((line, json.loads(raw)))
            except json.JSONDecodeError:
                digest.bad_lines += 1
    if harness == "pi":
        parse_pi(digest, records, args)
    else:
        digest.cwd = session_cwd(path, harness) or "?"
        parse_claude(digest, records, args)
    return digest


def print_digest(digest: Digest, top: int) -> None:
    print(f"# session: {digest.path}")
    print(f"# harness: {digest.harness}  cwd: {digest.cwd}")
    print("#   line kind      text")
    print("\n".join(digest.lines))
    print(
        f"# counts: {digest.users} user messages, {sum(digest.call_counts.values())} tool calls, "
        f"{digest.errors} tool errors"
        + (f", {digest.bad_lines} unparseable lines" if digest.bad_lines else "")
    )
    if digest.results:
        print(f"# largest tool results (chars, line, call):")
        for size, line, call in sorted(digest.results, reverse=True)[:top]:
            print(f"#   {size:>9,}  {line:>6}  {squash(call, 120)}")
    repeated = [(n, call) for call, n in digest.call_counts.most_common() if n > 1]
    if repeated:
        print("# calls repeated verbatim:")
        for n, call in repeated[:top]:
            print(f"#   {n}×  {squash(call, 120)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Transcripts are read from ~/.claude/projects/*/*.jsonl (Claude Code) and "
            "~/.pi/agent/sessions/*/*.jsonl (pi). Exit codes: 0 ok, 1 no session found, "
            "2 bad arguments."
        ),
    )
    parser.add_argument("path", nargs="?", type=Path, help="transcript .jsonl to digest")
    parser.add_argument("--latest", action="store_true", help="digest the newest session for --cwd")
    parser.add_argument("--list", type=int, metavar="N", help="list the N newest sessions for --cwd and exit")
    parser.add_argument("--cwd", default=str(Path.cwd()), help="working directory the session ran in (default: here)")
    parser.add_argument("--any-cwd", action="store_true", help="ignore --cwd when picking sessions")
    parser.add_argument("--harness", choices=("any", "claude", "pi"), default="any")
    parser.add_argument("--max-chars", type=int, default=240, help="truncate each line to N characters (default 240)")
    parser.add_argument("--no-assistant", action="store_true", help="omit assistant text replies")
    parser.add_argument("--sidechains", action="store_true", help="include Claude Code subagent records")
    parser.add_argument("--top", type=int, default=5, help="rows in the footer tables (default 5)")
    args = parser.parse_args()

    if sum(bool(x) for x in (args.path, args.latest, args.list)) != 1:
        parser.error("give exactly one of: a transcript path, --latest, or --list N")

    cwd = None if args.any_cwd else args.cwd
    if args.list or args.latest:
        sessions = matching_sessions(args.harness, cwd)
        if not sessions:
            where = "any directory" if cwd is None else cwd
            kind = "" if args.harness == "any" else f"{args.harness} "
            print(
                f"session_digest: no {kind}session found for {where}; "
                "pass --any-cwd, --harness, or a transcript path",
                file=sys.stderr,
            )
            return 1
        if args.list:
            for mtime, path, kind in sessions[: args.list]:
                stamp = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                print(f"{stamp}  {kind:<6}  {path}\n    {squash(first_prompt(path, kind), 100)}")
            return 0
        args.path = sessions[0][1]

    if not args.path.is_file():
        print(f"session_digest: {args.path} is not a file", file=sys.stderr)
        return 1
    print_digest(digest_file(args.path, args), args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
