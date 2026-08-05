from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from re import fullmatch

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

_MEDIA_TYPES = {"json": "application/json", "md": "text/markdown", "mjs": "text/javascript", "py": "text/x-python", "toml": "application/toml", "yaml": "application/yaml", "yml": "application/yaml"}


class CatalogError(ValueError):
    """Raised for unsafe or invalid catalog entries."""


class _Model(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, validate_default=True, revalidate_instances="always", allow_inf_nan=False)


class SkillFrontmatter(_Model):
    name: str
    description: str
    license: str | None = None
    compatibility: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    allowed_tools: str | None = Field(default=None, alias="allowed-tools")
    disable_model_invocation: bool = Field(default=False, alias="disable-model-invocation")


class SkillSummary(_Model):
    name: str
    description: str
    uri: str
    sha256: str
    compatibility: str | None
    model_invocation_enabled: bool


class SkillDocument(_Model):
    summary: SkillSummary
    content: str
    files: tuple[str, ...]


class SkillFile(_Model):
    skill: str
    path: str
    media_type: str
    sha256: str
    content: str


@dataclass(frozen=True, slots=True)
class SkillCatalog:
    root: Path

    def list_skills(self) -> list[SkillSummary]:
        names = sorted(path.name for path in self._resolved_root().iterdir() if path.is_dir() and (path / "SKILL.md").is_file())
        return [self.read_skill(name).summary for name in names]

    def read_skill(self, name: str) -> SkillDocument:
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
        skill_dir = self._skill_dir(name)
        relative_path = _validated_relative_path(path)
        candidate = _resolve(skill_dir / relative_path, f"unknown skill file: {name}/{relative_path.as_posix()}")
        if not candidate.is_relative_to(skill_dir):
            message = f"skill file path escapes {name!r}: {path!r}"
            raise CatalogError(message)
        if not candidate.is_file():
            message = f"skill file is not a regular file: {name}/{path}"
            raise CatalogError(message)

        content = self._read_text(candidate)
        return SkillFile(skill=name, path=relative_path.as_posix(), media_type=_MEDIA_TYPES.get(candidate.suffix.lower()[1:], "text/plain"), sha256=_digest(content), content=content)

    def _resolved_root(self) -> Path:
        root = _resolve(self.root, f"skills root does not exist: {self.root}")
        if not root.is_dir():
            message = f"skills root is not a directory: {root}"
            raise CatalogError(message)
        return root

    def _skill_dir(self, name: str) -> Path:
        if fullmatch(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", name) is None:
            message = f"invalid skill name: {name!r}"
            raise CatalogError(message)

        root = self._resolved_root()
        skill_dir = _resolve(root / name, f"unknown skill: {name!r}")
        if not skill_dir.is_relative_to(root):
            message = f"skill directory escapes the catalog root: {name!r}"
            raise CatalogError(message)
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").is_file():
            message = f"invalid skill directory: {name!r}"
            raise CatalogError(message)
        return skill_dir

    def _list_files(self, skill_dir: Path) -> tuple[str, ...]:
        return tuple(sorted(candidate.relative_to(skill_dir).as_posix() for candidate in skill_dir.rglob("*") if _is_safe_file(candidate, skill_dir)))

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            message = f"skill file is not UTF-8 text: {path}"
            raise CatalogError(message) from error

    @staticmethod
    def _parse_frontmatter(content: str, *, source: Path) -> SkillFrontmatter:
        if not content.startswith("---\n"):
            message = f"SKILL.md has no opening frontmatter delimiter: {source}"
            raise CatalogError(message)
        raw_frontmatter, delimiter, body = content[4:].partition("\n---")
        if delimiter == "" or body[:1] not in {"", "\n"}:
            message = f"SKILL.md has no closing frontmatter delimiter: {source}"
            raise CatalogError(message)
        try:
            return SkillFrontmatter.model_validate(yaml.safe_load(raw_frontmatter), strict=True)
        except ValidationError as error:
            message = f"invalid SKILL.md frontmatter in {source}: {error}"
            raise CatalogError(message) from error


def _validated_relative_path(path: str) -> PurePosixPath:
    if path == "" or "\\" in path or path.startswith("/") or any(part in {"", ".", ".."} for part in path.split("/")):
        message = f"invalid skill file path: {path!r}"
        raise CatalogError(message)
    return PurePosixPath(path)


def _resolve(path: Path, missing: str) -> Path:
    try:
        return path.resolve(strict=True)
    except FileNotFoundError as error:
        raise CatalogError(missing) from error


def _is_safe_file(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    ignored = any(part in {".ruff_cache", "__pycache__"} for part in relative.parts[:-1]) or path.name == ".DS_Store" or path.suffix == ".pyc"
    try:
        return not ignored and path.is_file() and path.resolve(strict=True).is_relative_to(root)
    except FileNotFoundError:
        return False


def _digest(content: str) -> str:
    return sha256(content.encode()).hexdigest()
