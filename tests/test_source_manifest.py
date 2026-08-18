from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO / "skill-manager.json"


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


def _kind(component: dict[str, object]) -> str | None:
    kind = component.get("kind")
    if kind == "skill":
        return kind
    return None


def _canonical_skill_directories() -> set[Path]:
    return {path.parent for path in REPO.glob("skills/*/SKILL.md")}


def _classify(package: dict[str, object]) -> str:
    kinds = [_kind(component) for component in _components(package)]
    present = {kind for kind in kinds if kind is not None}
    if present == {"skill"}:
        return "skill" if len(kinds) == 1 else "skill-bundle"
    return "unknown"


def test_manifest_is_v2_with_published_package_shapes() -> None:
    manifest = _load_manifest()
    source = manifest.get("source")
    assert manifest.get("version") == 2
    assert isinstance(source, dict)
    assert source.get("id") == "skillbook"

    shapes = {_classify(package) for package in _packages(manifest)}
    assert shapes == {"skill", "skill-bundle"}


def test_manifest_contains_only_agent_skills() -> None:
    for package in _packages(_load_manifest()):
        components = _components(package)
        assert components
        for component in components:
            assert component.get("kind") == "skill"
            path = component.get("path")
            assert isinstance(path, str)
            assert path.startswith("skills/")


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
