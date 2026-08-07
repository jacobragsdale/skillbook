#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Behavior tests for capture-app-context's tracked-file scanner."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import TypedDict, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "skills" / "capture-app-context" / "scripts" / "scan_repo_context.py"


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


def _git(repo: Path, *arguments: str) -> None:
    _ = subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True)


def _write(repo: Path, relative_path: str, content: str) -> None:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(content, encoding="utf-8")


def _commit(repo: Path) -> None:
    _git(repo, "-c", "user.name=Skill Test", "-c", "user.email=skill@example.test", "commit", "--quiet", "-m", "fixture")


def _run_scan(repo: Path, *arguments: str) -> ScanReport:
    completed = subprocess.run([sys.executable, str(SCRIPT_PATH), "--root", str(repo), *arguments], check=True, capture_output=True, text=True)
    payload: object = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        message = "scanner output is not a JSON object"
        raise TypeError(message)
    return cast("ScanReport", payload)


class ScannerTests(unittest.TestCase):
    def test_scan_reports_locations_without_source_or_untracked_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir).resolve()
            _git(repo, "init", "--quiet")
            _write(repo, "src/client.py", 'endpoint = "https://orders.example.test"\nclient = HttpClient()\n')
            _write(repo, "database/procedures.sql", "CREATE PROCEDURE dbo.ApplyPayment AS SELECT * FROM dbo.Payment\n")
            _write(repo, "deploy/worker.yaml", "kind: Deployment\n---\nkind: CronJob\n")
            _write(repo, "docs/runbook.md", "Search Application Insights using the order id.\n")
            _write(repo, ".env", "API_TOKEN=must-not-appear\n")
            _write(repo, "certificate.pem", "must-not-appear\n")
            _write(repo, "notes.txt", "Splunk appears only in an untracked file.\n")
            _git(repo, "add", "src/client.py", "database/procedures.sql", "deploy/worker.yaml", "docs/runbook.md", "certificate.pem")
            _commit(repo)

            report = _run_scan(repo)
            rendered = json.dumps(report)

        self.assertIn("src/client.py", rendered)
        self.assertIn("database/procedures.sql", rendered)
        self.assertIn("deploy/worker.yaml", rendered)
        self.assertIn("docs/runbook.md", rendered)
        self.assertNotIn("notes.txt", rendered)
        self.assertNotIn("certificate.pem", rendered)
        self.assertNotIn("must-not-appear", rendered)
        self.assertNotIn("orders.example.test", rendered)
        self.assertEqual(report["skipped_sensitive_files"], 1)

    def test_scan_caps_each_category_and_reports_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir).resolve()
            _git(repo, "init", "--quiet")
            _write(repo, "src/clients.py", "HttpClient()\nHttpClient()\nHttpClient()\n")
            _git(repo, "add", "src/clients.py")
            _commit(repo)

            report = _run_scan(repo, "--max-matches-per-category", "2")

        self.assertEqual(len(report["categories"]["external_apis"]), 2)
        self.assertIn("external_apis", report["truncated_categories"])

    def test_scan_does_not_treat_a_docker_base_image_as_sql(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir).resolve()
            _git(repo, "init", "--quiet")
            _write(repo, "Dockerfile", "FROM python:3.14-slim\n")
            _git(repo, "add", "Dockerfile")
            _commit(repo)

            report = _run_scan(repo)

        self.assertEqual(report["categories"]["databases"], [])

    def test_main_writes_valid_json_to_a_selected_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir).resolve()
            output = repo.parent / f"{repo.name}-context.json"
            _git(repo, "init", "--quiet")
            _write(repo, "README.md", "Application Insights\n")
            _git(repo, "add", "README.md")
            _commit(repo)

            try:
                _ = subprocess.run([sys.executable, str(SCRIPT_PATH), "--root", str(repo), "--output", str(output)], check=True, capture_output=True, text=True)
                payload: object = json.loads(output.read_text(encoding="utf-8"))
            finally:
                output.unlink(missing_ok=True)

        if not isinstance(payload, dict):
            message = "scanner output is not a JSON object"
            raise TypeError(message)
        self.assertEqual(payload.get("root"), str(repo))

    def test_scan_supports_a_repository_before_its_first_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir).resolve()
            _git(repo, "init", "--quiet")
            _write(repo, "README.md", "Application Insights\n")
            _git(repo, "add", "README.md")

            report = _run_scan(repo)

        self.assertEqual(report["git_head"], "unborn")


if __name__ == "__main__":
    _ = unittest.main()
