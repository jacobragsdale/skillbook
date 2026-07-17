#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Regression tests for jacob-create-skill's scaffolder and validator."""

import importlib.util
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "skills" / "jacob-create-skill" / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


init_skill = load_module("jacob_init_skill", SCRIPT_DIR / "init_skill.py")
validate_skill = load_module("jacob_validate_skill", SCRIPT_DIR / "validate_skill.py")

LEARNINGS = """# Learnings

Format: `- YYYY-MM-DD: <what happened> → <what to do instead>`

(no entries yet)
"""


class SkillToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_skill(
        self,
        name: str = "test-skill",
        *,
        extra_frontmatter: str = "",
        body: str = "Follow the requested workflow.\n\nRead LEARNINGS.md before executing.\n",
        description: str = (
            "Create a verified test artifact. Use when the user asks to exercise "
            "the skill tooling or validate a generated skill."
        ),
    ) -> Path:
        skill_dir = self.root / name
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {description}\n"
            f"{extra_frontmatter}---\n\n{body}",
            encoding="utf-8",
        )
        (skill_dir / "LEARNINGS.md").write_text(LEARNINGS, encoding="utf-8")
        return skill_dir

    def run_init(self, *args: str) -> int:
        argv = ["init_skill.py", *args]
        with patch.object(sys, "argv", argv), redirect_stdout(StringIO()):
            return init_skill.main()

    def test_unfinished_scaffold_fails_validation(self) -> None:
        self.assertEqual(self.run_init("probe", "--dir", str(self.root)), 0)
        skill_dir = self.root / "probe"
        errors, _ = validate_skill.validate(skill_dir)
        self.assertTrue(any("scaffold TODO" in error for error in errors), errors)
        self.assertNotIn(
            "disable-model-invocation", (skill_dir / "SKILL.md").read_text()
        )

    def test_explicit_only_scaffold_disables_model_invocation(self) -> None:
        self.assertEqual(
            self.run_init("locked", "--dir", str(self.root), "--explicit-only"), 0
        )
        self.assertIn(
            "disable-model-invocation: true",
            (self.root / "locked" / "SKILL.md").read_text(),
        )

    def test_strict_core_and_codex_scaffolding(self) -> None:
        self.assertEqual(
            self.run_init(
                "portable",
                "--dir",
                str(self.root),
                "--strict-core",
                "--codex",
                "--explicit-only",
            ),
            0,
        )
        skill_dir = self.root / "portable"
        skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("disable-model-invocation", skill_text)
        self.assertIn(
            "allow_implicit_invocation: false",
            (skill_dir / "agents" / "openai.yaml").read_text(encoding="utf-8"),
        )

    def test_codex_without_explicit_only_writes_no_sidecar(self) -> None:
        self.assertEqual(
            self.run_init("open", "--dir", str(self.root), "--codex"), 0
        )
        self.assertFalse((self.root / "open" / "agents").exists())

    def test_completed_skill_passes_house_profile(self) -> None:
        errors, warnings = validate_skill.validate(self.write_skill())
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_fenced_example_path_is_not_treated_as_reference(self) -> None:
        body = """Run the workflow.

```markdown
Read `references/not-real.md` in an example skill.
```

Read LEARNINGS.md before executing.
"""
        errors, warnings = validate_skill.validate(self.write_skill(body=body))
        self.assertEqual(errors, [])
        self.assertFalse(any("not-real" in warning for warning in warnings), warnings)

    def test_real_missing_reference_warns(self) -> None:
        body = (
            "Read references/missing.md before running.\n\nRead LEARNINGS.md first.\n"
        )
        _, warnings = validate_skill.validate(self.write_skill(body=body))
        self.assertTrue(any("references/missing.md" in warning for warning in warnings))

    def test_core_profile_rejects_vendor_frontmatter(self) -> None:
        skill_dir = self.write_skill(
            extra_frontmatter="disable-model-invocation: true\n"
        )
        errors, _ = validate_skill.validate(skill_dir, profile="core")
        self.assertTrue(
            any("disable-model-invocation" in error for error in errors), errors
        )

    def test_codex_profile_uses_sidecar_for_explicit_invocation(self) -> None:
        skill_dir = self.write_skill(
            extra_frontmatter="disable-model-invocation: true\n"
        )
        agents_dir = skill_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "openai.yaml").write_text(
            "policy:\n  allow_implicit_invocation: false\n", encoding="utf-8"
        )
        errors, warnings = validate_skill.validate(skill_dir, profile="codex")
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_metadata_values_must_be_strings(self) -> None:
        skill_dir = self.write_skill(extra_frontmatter="metadata:\n  version: 2\n")
        errors, _ = validate_skill.validate(skill_dir)
        self.assertIn("metadata must map string keys to string values", errors)

    def test_invalid_eval_manifest_fails_validation(self) -> None:
        skill_dir = self.write_skill()
        evals_dir = skill_dir / "evals"
        evals_dir.mkdir()
        (evals_dir / "evals.json").write_text("{not json}", encoding="utf-8")
        errors, _ = validate_skill.validate(skill_dir)
        self.assertTrue(any("not valid JSON" in error for error in errors), errors)

    def test_trigger_manifest_requires_balanced_cases(self) -> None:
        skill_dir = self.write_skill()
        evals_dir = skill_dir / "evals"
        evals_dir.mkdir()
        (evals_dir / "trigger_queries.json").write_text(
            '[{"query": "make a skill", "should_trigger": true}]',
            encoding="utf-8",
        )
        errors, _ = validate_skill.validate(skill_dir)
        self.assertTrue(
            any("three should-trigger" in error for error in errors), errors
        )

    def test_use_when_must_fit_250_character_budget(self) -> None:
        description = "A" * 251 + " Use when this should route."
        _, warnings = validate_skill.validate(self.write_skill(description=description))
        self.assertTrue(any("250" in warning for warning in warnings), warnings)


if __name__ == "__main__":
    unittest.main()
