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
    assert (summaries[0].compatibility, summaries[0].model_invocation_enabled, summaries[0].uri, len(summaries[0].sha256)) == ("Needs a demo runtime.", False, "skill://alpha", 64)


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

    assert (skill_file.skill, skill_file.path, skill_file.media_type, skill_file.content) == ("demo", "references/details.md", "text/markdown", "# Details\n")


@pytest.mark.parametrize("path", ["../secret.txt", "/etc/passwd", "..\\secret.txt"])
def test_read_file_rejects_paths_outside_the_skill(tmp_path: Path, path: str) -> None:
    _ = _write_skill(tmp_path, "demo")

    with pytest.raises(CatalogError, match="invalid skill file path"):
        _ = SkillCatalog(tmp_path).read_file("demo", path)


@pytest.mark.parametrize(
    ("frontmatter", "match"), [("---\nname: another\ndescription: mismatch\n---\n", "does not match directory"), ("---\nname: demo\ndescription: 123\n---\n", r"invalid SKILL\.md frontmatter")]
)
def test_read_skill_rejects_invalid_frontmatter(tmp_path: Path, frontmatter: str, match: str) -> None:
    skill_dir = _write_skill(tmp_path, "demo")
    _ = (skill_dir / "SKILL.md").write_text(frontmatter, encoding="utf-8")

    with pytest.raises(CatalogError, match=match):
        _ = SkillCatalog(tmp_path).read_skill("demo")


@pytest.mark.parametrize(("path", "content", "match"), [("binary.bin", b"\xff", "not UTF-8 text"), ("references/missing.md", None, "unknown skill file")])
def test_read_file_reports_invalid_content(tmp_path: Path, path: str, content: bytes | None, match: str) -> None:
    skill_dir = _write_skill(tmp_path, "demo")
    if content is not None:
        _ = (skill_dir / path).write_bytes(content)

    with pytest.raises(CatalogError, match=match):
        _ = SkillCatalog(tmp_path).read_file("demo", path)
