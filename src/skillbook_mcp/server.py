import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import FastAPI
from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from skillbook_mcp.catalog import SkillCatalog, SkillDocument, SkillFile

_SKILL_NAME = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", description="Exact skill name returned by list_skills.")]
_SKILL_PATH = Annotated[str, Field(min_length=1, description="POSIX path relative to the skill directory.")]
_READ_ONLY_TOOL = ToolAnnotations(read_only_hint=True, open_world_hint=False)


def create_mcp_server(catalog: SkillCatalog) -> MCPServer[object]:
    server = MCPServer[object](
        name="skillbook",
        title="Skillbook",
        description="Jacob's canonical Agent Skills library.",
        instructions="Call list_skills to discover relevant trigger descriptions. Call read_skill before applying a relevant skill, then call read_skill_file for any supporting path referenced by SKILL.md.",
        version="0.1.0",
    )

    server.add_tool(catalog.list_skills, title="List skills", description="List available skills and the trigger description for each one.", annotations=_READ_ONLY_TOOL)

    @server.tool(title="Read skill", annotations=_READ_ONLY_TOOL)
    def read_skill(name: _SKILL_NAME) -> SkillDocument:
        """Read a selected skill's complete SKILL.md and supporting file names."""
        return catalog.read_skill(name)

    @server.tool(title="Read skill file", annotations=_READ_ONLY_TOOL)
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


def create_app(server: MCPServer[object], catalog: SkillCatalog) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        async with server.session_manager.run():
            yield

    app = FastAPI(title="Skillbook MCP experiment", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str | int]:
        return {"status": "ok", "skills": len(catalog.list_skills())}

    app.mount("/", server.streamable_http_app(json_response=True, stateless_http=True))
    return app


catalog = SkillCatalog(Path(__file__).resolve().parents[2] / "skills")
app = create_app(create_mcp_server(catalog), catalog)


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8000)
