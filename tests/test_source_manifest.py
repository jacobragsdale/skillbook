from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import pytest

REPO = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO / "skill-manager.json"
ComponentKind = Literal["skill", "mcpServer"]


def _load_manifest() -> dict[str, object]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        message = "skill-manager.json must be a JSON object."
        raise TypeError(message)
    return payload


def _packages(manifest: dict[str, object]) -> list[dict[str, object]]:
    packages = manifest.get("packages")
    if not isinstance(packages, list) or not packages:
        message = "skill-manager.json must declare one or more packages."
        raise TypeError(message)
    return [package for package in packages if isinstance(package, dict)]


def _components(package: dict[str, object]) -> list[dict[str, object]]:
    components = package.get("components")
    if not isinstance(components, list):
        return []
    return [component for component in components if isinstance(component, dict)]


def _kind(component: dict[str, object]) -> ComponentKind | None:
    kind = component.get("kind")
    if kind in {"skill", "mcpServer"}:
        return kind
    return None


def _component_paths(kind: ComponentKind) -> list[Path]:
    paths: set[Path] = set()
    for package in _packages(_load_manifest()):
        for component in _components(package):
            if _kind(component) != kind:
                continue
            path = component.get("path")
            if isinstance(path, str):
                paths.add(REPO / path)
    return sorted(paths)


def _canonical_skill_directories() -> set[Path]:
    return {path.parent for path in REPO.glob("skills/*/SKILL.md")}


def _plugin_skill_directories() -> set[Path]:
    return {path.parent for path in REPO.glob("plugins/*/skills/*/SKILL.md")}


def _packages_for_skill(skill_dir: Path) -> list[dict[str, object]]:
    resolved = skill_dir.resolve()
    homes: list[dict[str, object]] = []
    for package in _packages(_load_manifest()):
        for component in _components(package):
            if _kind(component) != "skill":
                continue
            path = component.get("path")
            if isinstance(path, str) and (REPO / path).resolve() == resolved:
                homes.append(package)
                break
    return homes


def _classify(package: dict[str, object]) -> str:
    kinds = [_kind(component) for component in _components(package)]
    present = {kind for kind in kinds if kind is not None}
    if present == {"skill"}:
        return "skill" if len(kinds) == 1 else "skill-bundle"
    if present == {"mcpServer"}:
        return "mcp" if len(kinds) == 1 else "mcp-bundle"
    if present == {"skill", "mcpServer"}:
        return "mixed"
    return "unknown"


def test_manifest_is_v2_with_every_package_shape() -> None:
    manifest = _load_manifest()
    source = manifest.get("source")
    assert manifest.get("version") == 2
    assert isinstance(source, dict)
    assert source.get("id") == "skillbook"

    shapes = {_classify(package) for package in _packages(manifest)}
    assert shapes == {"skill", "mcp", "skill-bundle", "mcp-bundle", "mixed"}


def test_canonical_skills_have_a_standalone_package() -> None:
    standalone = set()
    for package in _packages(_load_manifest()):
        components = _components(package)
        if len(components) != 1 or _kind(components[0]) != "skill":
            continue
        path = components[0].get("path")
        if isinstance(path, str):
            standalone.add((REPO / path).resolve())

    missing = sorted(path.relative_to(REPO).as_posix() for path in _canonical_skill_directories() if path.resolve() not in standalone)
    assert missing == []


def test_plugin_skills_appear_only_in_their_plugin_package() -> None:
    for skill_dir in sorted(_plugin_skill_directories()):
        homes = _packages_for_skill(skill_dir)
        home_ids = [package.get("id") for package in homes]
        assert len(homes) == 1, f"{skill_dir.relative_to(REPO).as_posix()} appears in {home_ids}"
        components = _components(homes[0])
        assert len(components) > 1, f"{home_ids[0]} must be the plugin package, not a standalone card"


@pytest.mark.parametrize("path", list(_component_paths("mcpServer")))
def test_referenced_mcp_documents_are_portable(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    text = path.read_text(encoding="utf-8")
    assert payload.get("$schema") == "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
    assert payload.get("mcpServers")
    assert "${PLUGIN_ROOT}" not in text
    assert "${PLUGIN_DATA}" not in text
