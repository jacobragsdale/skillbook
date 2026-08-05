"""Behavior tests for the live skill catalog."""

from pathlib import Path

import pytest

from skillbook_mcp.catalog import CatalogError, SkillCatalog


def _write_skill(root: Path, name: str, *, description: str = "Use this demo skill.", extra_frontmatter: str = "") -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    _ = (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n{extra_frontmatter}---\n\n# {name}\n", encoding="utf-8")
    return skill_dir


def test_catalog_lists_valid_skills_in_name_order(tmp_path: Path) -> None:
    _ = _write_skill(tmp_path, "zeta")
    _ = _write_skill(tmp_path, "alpha", extra_frontmatter=('compatibility: "Needs a demo runtime."\ndisable-model-invocation: true\n'))

    summaries = SkillCatalog(tmp_path).list_skills()

    assert [summary.name for summary in summaries] == ["alpha", "zeta"]
    assert summaries[0].compatibility == "Needs a demo runtime."
    assert summaries[0].model_invocation_enabled is False
    assert summaries[0].uri == "skill://alpha"
    assert len(summaries[0].sha256) == 64


def test_read_skill_returns_content_and_supporting_files(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "demo")
    references = skill_dir / "references"
    references.mkdir()
    _ = (references / "details.md").write_text("# Details\n", encoding="utf-8")
    cache = skill_dir / "__pycache__"
    cache.mkdir()
    _ = (cache / "ignored.pyc").write_bytes(b"not served")

    document = SkillCatalog(tmp_path).read_skill("demo")

    assert document.content.endswith("# demo\n")
    assert document.files == ("SKILL.md", "references/details.md")


def test_read_file_returns_typed_utf8_content(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "demo")
    references = skill_dir / "references"
    references.mkdir()
    _ = (references / "details.md").write_text("# Details\n", encoding="utf-8")

    skill_file = SkillCatalog(tmp_path).read_file("demo", "references/details.md")

    assert skill_file.skill == "demo"
    assert skill_file.path == "references/details.md"
    assert skill_file.media_type == "text/markdown"
    assert skill_file.content == "# Details\n"


@pytest.mark.parametrize("path", ["../secret.txt", "/etc/passwd", "..\\secret.txt"])
def test_read_file_rejects_paths_outside_the_skill(tmp_path: Path, path: str) -> None:
    _ = _write_skill(tmp_path, "demo")

    with pytest.raises(CatalogError, match="invalid skill file path"):
        _ = SkillCatalog(tmp_path).read_file("demo", path)


def test_frontmatter_name_must_match_the_directory(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "demo")
    _ = (skill_dir / "SKILL.md").write_text("---\nname: another\ndescription: mismatch\n---\n", encoding="utf-8")

    with pytest.raises(CatalogError, match="does not match directory"):
        _ = SkillCatalog(tmp_path).read_skill("demo")


def test_frontmatter_uses_strict_field_types(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "demo")
    _ = (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: 123\n---\n", encoding="utf-8")

    with pytest.raises(CatalogError, match=r"invalid SKILL\.md frontmatter"):
        _ = SkillCatalog(tmp_path).read_skill("demo")


def test_read_file_rejects_non_utf8_assets(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "demo")
    _ = (skill_dir / "binary.bin").write_bytes(b"\xff")

    with pytest.raises(CatalogError, match="not UTF-8 text"):
        _ = SkillCatalog(tmp_path).read_file("demo", "binary.bin")


def test_read_file_reports_an_unknown_supporting_file(tmp_path: Path) -> None:
    _ = _write_skill(tmp_path, "demo")

    with pytest.raises(CatalogError, match="unknown skill file"):
        _ = SkillCatalog(tmp_path).read_file("demo", "references/missing.md")
