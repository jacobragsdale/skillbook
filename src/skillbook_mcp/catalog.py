"""Live, validated access to the canonical skill directories."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from re import Pattern
from re import compile as compile_pattern

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

_MODEL_CONFIG = ConfigDict(strict=True, extra="forbid", frozen=True, validate_default=True, revalidate_instances="always", allow_inf_nan=False)
_SKILL_NAME_PATTERN: Pattern[str] = compile_pattern(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_IGNORED_DIRECTORY_NAMES = frozenset({".ruff_cache", "__pycache__"})
_IGNORED_FILE_NAMES = frozenset({".DS_Store"})
_IGNORED_SUFFIXES = frozenset({".pyc"})
_MEDIA_TYPES = {
    ".json": "application/json",
    ".md": "text/markdown",
    ".mjs": "text/javascript",
    ".py": "text/x-python",
    ".toml": "application/toml",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
}


class CatalogError(ValueError):
    """Raised when a skill catalog entry cannot be served safely."""


class SkillFrontmatter(BaseModel):
    """Supported Agent Skills frontmatter fields."""

    model_config = _MODEL_CONFIG

    name: str
    description: str
    license: str | None = None
    compatibility: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    allowed_tools: str | None = Field(default=None, alias="allowed-tools")
    disable_model_invocation: bool = Field(default=False, alias="disable-model-invocation")


class SkillSummary(BaseModel):
    """Catalog metadata returned to MCP clients."""

    model_config = _MODEL_CONFIG

    name: str
    description: str
    uri: str
    sha256: str
    compatibility: str | None
    model_invocation_enabled: bool


class SkillDocument(BaseModel):
    """A complete SKILL.md document and its supporting file names."""

    model_config = _MODEL_CONFIG

    summary: SkillSummary
    content: str
    files: tuple[str, ...]


class SkillFile(BaseModel):
    """A UTF-8 supporting file from a skill directory."""

    model_config = _MODEL_CONFIG

    skill: str
    path: str
    media_type: str
    sha256: str
    content: str


@dataclass(frozen=True, slots=True)
class SkillCatalog:
    """Read validated skills directly from disk on every request."""

    root: Path

    def list_skills(self) -> list[SkillSummary]:
        """Return every valid skill in deterministic name order."""
        root = self._resolved_root()
        names = sorted(path.name for path in root.iterdir() if path.is_dir() and (path / "SKILL.md").is_file())
        return [self.read_skill(name).summary for name in names]

    def read_skill(self, name: str) -> SkillDocument:
        """Read one SKILL.md and list the files available beside it."""
        skill_dir = self._skill_dir(name)
        skill_path = skill_dir / "SKILL.md"
        content = self._read_text(skill_path)
        frontmatter = self._parse_frontmatter(content, source=skill_path)
        if frontmatter.name != name:
            message = f"frontmatter name {frontmatter.name!r} does not match directory {name!r}"
            raise CatalogError(message)

        summary = SkillSummary(
            name=name,
            description=frontmatter.description,
            uri=f"skill://{name}",
            sha256=_digest(content),
            compatibility=frontmatter.compatibility,
            model_invocation_enabled=not frontmatter.disable_model_invocation,
        )
        return SkillDocument(summary=summary, content=content, files=self._list_files(skill_dir))

    def read_file(self, name: str, path: str) -> SkillFile:
        """Read one UTF-8 file without allowing escape from its skill directory."""
        skill_dir = self._skill_dir(name)
        relative_path = _validated_relative_path(path)
        try:
            candidate = (skill_dir / relative_path).resolve(strict=True)
        except FileNotFoundError as error:
            message = f"unknown skill file: {name}/{relative_path.as_posix()}"
            raise CatalogError(message) from error
        try:
            _ = candidate.relative_to(skill_dir)
        except ValueError as error:
            message = f"skill file path escapes {name!r}: {path!r}"
            raise CatalogError(message) from error
        if not candidate.is_file():
            message = f"skill file is not a regular file: {name}/{path}"
            raise CatalogError(message)

        content = self._read_text(candidate)
        return SkillFile(skill=name, path=relative_path.as_posix(), media_type=_MEDIA_TYPES.get(candidate.suffix.lower(), "text/plain"), sha256=_digest(content), content=content)

    def _resolved_root(self) -> Path:
        try:
            root = self.root.resolve(strict=True)
        except FileNotFoundError as error:
            message = f"skills root does not exist: {self.root}"
            raise CatalogError(message) from error
        if not root.is_dir():
            message = f"skills root is not a directory: {root}"
            raise CatalogError(message)
        return root

    def _skill_dir(self, name: str) -> Path:
        if _SKILL_NAME_PATTERN.fullmatch(name) is None:
            message = f"invalid skill name: {name!r}"
            raise CatalogError(message)

        root = self._resolved_root()
        try:
            skill_dir = (root / name).resolve(strict=True)
        except FileNotFoundError as error:
            message = f"unknown skill: {name!r}"
            raise CatalogError(message) from error
        try:
            _ = skill_dir.relative_to(root)
        except ValueError as error:
            message = f"skill directory escapes the catalog root: {name!r}"
            raise CatalogError(message) from error
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").is_file():
            message = f"invalid skill directory: {name!r}"
            raise CatalogError(message)
        return skill_dir

    def _list_files(self, skill_dir: Path) -> tuple[str, ...]:
        files: list[str] = []
        for candidate in skill_dir.rglob("*"):
            relative_path = candidate.relative_to(skill_dir)
            if _is_ignored(relative_path) or not candidate.is_file():
                continue
            try:
                _ = candidate.resolve(strict=True).relative_to(skill_dir)
            except (FileNotFoundError, ValueError):
                continue
            files.append(relative_path.as_posix())
        return tuple(sorted(files))

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            message = f"skill file is not UTF-8 text: {path}"
            raise CatalogError(message) from error

    @staticmethod
    def _parse_frontmatter(content: str, *, source: Path) -> SkillFrontmatter:
        lines = content.splitlines()
        if len(lines) == 0 or lines[0] != "---":
            message = f"SKILL.md has no opening frontmatter delimiter: {source}"
            raise CatalogError(message)
        try:
            closing_index = lines.index("---", 1)
        except ValueError as error:
            message = f"SKILL.md has no closing frontmatter delimiter: {source}"
            raise CatalogError(message) from error

        raw_frontmatter: object = yaml.safe_load("\n".join(lines[1:closing_index]))
        try:
            return SkillFrontmatter.model_validate(raw_frontmatter, strict=True)
        except ValidationError as error:
            message = f"invalid SKILL.md frontmatter in {source}: {error}"
            raise CatalogError(message) from error


def _validated_relative_path(path: str) -> PurePosixPath:
    if path == "" or "\\" in path:
        message = f"invalid skill file path: {path!r}"
        raise CatalogError(message)
    relative_path = PurePosixPath(path)
    if relative_path.is_absolute() or any(part in {"", ".", ".."} for part in relative_path.parts):
        message = f"invalid skill file path: {path!r}"
        raise CatalogError(message)
    return relative_path


def _is_ignored(path: Path) -> bool:
    return any(part in _IGNORED_DIRECTORY_NAMES for part in path.parts[:-1]) or path.name in _IGNORED_FILE_NAMES or path.suffix in _IGNORED_SUFFIXES


def _digest(content: str) -> str:
    return sha256(content.encode()).hexdigest()
