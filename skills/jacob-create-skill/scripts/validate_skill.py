#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Validate Agent Skills core fields, target extensions, and house rules.

Errors (exit 1) are invalid for the selected profile. Warnings require a
deliberate decision but do not change the exit code.

Usage: validate_skill.py [--profile house|core|cursor|claude|codex] <skill-dir> [...]
"""

import argparse
import json
import re
from pathlib import Path

import yaml

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LOCAL_REF_RE = re.compile(r"\b((?:scripts|references|assets)/[A-Za-z0-9_.\-/]+)")

CORE_FIELDS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}
CURSOR_FIELDS = {"paths", "disable-model-invocation"}
CLAUDE_FIELDS = {
    "when_to_use",
    "argument-hint",
    "arguments",
    "disable-model-invocation",
    "user-invocable",
    "disallowed-tools",
    "model",
    "effort",
    "context",
    "agent",
    "hooks",
    "paths",
    "shell",
}
PROFILE_FIELDS = {
    "core": CORE_FIELDS,
    "cursor": CORE_FIELDS | CURSOR_FIELDS,
    "claude": CORE_FIELDS | CLAUDE_FIELDS,
    "codex": CORE_FIELDS,
    "house": CORE_FIELDS | CURSOR_FIELDS | CLAUDE_FIELDS,
}

BODY_WARN_LINES = 300
BODY_MAX_LINES = 500
DESCRIPTION_MAX = 1024
COMPATIBILITY_MAX = 500
ROUTER_VISIBLE_CHARS = 250


def parse_frontmatter(text: str) -> tuple[dict | None, str, str | None]:
    """Return (frontmatter, body, error)."""
    if not text.startswith("---\n"):
        return None, text, "SKILL.md does not start with '---' frontmatter"
    end = text.find("\n---", 4)
    if end == -1:
        return None, text, "frontmatter is not closed with '---'"
    raw = text[4:end]
    body = text[end + 4 :].lstrip("\n")
    try:
        fm = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return None, body, f"frontmatter is not valid YAML: {exc}"
    if not isinstance(fm, dict):
        return None, body, "frontmatter is not a YAML mapping"
    return fm, body, None


def strip_fenced_code(markdown: str) -> str:
    """Remove fenced blocks so illustrative paths are not validated as files."""
    kept: list[str] = []
    fence: str | None = None
    for line in markdown.splitlines():
        stripped = line.lstrip()
        marker = stripped[:3]
        if fence is None and marker in {"```", "~~~"}:
            fence = marker
            continue
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        kept.append(line)
    return "\n".join(kept)


def validate_openai_yaml(
    skill_dir: Path, skill_name: str | None
) -> tuple[list[str], list[str]]:
    """Validate the Codex sidecar fields this scaffolder creates or documents."""
    errors: list[str] = []
    warnings: list[str] = []
    path = skill_dir / "agents" / "openai.yaml"
    if not path.exists():
        return errors, warnings
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [f"agents/openai.yaml is not valid YAML: {exc}"], warnings
    if not isinstance(data, dict):
        return ["agents/openai.yaml is not a YAML mapping"], warnings

    policy = data.get("policy")
    if policy is not None:
        if not isinstance(policy, dict):
            errors.append("agents/openai.yaml policy must be a mapping")
        elif "allow_implicit_invocation" in policy and not isinstance(
            policy["allow_implicit_invocation"], bool
        ):
            errors.append(
                "agents/openai.yaml policy.allow_implicit_invocation must be boolean"
            )

    interface = data.get("interface")
    if interface is not None and not isinstance(interface, dict):
        errors.append("agents/openai.yaml interface must be a mapping")
    elif isinstance(interface, dict):
        prompt = interface.get("default_prompt")
        if prompt is not None and not isinstance(prompt, str):
            errors.append(
                "agents/openai.yaml interface.default_prompt must be a string"
            )
        elif prompt and skill_name and f"${skill_name}" not in prompt:
            warnings.append(
                f"agents/openai.yaml default_prompt should mention ${skill_name} explicitly"
            )
    return errors, warnings


def codex_implicit_invocation_disabled(skill_dir: Path) -> bool:
    """Return whether the Codex sidecar explicitly disables implicit invocation."""
    path = skill_dir / "agents" / "openai.yaml"
    if not path.is_file():
        return False
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return False
    return (
        isinstance(data, dict)
        and isinstance(data.get("policy"), dict)
        and data["policy"].get("allow_implicit_invocation") is False
    )


def validate_evals(
    skill_dir: Path, skill_name: str | None
) -> tuple[list[str], list[str]]:
    """Validate the lightweight eval manifest when a skill includes one."""
    path = skill_dir / "evals" / "evals.json"
    if not path.exists():
        return [], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"evals/evals.json is not valid JSON: {exc}"], []
    if not isinstance(data, dict):
        return ["evals/evals.json must be a JSON object"], []

    errors: list[str] = []
    warnings: list[str] = []
    if skill_name and data.get("skill_name") != skill_name:
        errors.append("evals/evals.json skill_name must match SKILL.md name")
    evals = data.get("evals")
    if not isinstance(evals, list) or not evals:
        return errors + ["evals/evals.json evals must be a non-empty list"], warnings
    if len(evals) < 2:
        warnings.append("evals/evals.json has fewer than two task cases")
    for index, case in enumerate(evals, start=1):
        label = f"evals/evals.json case {index}"
        if not isinstance(case, dict):
            errors.append(f"{label} must be an object")
            continue
        if not isinstance(case.get("id"), (str, int)):
            errors.append(f"{label} needs a string or integer id")
        for field in ("prompt", "expected_output"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                errors.append(f"{label} needs a non-empty {field} string")
        files = case.get("files")
        if files is not None and not (
            isinstance(files, list) and all(isinstance(item, str) for item in files)
        ):
            errors.append(f"{label} files must be a list of strings")
    return errors, warnings


def validate_trigger_queries(skill_dir: Path) -> tuple[list[str], list[str]]:
    """Validate the six-message routing manifest when present."""
    path = skill_dir / "evals" / "trigger_queries.json"
    if not path.exists():
        return [], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"evals/trigger_queries.json is not valid JSON: {exc}"], []
    if not isinstance(data, list):
        return ["evals/trigger_queries.json must be a JSON list"], []

    errors: list[str] = []
    positives = 0
    negatives = 0
    for index, case in enumerate(data, start=1):
        label = f"evals/trigger_queries.json case {index}"
        if not isinstance(case, dict):
            errors.append(f"{label} must be an object")
            continue
        if not isinstance(case.get("query"), str) or not case["query"].strip():
            errors.append(f"{label} needs a non-empty query string")
        should_trigger = case.get("should_trigger")
        if not isinstance(should_trigger, bool):
            errors.append(f"{label} should_trigger must be boolean")
        elif should_trigger:
            positives += 1
        else:
            negatives += 1
    if positives < 3 or negatives < 3:
        errors.append(
            "evals/trigger_queries.json needs at least three should-trigger and three near-miss cases"
        )
    return errors, []


def validate_python_header(path: Path, skill_dir: Path) -> str | None:
    """Return an error when a bundled Python file is not a complete PEP 723 script."""
    lines = path.read_text(encoding="utf-8").splitlines()[:30]
    rel = path.relative_to(skill_dir)
    if not lines or lines[0] != "#!/usr/bin/env -S uv run --script":
        return f"{rel} must start with '#!/usr/bin/env -S uv run --script'"
    try:
        start = lines.index("# /// script")
        end = lines.index("# ///", start + 1)
    except ValueError:
        return f"{rel} lacks a complete PEP 723 '# /// script' metadata block"
    block = lines[start + 1 : end]
    if not any(line.startswith("# requires-python =") for line in block):
        return f"{rel} PEP 723 block lacks requires-python"
    if not any(line.startswith("# dependencies =") for line in block):
        return f"{rel} PEP 723 block lacks dependencies"
    return None


def validate(skill_dir: Path, profile: str = "house") -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [f"no SKILL.md in {skill_dir}"], []

    fm, body, fm_error = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    if fm_error:
        errors.append(fm_error)
    fm = fm or {}

    name = fm.get("name")
    if not name:
        errors.append("frontmatter missing required field: name")
    elif not isinstance(name, str) or not NAME_RE.fullmatch(name) or len(name) > 64:
        errors.append(
            f"invalid name {name!r}: need lowercase alphanumerics/single hyphens, max 64 chars"
        )
    elif name != skill_dir.name:
        errors.append(f"name {name!r} does not match folder name {skill_dir.name!r}")

    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        errors.append("frontmatter missing required field: description")
    else:
        if len(desc) > DESCRIPTION_MAX:
            errors.append(f"description is {len(desc)} chars (max {DESCRIPTION_MAX})")
        if desc.lstrip().startswith("TODO:"):
            errors.append("description still contains the scaffold TODO")
        if len(desc) < 60:
            warnings.append("description under 60 chars — likely too thin to route on")
        use_when = desc.lower().find("use when")
        if use_when == -1:
            warnings.append(
                "description has no 'Use when ...' clause — write it as a trigger"
            )
        elif use_when >= ROUTER_VISIBLE_CHARS:
            warnings.append(
                f"'Use when' starts at char {use_when}; house routing budget is {ROUTER_VISIBLE_CHARS} chars"
            )

    allowed_fields = PROFILE_FIELDS[profile]
    for field in fm:
        if field not in allowed_fields:
            if profile == "codex" and field == "disable-model-invocation":
                continue
            message = (
                f"frontmatter field {field!r} is unsupported by profile {profile!r}"
            )
            if profile == "core":
                errors.append(message)
            else:
                warnings.append(message)

    license_value = fm.get("license")
    if license_value is not None and (
        not isinstance(license_value, str) or not license_value.strip()
    ):
        errors.append("license must be a non-empty string when provided")

    compatibility = fm.get("compatibility")
    if compatibility is not None:
        if not isinstance(compatibility, str) or not compatibility.strip():
            errors.append("compatibility must be a non-empty string when provided")
        elif len(compatibility) > COMPATIBILITY_MAX:
            errors.append(
                f"compatibility is {len(compatibility)} chars (max {COMPATIBILITY_MAX})"
            )

    metadata = fm.get("metadata")
    if metadata is not None and (
        not isinstance(metadata, dict)
        or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in metadata.items()
        )
    ):
        errors.append("metadata must map string keys to string values")

    allowed_tools = fm.get("allowed-tools")
    if allowed_tools is not None:
        string_list = isinstance(allowed_tools, list) and all(
            isinstance(item, str) for item in allowed_tools
        )
        if profile == "core" and not isinstance(allowed_tools, str):
            errors.append("core allowed-tools must be a space-separated string")
        elif not isinstance(allowed_tools, str) and not string_list:
            errors.append("allowed-tools must be a string or a list of strings")

    for field in ("paths", "arguments", "disallowed-tools"):
        value = fm.get(field)
        if value is not None and not (
            isinstance(value, str)
            or isinstance(value, list)
            and all(isinstance(item, str) for item in value)
        ):
            errors.append(f"{field} must be a string or a list of strings")

    for field in ("disable-model-invocation", "user-invocable"):
        value = fm.get(field)
        if value is not None and not isinstance(value, bool):
            errors.append(f"{field} must be boolean")

    if (
        profile in {"house", "cursor", "claude"}
        and fm.get("disable-model-invocation") is not True
    ):
        warnings.append(
            "disable-model-invocation is not true — house default is explicit-only; "
            "confirm automatic invocation was requested"
        )
    if (
        profile == "codex"
        and fm.get("disable-model-invocation") is True
        and not codex_implicit_invocation_disabled(skill_dir)
    ):
        warnings.append(
            "disable-model-invocation does not control Codex; add agents/openai.yaml "
            "policy.allow_implicit_invocation: false to preserve explicit-only behavior"
        )

    if not body.strip():
        errors.append("SKILL.md body is empty")
    if "<!-- TODO:" in body:
        errors.append("SKILL.md still contains scaffold TODO comments")

    body_lines = body.count("\n") + 1 if body else 0
    if body_lines > BODY_MAX_LINES:
        errors.append(f"body is {body_lines} lines (max {BODY_MAX_LINES})")
    elif body_lines > BODY_WARN_LINES:
        warnings.append(
            f"body is {body_lines} lines (house target < {BODY_WARN_LINES}) — move conditional detail to references"
        )

    searchable_body = strip_fenced_code(body)
    for ref in sorted(set(LOCAL_REF_RE.findall(searchable_body))):
        ref = ref.rstrip(".,;:")
        if not (skill_dir / ref).exists():
            warnings.append(f"body references {ref} but the file does not exist")

    for py_file in sorted(skill_dir.rglob("*.py")):
        header_error = validate_python_header(py_file, skill_dir)
        if header_error:
            errors.append(header_error)

    if not (skill_dir / "LEARNINGS.md").is_file():
        warnings.append("no LEARNINGS.md — the skill has no house learnings loop")
    if "learnings.md" not in body.lower():
        warnings.append(
            "body never mentions LEARNINGS.md — agents will not read or update it"
        )

    codex_errors, codex_warnings = validate_openai_yaml(
        skill_dir, name if isinstance(name, str) else None
    )
    errors.extend(codex_errors)
    warnings.extend(codex_warnings)
    eval_errors, eval_warnings = validate_evals(
        skill_dir, name if isinstance(name, str) else None
    )
    errors.extend(eval_errors)
    warnings.extend(eval_warnings)
    trigger_errors, trigger_warnings = validate_trigger_queries(skill_dir)
    errors.extend(trigger_errors)
    warnings.extend(trigger_warnings)
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILE_FIELDS),
        default="house",
        help="frontmatter compatibility profile (default: house union)",
    )
    parser.add_argument(
        "skill_dirs", nargs="+", type=Path, help="skill folder(s) to validate"
    )
    args = parser.parse_args()

    exit_code = 0
    for skill_dir in args.skill_dirs:
        errors, warnings = validate(skill_dir, profile=args.profile)
        print(f"\n{skill_dir} [{args.profile}]")
        for error in errors:
            print(f"  ERROR: {error}")
        for warning in warnings:
            print(f"  WARN:  {warning}")
        if not errors and not warnings:
            print("  OK")
        elif not errors:
            print(f"  OK with {len(warnings)} warning(s)")
        else:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
