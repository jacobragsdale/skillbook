import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mcp import Client
from mcp.types import TextContent, TextResourceContents

from skillbook_mcp.catalog import SkillCatalog, SkillDocument, SkillSummary
from skillbook_mcp.server import create_app, create_mcp_server


def _catalog(tmp_path: Path) -> SkillCatalog:
    skill_dir = tmp_path / "demo"
    references = skill_dir / "references"
    references.mkdir(parents=True)
    _ = (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: Use the demo skill.\n---\n\n# Demo\n", encoding="utf-8")
    _ = (references / "details.md").write_text("# Details\n", encoding="utf-8")
    return SkillCatalog(tmp_path)


@pytest.mark.asyncio
async def test_mcp_exposes_tools_and_resources(tmp_path: Path) -> None:
    server = create_mcp_server(_catalog(tmp_path))

    async with Client(server, raise_exceptions=True) as client:
        tools = await client.list_tools()
        assert [tool.name for tool in tools.tools] == ["list_skills", "read_skill", "read_skill_file"]

        listed = await client.call_tool("list_skills", {})
        summaries: list[SkillSummary] = []
        for listed_content in listed.content:
            assert isinstance(listed_content, TextContent)
            summaries.append(SkillSummary.model_validate_json(listed_content.text, strict=True))
        assert [summary.name for summary in summaries] == ["demo"]

        read = await client.call_tool("read_skill", {"name": "demo"})
        document = SkillDocument.model_validate_json(json.dumps(read.structured_content), strict=True)
        assert document.summary.description == "Use the demo skill."
        assert document.files == ("SKILL.md", "references/details.md")

        resources = await client.list_resources()
        assert [(resource.name, resource.uri) for resource in resources.resources] == [("skill_catalog", "skills://catalog")]

        templates = await client.list_resource_templates()
        assert [template.uri_template for template in templates.resource_templates] == ["skill://{name}", "skill-file://{name}/{+path}"]

        document_result = await client.read_resource("skill://demo")
        document = document_result.contents[0]
        assert isinstance(document, TextResourceContents)
        assert document.text.endswith("# Demo\n")

        file_result = await client.read_resource("skill-file://demo/references/details.md")
        skill_file = file_result.contents[0]
        assert isinstance(skill_file, TextResourceContents)
        assert skill_file.text == "# Details\n"


def test_fastapi_health_checks_the_live_catalog(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    app = create_app(create_mcp_server(catalog), catalog)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "skills": 1}
