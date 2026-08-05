import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mcp import Client
from mcp.types import DiscoverResult, JSONRPCError, TextContent, TextResourceContents, ToolAnnotations

from skillbook_mcp.catalog import SkillCatalog, SkillDocument, SkillSummary
from skillbook_mcp.server import create_app, create_mcp_server


def _catalog(tmp_path: Path) -> SkillCatalog:
    skill_dir = tmp_path / "demo"
    references = skill_dir / "references"
    references.mkdir(parents=True)
    _ = (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: Use the demo skill.\n---\n\n# Demo\n", encoding="utf-8")
    _ = (references / "details.md").write_text("# Details\n", encoding="utf-8")
    return SkillCatalog(tmp_path)


def _discover_request() -> dict[str, object]:
    client_capabilities: dict[str, object] = {}
    metadata: dict[str, object] = {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientInfo": {"name": "contract-test", "version": "1.0.0"},
        "io.modelcontextprotocol/clientCapabilities": client_capabilities,
    }
    return {"jsonrpc": "2.0", "id": "discover-1", "method": "server/discover", "params": {"_meta": metadata}}


@pytest.mark.asyncio
async def test_mcp_exposes_tools_and_resources(tmp_path: Path) -> None:
    server = create_mcp_server(_catalog(tmp_path))

    async with Client(server, raise_exceptions=True) as client:
        assert client.protocol_version == "2026-07-28"
        assert client.server_info is not None
        assert client.server_info.name == "skillbook"

        tools = await client.list_tools()
        assert [tool.name for tool in tools.tools] == ["list_skills", "read_skill", "read_skill_file"]
        assert [tool.title for tool in tools.tools] == ["List skills", "Read skill", "Read skill file"]
        assert all(tool.annotations == ToolAnnotations(read_only_hint=True, open_world_hint=False) for tool in tools.tools)
        assert (tools.result_type, tools.ttl_ms, tools.cache_scope) == ("complete", 0, "private")

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
        assert (resources.result_type, resources.ttl_ms, resources.cache_scope) == ("complete", 0, "private")

        templates = await client.list_resource_templates()
        assert [template.uri_template for template in templates.resource_templates] == ["skill://{name}", "skill-file://{name}/{+path}"]
        assert (templates.result_type, templates.ttl_ms, templates.cache_scope) == ("complete", 0, "private")

        prompts = await client.list_prompts()
        assert prompts.prompts == []
        assert (prompts.result_type, prompts.ttl_ms, prompts.cache_scope) == ("complete", 0, "private")

        document_result = await client.read_resource("skill://demo")
        document = document_result.contents[0]
        assert isinstance(document, TextResourceContents)
        assert document.text.endswith("# Demo\n")

        file_result = await client.read_resource("skill-file://demo/references/details.md")
        skill_file = file_result.contents[0]
        assert isinstance(skill_file, TextResourceContents)
        assert skill_file.text == "# Details\n"


def test_streamable_http_exposes_modern_discovery_contract(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    app = create_app(create_mcp_server(catalog), catalog)
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json", "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "server/discover"}

    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        response = client.post("/mcp", headers=headers, json=_discover_request())

    assert response.status_code == 200
    assert "mcp-session-id" not in response.headers
    payload: object = response.json()
    assert isinstance(payload, dict)
    result = DiscoverResult.model_validate(payload.get("result"), strict=True)
    assert result.result_type == "complete"
    assert result.supported_versions == ["2026-07-28"]
    assert (result.ttl_ms, result.cache_scope) == (0, "private")
    assert result.meta is not None and "io.modelcontextprotocol/serverInfo" in result.meta


def test_streamable_http_rejects_missing_modern_routing_header(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    app = create_app(create_mcp_server(catalog), catalog)
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json", "MCP-Protocol-Version": "2026-07-28"}

    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        response = client.post("/mcp", headers=headers, json=_discover_request())

    assert response.status_code == 400
    error = JSONRPCError.model_validate(response.json(), strict=True)
    assert error.error.code == -32020


def test_fastapi_health_checks_the_live_catalog(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    app = create_app(create_mcp_server(catalog), catalog)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "skills": 1}
