"""AgentVerse Hub — edge-case tests (streaming, export, engine, router, templates)."""

import uuid
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

with patch.dict("os.environ", {"OLLAMA_URL": ""}, clear=False):
    from main import app
    from llm.router import LLMRouter, LLMResponse
    from agents.engine import AgentConfig, AgentEngine, AgentResult
    from templates.registry import TEMPLATES, get_template, get_templates, get_categories


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from security import get_limiter
    get_limiter().reset()
    yield
    get_limiter().reset()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------

class TestStream:
    def _post(self, client, payload):
        return client.post("/api/agents/stream", json=payload, timeout=60)

    def test_stream_unknown_agent_404(self, client):
        r = self._post(client, {"agent_id": "nope", "message": "hi"})
        assert r.status_code == 404

    def test_stream_missing_message_422(self, client):
        r = self._post(client, {"agent_id": "content-writer"})
        assert r.status_code == 422

    def test_stream_sse_content_type(self, client):
        with patch("routes.agents.get_router") as mock_gr:
            async def fake(**kwargs):
                yield "OK"
            mock_gr.return_value = MagicMock(stream=fake)
            r = self._post(client, {"agent_id": "content-writer", "message": "hi"})
            assert r.status_code == 200
            assert "text/event-stream" in r.headers["content-type"]

    def test_stream_start_event(self, client):
        with patch("routes.agents.get_router") as mock_gr:
            async def fake(**kwargs):
                yield "OK"
            mock_gr.return_value = MagicMock(stream=fake)
            r = self._post(client, {"agent_id": "content-writer", "message": "hi"})
            assert "start" in r.text

    def test_stream_end_event(self, client):
        with patch("routes.agents.get_router") as mock_gr:
            async def fake(**kwargs):
                yield "OK"
            mock_gr.return_value = MagicMock(stream=fake)
            r = self._post(client, {"agent_id": "content-writer", "message": "hi"})
            assert "end" in r.text

    def test_stream_error_event_on_broken_provider(self, client):
        with patch("routes.agents.get_router") as mock_gr:
            async def broken(**kwargs):
                raise RuntimeError("provider down")
                yield  # pragma: no cover
            mock_gr.return_value = MagicMock(stream=broken)
            r = self._post(client, {"agent_id": "content-writer", "message": "hi"})
            assert r.status_code == 200  # SSE always 200; error inside
            assert "error" in r.text

    def test_stream_session_id_generated(self, client):
        with patch("routes.agents.get_router") as mock_gr:
            async def fake(**kwargs):
                yield "OK"
            mock_gr.return_value = MagicMock(stream=fake)
            r = self._post(client, {"agent_id": "content-writer", "message": "hi"})
            assert "session_id" in r.text


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class TestExport:
    def test_export_python_contains_class(self, client):
        r = client.get("/api/agents/content-writer/export?format=python")
        assert r.status_code == 200
        assert "class" in r.json()["code"]

    def test_export_typescript_contains_interface(self, client):
        r = client.get("/api/agents/content-writer/export?format=typescript")
        assert r.status_code == 200
        assert "interface" in r.json()["code"]

    def test_export_unknown_404(self, client):
        r = client.get("/api/agents/no-such-agent/export?format=python")
        assert r.status_code == 404

    def test_export_default_format_python(self, client):
        r = client.get("/api/agents/content-writer/export")
        assert r.status_code == 200
        assert r.json()["format"] == "python"

    def test_export_unknown_format_still_returns(self, client):
        r = client.get("/api/agents/content-writer/export?format=java")
        assert r.status_code == 200
        # Unknown format falls back to python branch
        assert "code" in r.json()

    def test_export_contains_agent_name(self, client):
        r = client.get("/api/agents/content-writer/export?format=python")
        assert "Content Writer" in r.json()["code"] or "content" in r.json()["code"].lower()

    def test_export_all_template_agents(self, client):
        # First 10 templates should all export cleanly
        for t in TEMPLATES[:10]:
            r = client.get(f"/api/agents/{t.id}/export?format=python")
            assert r.status_code == 200, f"export failed for {t.id}"


# ---------------------------------------------------------------------------
# Create / delete custom agent
# ---------------------------------------------------------------------------

class TestCustomAgents:
    def test_create_and_delete(self, client):
        name = f"TmpBot-{uuid.uuid4().hex[:6]}"
        r = client.post("/api/agents/create", json={
            "name": name, "description": "d", "category": "productivity",
            "system_prompt": "Be helpful.", "model": "llama3.2",
            "tools": [], "temperature": 0.5,
        })
        assert r.status_code == 200
        aid = r.json()["id"]
        r2 = client.delete(f"/api/agents/{aid}")
        assert r2.status_code == 200

    def test_delete_unknown_404(self, client):
        r = client.delete("/api/agents/never-existed")
        assert r.status_code == 404

    def test_delete_template_404(self, client):
        r = client.delete("/api/agents/content-writer")
        assert r.status_code == 404  # templates cannot be deleted

    def test_create_missing_field_422(self, client):
        r = client.post("/api/agents/create", json={"name": "x"})
        assert r.status_code == 422

    def test_custom_agent_appears_in_list(self, client):
        name = f"ListBot-{uuid.uuid4().hex[:6]}"
        r = client.post("/api/agents/create", json={
            "name": name, "description": "d", "category": "coding",
            "system_prompt": "code", "model": "llama3.2",
            "tools": [], "temperature": 0.5,
        })
        aid = r.json()["id"]
        listing = client.get("/api/agents/").json()["agents"]
        ids = [a["id"] for a in listing]
        assert aid in ids
        client.delete(f"/api/agents/{aid}")

    def test_create_sanitize_xss_in_name(self, client):
        r = client.post("/api/agents/create", json={
            "name": "<script>alert(1)</script>Bot", "description": "d",
            "category": "productivity", "system_prompt": "hi",
            "model": "llama3.2", "tools": [], "temperature": 0.5,
        })
        assert r.status_code == 200
        aid = r.json()["id"]
        got = client.get(f"/api/agents/{aid}").json()
        assert "<script" not in got["name"]
        client.delete(f"/api/agents/{aid}")


# ---------------------------------------------------------------------------
# Templates registry (unit)
# ---------------------------------------------------------------------------

class TestTemplates:
    def test_templates_nonempty(self):
        assert len(TEMPLATES) >= 100

    def test_get_template_found(self):
        t = get_template("content-writer")
        assert t is not None
        assert t.id == "content-writer"

    def test_get_template_missing(self):
        assert get_template("does-not-exist") is None

    def test_categories_nonempty(self):
        cats = get_categories()
        assert len(cats) >= 5

    def test_every_template_has_required_fields(self):
        for t in TEMPLATES:
            assert t.id and t.name and t.description
            assert t.category and t.system_prompt

    def test_template_ids_unique(self):
        ids = [t.id for t in TEMPLATES]
        assert len(ids) == len(set(ids))

    def test_get_templates_returns_all(self):
        assert len(get_templates()) == len(TEMPLATES)

    def test_categories_have_counts(self):
        r = TestClient(app).get("/api/agents/categories")
        data = r.json()
        assert "categories" in data
        assert all("count" in c for c in data["categories"])


# ---------------------------------------------------------------------------
# Engine (unit)
# ---------------------------------------------------------------------------

class TestEngineUnit:
    def _cfg(self, **kw):
        base = dict(
            id="t1", name="T", description="d", category="coding",
            system_prompt="You are a bot.", model="llama3.2",
            tools=[], temperature=0.5,
        )
        base.update(kw)
        return AgentConfig(**base)

    def test_config_defaults(self):
        c = self._cfg()
        assert c.temperature == 0.5
        assert c.tools == []
        assert c.max_tokens == 4096

    def test_result_defaults(self):
        r = AgentResult(success=True, output="ok")
        assert r.tool_calls == []
        assert r.error is None

    def test_engine_init(self):
        with patch.dict("os.environ", {"OLLAMA_URL": ""}, clear=False):
            e = AgentEngine(self._cfg())
            assert e.config.id == "t1"

    def test_detect_language_python(self):
        with patch.dict("os.environ", {"OLLAMA_URL": ""}, clear=False):
            e = AgentEngine(self._cfg())
            assert e._detect_language("def foo(): pass") == "python"

    def test_detect_language_js(self):
        with patch.dict("os.environ", {"OLLAMA_URL": ""}, clear=False):
            e = AgentEngine(self._cfg())
            assert e._detect_language("function f() { console.log(1) }") == "javascript"

    def test_extract_search_query(self):
        with patch.dict("os.environ", {"OLLAMA_URL": ""}, clear=False):
            e = AgentEngine(self._cfg())
            assert e._extract_search_query("search for fastapi") == "fastapi"

    def test_extract_code_from_fences(self):
        with patch.dict("os.environ", {"OLLAMA_URL": ""}, clear=False):
            e = AgentEngine(self._cfg())
            code = e._extract_code("here ```python\nprint(1)\n``` done")
            assert code is not None
            assert "print(1)" in code

    def test_extract_code_none(self):
        with patch.dict("os.environ", {"OLLAMA_URL": ""}, clear=False):
            e = AgentEngine(self._cfg())
            assert e._extract_code("no code here") is None


# ---------------------------------------------------------------------------
# LLM router (unit)
# ---------------------------------------------------------------------------

class TestRouterUnit:
    def test_provider_openai(self):
        r = LLMRouter()
        assert r._get_provider("gpt-4") == "openai"

    def test_provider_anthropic(self):
        r = LLMRouter()
        assert r._get_provider("claude-3-opus") == "anthropic"

    def test_provider_google(self):
        r = LLMRouter()
        assert r._get_provider("gemini-pro") == "google"

    def test_provider_ollama(self):
        r = LLMRouter()
        assert r._get_provider("llama3.2") == "ollama"
        assert r._get_provider("qwen3:8b") == "ollama"

    def test_list_models_shape(self):
        r = LLMRouter()
        m = r.list_models()
        assert isinstance(m, dict)
        for v in m.values():
            assert isinstance(v, list)

    def test_generate_no_providers_raises(self):
        r = LLMRouter()
        r.providers = {}
        with pytest.raises(Exception):
            import asyncio
            asyncio.run(r.generate(model="x", messages=[{"role": "user", "content": "hi"}]))

    def test_stream_no_providers_raises(self):
        r = LLMRouter()
        r.providers = {}
        with pytest.raises(Exception):
            async def consume():
                async for _ in r.stream(model="x", messages=[]):
                    pass
            import asyncio
            asyncio.run(consume())


# ---------------------------------------------------------------------------
# Run endpoint error handling
# ---------------------------------------------------------------------------

class TestRunErrors:
    def test_run_unknown_404(self, client):
        r = client.post("/api/agents/run", json={"agent_id": "ghost", "message": "hi"})
        assert r.status_code == 404

    def test_run_missing_message_422(self, client):
        r = client.post("/api/agents/run", json={"agent_id": "content-writer"})
        assert r.status_code == 422

    def test_run_with_mocked_llm(self, client):
        with patch("llm.router.LLMRouter.generate") as mock_gen:
            mock_gen.return_value = LLMResponse(
                content="mocked output", model="llama3.2", provider="ollama", tokens_used=5,
            )
            r = client.post("/api/agents/run", json={
                "agent_id": "content-writer", "message": "Write a line",
            }, timeout=30)
            assert r.status_code == 200
            assert r.json()["output"] == "mocked output"

    def test_run_history_passed(self, client):
        with patch("llm.router.LLMRouter.generate") as mock_gen:
            mock_gen.return_value = LLMResponse(
                content="ok", model="llama3.2", provider="ollama",
            )
            r = client.post("/api/agents/run", json={
                "agent_id": "content-writer", "message": "hi",
                "history": [{"role": "user", "content": "earlier"}],
            }, timeout=30)
            assert r.status_code == 200
