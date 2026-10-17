"""AgentVerse Hub - Backend Tests"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from main import app
from templates.registry import TEMPLATES, CATEGORIES, get_template, get_templates, get_categories
from agents.engine import AgentConfig, AgentEngine, AgentResult
from tools.registry import get_tool_registry
from llm.router import get_router


client = TestClient(app)


# ============================================================
# TEMPLATE TESTS
# ============================================================

class TestTemplates:
    def test_total_templates(self):
        assert len(TEMPLATES) >= 100, f"Expected 100+, got {len(TEMPLATES)}"

    def test_all_categories_have_agents(self):
        for cat in CATEGORIES:
            count = sum(1 for t in TEMPLATES if t.category == cat)
            assert count > 0, f"Category '{cat}' has 0 agents"

    def test_template_ids_unique(self):
        ids = [t.id for t in TEMPLATES]
        assert len(ids) == len(set(ids)), "Duplicate template IDs found"

    def test_template_names_present(self):
        for t in TEMPLATES:
            assert t.name, f"Template {t.id} has no name"

    def test_template_descriptions_present(self):
        for t in TEMPLATES:
            assert t.description, f"Template {t.id} has no description"

    def test_template_system_prompts_present(self):
        for t in TEMPLATES:
            assert t.system_prompt, f"Template {t.id} has no system prompt"

    def test_get_templates_no_filter(self):
        result = get_templates()
        assert len(result) == len(TEMPLATES)

    def test_get_templates_by_category(self):
        for cat in CATEGORIES:
            result = get_templates(category=cat)
            assert all(t.category == cat for t in result)

    def test_get_template_by_id(self):
        t = get_template("content-writer")
        assert t is not None
        assert t.name == "Content Writer"

    def test_get_template_not_found(self):
        t = get_template("nonexistent-agent")
        assert t is None

    def test_get_categories(self):
        cats = get_categories()
        assert len(cats) == 8
        assert "writing" in cats
        assert "coding" in cats
        assert "design" in cats
        assert "business" in cats
        assert "education" in cats
        assert "productivity" in cats

    def test_writing_agents_count(self):
        assert sum(1 for t in TEMPLATES if t.category == "writing") == 15

    def test_coding_agents_count(self):
        assert sum(1 for t in TEMPLATES if t.category == "coding") == 20

    def test_research_agents_count(self):
        assert sum(1 for t in TEMPLATES if t.category == "research") == 15

    def test_marketing_agents_count(self):
        assert sum(1 for t in TEMPLATES if t.category == "marketing") == 15

    def test_design_agents_count(self):
        assert sum(1 for t in TEMPLATES if t.category == "design") == 10

    def test_business_agents_count(self):
        assert sum(1 for t in TEMPLATES if t.category == "business") == 10

    def test_education_agents_count(self):
        assert sum(1 for t in TEMPLATES if t.category == "education") == 8

    def test_productivity_agents_count(self):
        assert sum(1 for t in TEMPLATES if t.category == "productivity") == 8


# ============================================================
# AGENT ENGINE TESTS
# ============================================================

class TestAgentEngine:
    def test_agent_config_creation(self):
        config = AgentConfig(
            id="test",
            name="Test Agent",
            description="A test agent",
            category="writing",
            system_prompt="You are a test agent.",
        )
        assert config.id == "test"
        assert config.name == "Test Agent"

    def test_agent_config_defaults(self):
        config = AgentConfig(
            id="test",
            name="Test",
            description="Test",
            category="writing",
            system_prompt="Test",
        )
        assert config.model == "llama3.2"
        assert config.temperature == 0.7
        assert config.tools == []

    def test_agent_engine_creation(self):
        config = AgentConfig(
            id="test",
            name="Test",
            description="Test",
            category="coding",
            system_prompt="You are a coder.",
        )
        engine = AgentEngine(config)
        assert engine.config.name == "Test"

    @pytest.mark.asyncio
    async def test_agent_engine_run_mocked(self):
        config = AgentConfig(
            id="test",
            name="Test",
            description="Test",
            category="coding",
            system_prompt="You are a coder.",
        )
        engine = AgentEngine(config)

        with patch.object(engine.router, 'generate') as mock_llm:
            from llm.router import LLMResponse
            mock_llm.return_value = LLMResponse(
                content="Hello!",
                model="llama3.2",
                provider="ollama",
                tokens_used=10,
            )
            result = await engine.run(message="Hi")
            assert result.success is True
            assert result.output == "Hello!"

    def test_agent_result_creation(self):
        result = AgentResult(
            success=True,
            output="test output",
            tool_calls=["tool1"],
            tokens_used=100,
        )
        assert result.success is True
        assert result.output == "test output"
        assert result.tool_calls == ["tool1"]


# ============================================================
# TOOLS TESTS
# ============================================================

class TestTools:
    def test_available_tools(self):
        registry = get_tool_registry()
        tools = registry.list_tools()
        names = [t["name"] for t in tools]
        assert "web_search" in names
        assert "code_execution" in names
        assert "file_ops" in names

    def test_get_tool_web_search(self):
        tool = get_tool_registry().get_tool("web_search")
        assert tool is not None

    def test_get_tool_code_execution(self):
        tool = get_tool_registry().get_tool("code_execution")
        assert tool is not None

    def test_get_tool_file_ops(self):
        tool = get_tool_registry().get_tool("file_ops")
        assert tool is not None

    def test_get_tool_not_found(self):
        tool = get_tool_registry().get_tool("nonexistent")
        assert tool is None

    def test_tool_count(self):
        tools = get_tool_registry().list_tools()
        assert len(tools) == 3


# ============================================================
# LLM ROUTER TESTS
# ============================================================

class TestLLMRouter:
    def test_get_router_singleton(self):
        r1 = get_router()
        r2 = get_router()
        assert r1 is r2

    def test_router_has_provider(self):
        router = get_router()
        assert "ollama" in router.providers

    @pytest.mark.asyncio
    async def test_generate_with_mock(self):
        router = get_router()
        with patch.object(router.providers['ollama'], 'generate') as mock_gen:
            from llm.router import LLMResponse
            mock_gen.return_value = LLMResponse(
                content="Hello!",
                model="llama3.2",
                provider="ollama",
                tokens_used=10,
            )
            result = await router.generate("llama3.2", [{"role": "user", "content": "Hi"}])
            assert result.content == "Hello!"


# ============================================================
# API TESTS
# ============================================================

class TestAPI:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_list_agents(self):
        resp = client.get("/api/agents/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 100
        assert len(data["agents"]) >= 100

    def test_list_agents_structure(self):
        resp = client.get("/api/agents/")
        data = resp.json()
        agent = data["agents"][0]
        assert "id" in agent
        assert "name" in agent
        assert "description" in agent
        assert "category" in agent
        assert "tools" in agent
        assert "tags" in agent
        assert "is_template" in agent

    def test_list_categories(self):
        resp = client.get("/api/agents/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["categories"]) == 8

    def test_get_agent(self):
        resp = client.get("/api/agents/content-writer")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Content Writer"

    def test_get_agent_not_found(self):
        resp = client.get("/api/agents/nonexistent")
        assert resp.status_code == 404

    def test_create_agent(self):
        resp = client.post("/api/agents/create", json={
            "name": "Test Agent",
            "description": "A test agent",
            "category": "writing",
            "system_prompt": "You are a test agent.",
            "model": "llama3.2",
            "tools": [],
            "temperature": 0.5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"
        assert "id" in data

    def test_create_agent_validation(self):
        resp = client.post("/api/agents/create", json={})
        assert resp.status_code == 422

    def test_export_agent_python(self):
        resp = client.get("/api/agents/content-writer/export?format=python")
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "python"
        assert "class" in data["code"]
        assert "ContentWriter" in data["code"]

    def test_export_agent_typescript(self):
        resp = client.get("/api/agents/content-writer/export?format=typescript")
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "typescript"
        assert "export" in data["code"]
        assert "AgentConfig" in data["code"]

    def test_export_agent_not_found(self):
        resp = client.get("/api/agents/nonexistent/export")
        assert resp.status_code == 404

    def test_delete_template_forbidden(self):
        resp = client.delete("/api/agents/content-writer")
        assert resp.status_code == 404

    def test_delete_custom_agent(self):
        # Create then delete
        resp = client.post("/api/agents/create", json={
            "name": "Delete Me",
            "description": "Temp agent",
            "category": "writing",
            "system_prompt": "Test prompt",
        })
        agent_id = resp.json()["id"]
        resp = client.delete(f"/api/agents/{agent_id}")
        assert resp.status_code == 200

    def test_agent_search_by_category(self):
        resp = client.get("/api/agents/")
        data = resp.json()
        coding_agents = [a for a in data["agents"] if a["category"] == "coding"]
        assert len(coding_agents) == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
