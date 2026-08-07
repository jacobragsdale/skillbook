#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Inventory tracked repository evidence for surrounding application context."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from collections.abc import Sequence


class DiscoveryError(RuntimeError):
    """Raised when a repository cannot be scanned safely."""


class Evidence(TypedDict):
    path: str
    line: int | None
    signals: list[str]


class ScanReport(TypedDict):
    root: str
    git_head: str
    generated_at: str
    scanned_files: int
    skipped_sensitive_files: int
    categories: dict[str, list[Evidence]]
    truncated_categories: list[str]


_SKIPPED_DIRECTORY_NAMES = {".git", ".idea", ".pytest_cache", ".ruff_cache", ".venv", ".vscode", "__pycache__", "node_modules", "target"}
_SENSITIVE_SUFFIXES = {".cer", ".crt", ".der", ".jks", ".key", ".p12", ".pem", ".pfx"}
_SENSITIVE_NAMES = {".npmrc", ".pypirc", "id_dsa", "id_ed25519", "id_rsa"}

_PATH_PATTERNS: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "observability": (("observability-path", re.compile(r"(?:^|/)(?:log|logs|logging|monitoring|observability|runbooks?)(?:/|\.|$)", re.IGNORECASE)),),
    "external_apis": (("api-path", re.compile(r"(?:^|/)(?:api|apis|clients?|openapi|swagger)(?:/|\.|$)", re.IGNORECASE)),),
    "databases": (("database-path", re.compile(r"(?:^|/)(?:database|db|migrations?|sql|stored[-_ ]?procedures?)(?:/|\.|$)", re.IGNORECASE)),),
    "aks_runtime": (("kubernetes-path", re.compile(r"(?:^|/)(?:charts?|deploy|helm|k8s|kubernetes|manifests?)(?:/|\.|$)", re.IGNORECASE)),),
    "jobs": (("job-path", re.compile(r"(?:^|/)(?:cron|jobs?|schedules?)(?:/|\.|$)", re.IGNORECASE)),),
    "delivery": (("pipeline-path", re.compile(r"(?:^|/)(?:\.github/workflows|azure-pipelines|deploy|pipelines?)(?:/|\.|$)", re.IGNORECASE)),),
    "dependencies": (("dependency-path", re.compile(r"(?:^|/)(?:config|infrastructure|messaging|queues?|storage)(?:/|\.|$)", re.IGNORECASE)),),
    "operations": (("operations-path", re.compile(r"(?:^|/)(?:alerts?|codeowners|operations|owners?|runbooks?)(?:/|\.|$)", re.IGNORECASE)),),
}

_CONTENT_PATTERNS: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "observability": (
        ("application-insights", re.compile(r"\b(?:ApplicationInsights|appinsights)\b", re.IGNORECASE)),
        ("log-analytics", re.compile(r"\b(?:Log Analytics|logAnalytics|workspaceId)\b", re.IGNORECASE)),
        ("logging", re.compile(r"\b(?:Datadog|ILogger|log4net|New Relic|Serilog|Splunk)\b", re.IGNORECASE)),
    ),
    "external_apis": (
        ("http-client", re.compile(r"\b(?:axios|fetch|HttpClient|httpx|requests)\b", re.IGNORECASE)),
        ("api-contract", re.compile(r"\b(?:OpenAPI|Swagger)\b", re.IGNORECASE)),
        ("url", re.compile(r"https?://", re.IGNORECASE)),
    ),
    "databases": (
        ("database-client", re.compile(r"\b(?:DbContext|Dapper|JDBC|Npgsql|ODBC|SqlConnection)\b", re.IGNORECASE)),
        ("sql-call", re.compile(r"\b(?:CALL|EXEC)\s+[\[\]\w.]+|\bSELECT\b.+\bFROM\b|\b(?:DELETE\s+FROM|INSERT\s+INTO|UPDATE)\s+[\[\]\w.]+")),
        ("database-definition", re.compile(r"\bCREATE\s+(?:FUNCTION|PROCEDURE|TABLE|VIEW)\b", re.IGNORECASE)),
    ),
    "aks_runtime": (
        ("aks", re.compile(r"\bAKS\b|\baz\s+aks\b", re.IGNORECASE)),
        ("kubernetes-kind", re.compile(r"\bkind:\s*(?:CronJob|Deployment|Ingress|Job|Service|StatefulSet)\b", re.IGNORECASE)),
        ("kubectl", re.compile(r"\bkubectl\b", re.IGNORECASE)),
    ),
    "jobs": (
        ("job-kind", re.compile(r"\bkind:\s*(?:CronJob|Job)\b", re.IGNORECASE)),
        ("scheduler", re.compile(r"\b(?:Hangfire|Quartz|schedule|scheduler)\b", re.IGNORECASE)),
        ("cron", re.compile(r"\bcron(?:job)?\b", re.IGNORECASE)),
    ),
    "delivery": (
        ("pipeline", re.compile(r"\b(?:azure-pipelines|GitHub Actions|Jenkinsfile|pipeline)\b", re.IGNORECASE)),
        ("deployment-command", re.compile(r"\b(?:helm\s+(?:install|upgrade)|kubectl\s+apply)\b", re.IGNORECASE)),
    ),
    "dependencies": (
        ("messaging", re.compile(r"\b(?:Event Hubs?|Kafka|RabbitMQ|Service Bus|topic|queue)\b", re.IGNORECASE)),
        ("storage", re.compile(r"\b(?:Blob Storage|Cosmos DB|Redis|S3)\b", re.IGNORECASE)),
        ("secret-store", re.compile(r"\b(?:Key Vault|KeyVault|secretKeyRef|Secrets Manager)\b", re.IGNORECASE)),
    ),
    "operations": (("ownership", re.compile(r"\b(?:CODEOWNERS|on-call|owner|support team)\b", re.IGNORECASE)), ("runbook", re.compile(r"\b(?:alert|incident|runbook)\b", re.IGNORECASE))),
}


def _run_git(root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(["git", "-C", str(root), *arguments], check=False, capture_output=True)
    if completed.returncode != 0:
        detail = completed.stderr.decode(errors="replace").strip()
        diagnostic = detail if detail != "" else "no diagnostic"
        message = f"git {' '.join(arguments)} failed for {root}: {diagnostic}"
        raise DiscoveryError(message)
    return completed.stdout


def _repository_root(root: Path) -> Path:
    candidate = root.expanduser().resolve()
    if not candidate.is_dir():
        message = f"repository root is not a directory: {candidate}"
        raise DiscoveryError(message)
    resolved = Path(os.fsdecode(_run_git(candidate, "rev-parse", "--show-toplevel").strip())).resolve()
    if not resolved.is_dir():
        message = f"Git reported a missing repository root: {resolved}"
        raise DiscoveryError(message)
    return resolved


def _tracked_paths(root: Path) -> list[Path]:
    raw_paths = _run_git(root, "ls-files", "-z").split(b"\0")
    return [Path(os.fsdecode(raw_path)) for raw_path in raw_paths if raw_path != b""]


def _is_sensitive(relative_path: Path) -> bool:
    lowered_name = relative_path.name.lower()
    if any(part in _SKIPPED_DIRECTORY_NAMES for part in relative_path.parts):
        return True
    if lowered_name in _SENSITIVE_NAMES or relative_path.suffix.lower() in _SENSITIVE_SUFFIXES:
        return True
    return lowered_name.startswith(".env") and lowered_name != ".env.example"


def _read_text(path: Path, *, max_file_bytes: int) -> str | None:
    if path.is_symlink() or not path.is_file():
        return None
    with path.open("rb") as source:
        raw = source.read(max_file_bytes + 1)
    if len(raw) > max_file_bytes or b"\0" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _append_match(matches: dict[tuple[str, int | None], set[str]], *, path: str, line: int | None, signals: Sequence[str]) -> None:
    key = (path, line)
    matches.setdefault(key, set()).update(signals)


def _category_evidence(matches: dict[tuple[str, int | None], set[str]], *, limit: int) -> tuple[list[Evidence], bool]:
    ordered = sorted(matches.items(), key=_evidence_sort_key)
    evidence = [Evidence(path=path, line=line, signals=sorted(signals)) for (path, line), signals in ordered[:limit]]
    return evidence, len(ordered) > limit


def _evidence_sort_key(item: tuple[tuple[str, int | None], set[str]]) -> tuple[str, int]:
    path, line = item[0]
    return path, -1 if line is None else line


def _git_head(root: Path) -> str:
    completed = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "HEAD"], check=False, capture_output=True)
    if completed.returncode != 0:
        return "unborn"
    return completed.stdout.decode(errors="replace").strip()


def scan_repository(root: Path, *, max_file_bytes: int = 1_000_000, max_matches_per_category: int = 200) -> ScanReport:
    """Return source-free evidence locations from tracked UTF-8 repository files."""
    if max_file_bytes < 1:
        message = "max_file_bytes must be positive"
        raise ValueError(message)
    if max_matches_per_category < 1:
        message = "max_matches_per_category must be positive"
        raise ValueError(message)

    repo_root = _repository_root(root)
    matches_by_category: dict[str, dict[tuple[str, int | None], set[str]]] = {category: {} for category in _CONTENT_PATTERNS}
    scanned_files = 0
    skipped_sensitive_files = 0

    for relative_path in _tracked_paths(repo_root):
        if _is_sensitive(relative_path):
            skipped_sensitive_files += 1
            continue
        candidate = repo_root / relative_path
        try:
            resolved_candidate = candidate.resolve(strict=True)
        except FileNotFoundError:
            continue
        if not resolved_candidate.is_relative_to(repo_root):
            continue

        path_text = relative_path.as_posix()
        for category, patterns in _PATH_PATTERNS.items():
            path_signals = [name for name, pattern in patterns if pattern.search(path_text) is not None]
            if len(path_signals) > 0:
                _append_match(matches_by_category[category], path=path_text, line=None, signals=path_signals)

        text = _read_text(candidate, max_file_bytes=max_file_bytes)
        if text is None:
            continue
        scanned_files += 1
        for line_number, line in enumerate(text.splitlines(), start=1):
            for category, patterns in _CONTENT_PATTERNS.items():
                signals = [name for name, pattern in patterns if pattern.search(line) is not None]
                if len(signals) > 0:
                    _append_match(matches_by_category[category], path=path_text, line=line_number, signals=signals)

    categories: dict[str, list[Evidence]] = {}
    truncated_categories: list[str] = []
    for category, matches in matches_by_category.items():
        evidence, truncated = _category_evidence(matches, limit=max_matches_per_category)
        categories[category] = evidence
        if truncated:
            truncated_categories.append(category)

    return ScanReport(
        root=str(repo_root),
        git_head=_git_head(repo_root),
        generated_at=datetime.now(UTC).isoformat(),
        scanned_files=scanned_files,
        skipped_sensitive_files=skipped_sensitive_files,
        categories=categories,
        truncated_categories=truncated_categories,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--root", type=Path, default=Path.cwd(), help="Git repository to scan (default: current directory)")
    _ = parser.add_argument("--output", type=Path, help="write JSON to this file instead of stdout")
    _ = parser.add_argument("--max-file-bytes", type=int, default=1_000_000, help="skip tracked files larger than this many bytes")
    _ = parser.add_argument("--max-matches-per-category", type=int, default=200, help="cap emitted evidence records in each category")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = scan_repository(Path(args.root), max_file_bytes=int(args.max_file_bytes), max_matches_per_category=int(args.max_matches_per_category))
    except (DiscoveryError, OSError, ValueError) as error:
        _ = sys.stderr.write(f"error: {error}\n")
        return 1

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        _ = sys.stdout.write(rendered)
    else:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        _ = output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
