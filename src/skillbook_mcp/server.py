"""FastAPI host and MCP v2 surface for the canonical skillbook."""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import FastAPI
from mcp.server import MCPServer
from pydantic import BaseModel, ConfigDict, Field

from skillbook_mcp.catalog import SkillCatalog, SkillDocument, SkillFile, SkillSummary

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILLS_ROOT = _REPO_ROOT / "skills"
_SKILL_NAME = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", description="Exact skill name returned by list_skills.")]
_SKILL_PATH = Annotated[str, Field(min_length=1, description="POSIX path relative to the skill directory.")]


class HealthResponse(BaseModel):
    """FastAPI health response."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, validate_default=True, revalidate_instances="always", allow_inf_nan=False)

    status: str
    skills: int


class SkillMCPServer(MCPServer[object]):
    """Narrow typed boundary around the SDK server."""


def create_mcp_server(catalog: SkillCatalog) -> SkillMCPServer:
    """Build an MCP v2 server around an injected live catalog."""
    server = SkillMCPServer(
        name="skillbook",
        title="Skillbook",
        description="Jacob's canonical Agent Skills library.",
        instructions=(
            "Call list_skills to discover relevant trigger descriptions. Call read_skill before applying a relevant skill, then call read_skill_file for any supporting path referenced by SKILL.md."
        ),
        version="0.1.0",
    )

    @server.tool()
    def list_skills() -> list[SkillSummary]:
        """List available skills and the trigger description for each one."""
        return catalog.list_skills()

    @server.tool()
    def read_skill(name: _SKILL_NAME) -> SkillDocument:
        """Read a selected skill's complete SKILL.md and supporting file names."""
        return catalog.read_skill(name)

    @server.tool()
    def read_skill_file(name: _SKILL_NAME, path: _SKILL_PATH) -> SkillFile:
        """Read a UTF-8 supporting file referenced by a selected skill."""
        return catalog.read_file(name, path)

    @server.resource("skills://catalog", name="skill_catalog", description="JSON catalog of every available skill and its trigger description.", mime_type="application/json")
    def skill_catalog_resource() -> str:
        return json.dumps([summary.model_dump(mode="json") for summary in catalog.list_skills()], sort_keys=True)

    @server.resource("skill://{name}", name="skill_document", description="Complete SKILL.md for one named skill.", mime_type="text/markdown")
    def skill_document_resource(name: str) -> str:
        return catalog.read_skill(name).content

    @server.resource("skill-file://{name}/{+path}", name="skill_file", description="UTF-8 supporting file inside one named skill directory.", mime_type="text/plain")
    def skill_file_resource(name: str, path: str) -> str:
        return catalog.read_file(name, path).content

    return server


def create_app(server: SkillMCPServer, catalog: SkillCatalog) -> FastAPI:
    """Mount MCP Streamable HTTP in FastAPI with the required shared lifespan."""
    mcp_app = server.streamable_http_app(json_response=True, stateless_http=True)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        async with server.session_manager.run():
            yield

    app = FastAPI(title="Skillbook MCP experiment", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health() -> HealthResponse:
        return HealthResponse(status="ok", skills=len(catalog.list_skills()))

    app.mount("/", mcp_app)
    return app


catalog = SkillCatalog(_SKILLS_ROOT)
mcp = create_mcp_server(catalog)
app = create_app(mcp, catalog)


def main() -> None:
    """Run the local experiment on its documented address."""
    uvicorn.run(app, host="127.0.0.1", port=8000)
