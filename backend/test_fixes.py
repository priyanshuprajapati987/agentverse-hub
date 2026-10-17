"""AgentVerse Hub — regression tests for the audit fix round."""

import ast
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from llm.router import LLMResponse
from tools.registry import ToolResult, get_tool_registry


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


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Point the store at a temp dir and clear the custom-agent working set."""
    import store
    import routes.agents as agents_module
    monkeypatch.setenv("AGENTVERSE_DATA_DIR", str(tmp_path))
    store._reset()
    saved = dict(agents_module._custom_agents)
    agents_module._custom_agents.clear()
    yield
    agents_module._custom_agents.clear()
    agents_module._custom_agents.update(saved)
    store._reset()


def _payload(**kw):
    base = {
        "name": f"Bot-{uuid.uuid4().hex[:8]}",
        "description": "A test bot",
        "category": "writing",
        "system_prompt": "You are a helpful bot.",
        "model": "llama3.2",
        "tools": [],
        "temperature": 0.5,
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# 1. Model-override must not corrupt shared templates
# ---------------------------------------------------------------------------

class TestModelOverrideIsolation:
    def test_run_model_override_does_not_mutate_template(self, client, isolated):
        with patch("llm.router.LLMRouter.generate") as mock_gen:
            mock_gen.return_value = LLMResponse(
                content="ok", model="qwen3:8b", provider="ollama", tokens_used=1,
            )
            r = client.post("/api/agents/run", json={
                "agent_id": "content-writer", "message": "hi", "model": "qwen3:8b",
            }, timeout=30)
            assert r.status_code == 200
        got = client.get("/api/agents/content-writer").json()
        assert got["model"] == "llama3.2"

    def test_stream_model_override_does_not_mutate_template(self, client, isolated):
        with patch("routes.agents.get_router") as mock_gr:
            async def fake(**kwargs):
                yield "OK"
            mock_gr.return_value = MagicMock(stream=fake)
            r = client.post("/api/agents/stream", json={
                "agent_id": "content-writer", "message": "hi", "model": "qwen3:8b",
            }, timeout=30)
            assert r.status_code == 200
        got = client.get("/api/agents/content-writer").json()
        assert got["model"] == "llama3.2"


# ---------------------------------------------------------------------------
# 2. Persistence + run/star counters
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_store_roundtrip_across_reload(self, isolated, tmp_path):
        import store
        store.put_custom_agent({
            "id": "abc123def456", "name": "Persist Bot", "description": "d",
            "category": "writing", "system_prompt": "p", "model": "llama3.2",
            "tools": [], "temperature": 0.5, "max_tokens": 4096,
            "author": "user", "tags": [],
        })
        store._reset()  # simulate process restart
        agents = store.get_custom_agents()
        assert "abc123def456" in agents
        assert agents["abc123def456"]["name"] == "Persist Bot"
        assert (tmp_path / "store.json").exists()

    def test_create_persists_to_disk(self, client, isolated, tmp_path):
        r = client.post("/api/agents/create", json=_payload(name="Disk Persist Bot"))
        assert r.status_code == 200
        aid = r.json()["id"]
        raw = json.loads((tmp_path / "store.json").read_text(encoding="utf-8"))
        assert aid in raw["custom_agents"]
        assert raw["custom_agents"][aid]["name"] == "Disk Persist Bot"

    def test_delete_removes_from_disk(self, client, isolated, tmp_path):
        r = client.post("/api/agents/create", json=_payload(name="Delete Disk Bot"))
        aid = r.json()["id"]
        assert client.delete(f"/api/agents/{aid}").status_code == 200
        raw = json.loads((tmp_path / "store.json").read_text(encoding="utf-8"))
        assert aid not in raw["custom_agents"]

    def test_run_endpoint_increments(self, client, isolated):
        r = client.post("/api/agents/content-writer/run")
        assert r.status_code == 200
        assert r.json()["run_count"] == 1
        r = client.post("/api/agents/content-writer/run")
        assert r.json()["run_count"] == 2

    def test_run_endpoint_unknown_404(self, client, isolated):
        assert client.post("/api/agents/no-such-agent-xyz/run").status_code == 404

    def test_star_endpoint_increment_decrement_floor(self, client, isolated):
        aid = "content-writer"
        assert client.post(f"/api/agents/{aid}/star", json={"delta": 1}).json()["star_count"] == 1
        assert client.post(f"/api/agents/{aid}/star", json={"delta": 1}).json()["star_count"] == 2
        assert client.post(f"/api/agents/{aid}/star", json={"delta": -1}).json()["star_count"] == 1
        assert client.post(f"/api/agents/{aid}/star", json={"delta": -1}).json()["star_count"] == 0
        assert client.post(f"/api/agents/{aid}/star", json={"delta": -1}).json()["star_count"] == 0

    def test_star_unknown_404(self, client, isolated):
        r = client.post("/api/agents/no-such-agent-xyz/star", json={"delta": 1})
        assert r.status_code == 404

    def test_list_includes_counts(self, client, isolated):
        client.post("/api/agents/content-writer/star", json={"delta": 1})
        r = client.get("/api/agents/")
        agents = r.json()["agents"]
        assert all("run_count" in a and "star_count" in a for a in agents)
        cw = next(a for a in agents if a["id"] == "content-writer")
        assert cw["star_count"] == 1
        assert cw["run_count"] == 0

    def test_run_auto_increments_on_success(self, client, isolated):
        with patch("llm.router.LLMRouter.generate") as mock_gen:
            mock_gen.return_value = LLMResponse(
                content="ok", model="llama3.2", provider="ollama",
            )
            r = client.post("/api/agents/run", json={
                "agent_id": "content-writer", "message": "hi",
            }, timeout=30)
            assert r.status_code == 200
        import store
        assert store.get_stat("content-writer")["run_count"] == 1

    def test_stream_increments_on_end(self, client, isolated):
        with patch("routes.agents.get_router") as mock_gr:
            async def fake(**kwargs):
                yield "OK"
            mock_gr.return_value = MagicMock(stream=fake)
            r = client.post("/api/agents/stream", json={
                "agent_id": "content-writer", "message": "hi",
            }, timeout=30)
            assert '"end"' in r.text
        import store
        assert store.get_stat("content-writer")["run_count"] == 1

    def test_stream_error_does_not_increment(self, client, isolated):
        with patch("routes.agents.get_router") as mock_gr:
            async def broken(**kwargs):
                raise RuntimeError("provider down")
                yield  # pragma: no cover
            mock_gr.return_value = MagicMock(stream=broken)
            r = client.post("/api/agents/stream", json={
                "agent_id": "content-writer", "message": "hi",
            }, timeout=30)
            assert '"error"' in r.text
        import store
        assert store.get_stat("content-writer")["run_count"] == 0


# ---------------------------------------------------------------------------
# 3. Create-agent validation
# ---------------------------------------------------------------------------

class TestCreateValidation:
    def test_empty_name_422(self, client, isolated):
        r = client.post("/api/agents/create", json=_payload(name=""))
        assert r.status_code == 422

    def test_whitespace_name_422(self, client, isolated):
        r = client.post("/api/agents/create", json=_payload(name="   "))
        assert r.status_code == 422

    def test_name_too_long_422(self, client, isolated):
        r = client.post("/api/agents/create", json=_payload(name="x" * 201))
        assert r.status_code == 422

    def test_temperature_too_high_422(self, client, isolated):
        r = client.post("/api/agents/create", json=_payload(temperature=999.0))
        assert r.status_code == 422

    def test_temperature_negative_422(self, client, isolated):
        r = client.post("/api/agents/create", json=_payload(temperature=-1.0))
        assert r.status_code == 422

    def test_unknown_tool_422_lists_valid(self, client, isolated):
        r = client.post("/api/agents/create", json=_payload(tools=["nope_tool"]))
        assert r.status_code == 422
        detail = str(r.json()["detail"])
        assert "nope_tool" in detail
        assert "web_search" in detail

    def test_known_tools_accepted(self, client, isolated):
        r = client.post("/api/agents/create", json=_payload(tools=["web_search", "code_execution"]))
        assert r.status_code == 200

    def test_empty_category_422(self, client, isolated):
        r = client.post("/api/agents/create", json=_payload(category=""))
        assert r.status_code == 422

    def test_duplicate_custom_name_409(self, client, isolated):
        name = f"DupBot-{uuid.uuid4().hex[:6]}"
        assert client.post("/api/agents/create", json=_payload(name=name)).status_code == 200
        r = client.post("/api/agents/create", json=_payload(name=name))
        assert r.status_code == 409
        assert r.json()["detail"] == "Agent name already exists"

    def test_duplicate_template_name_409(self, client, isolated):
        r = client.post("/api/agents/create", json=_payload(name="Content Writer"))
        assert r.status_code == 409

    def test_unique_names_get_distinct_ids(self, client, isolated):
        r1 = client.post("/api/agents/create", json=_payload(name="Same Prompt Bot", system_prompt="p"))
        r2 = client.post("/api/agents/create", json=_payload(name="Same Prompt Bot 2", system_prompt="p"))
        assert r1.json()["id"] != r2.json()["id"]


# ---------------------------------------------------------------------------
# 10. Tools actually run in /stream
# ---------------------------------------------------------------------------

class TestStreamTools:
    def test_stream_emits_tool_event_and_increments(self, client, isolated):
        r = client.post("/api/agents/create", json=_payload(
            name=f"ToolBot-{uuid.uuid4().hex[:6]}", tools=["web_search"],
        ))
        aid = r.json()["id"]
        tool = get_tool_registry().get_tool("web_search")
        with patch.object(tool, "search", new=AsyncMock(
            return_value=ToolResult(success=True, output="search findings"),
        )), patch("routes.agents.get_router") as mock_gr:
            async def fake(**kwargs):
                yield "LLM answer"
            mock_gr.return_value = MagicMock(stream=fake)
            r = client.post("/api/agents/stream", json={
                "agent_id": aid, "message": "search for fastapi",
            }, timeout=30)
        assert r.status_code == 200
        assert '"type": "tool"' in r.text
        assert '"name": "web_search"' in r.text
        assert "LLM answer" in r.text
        import store
        assert store.get_stat(aid)["run_count"] == 1

    def test_stream_without_tool_match_has_no_tool_event(self, client, isolated):
        with patch("routes.agents.get_router") as mock_gr:
            async def fake(**kwargs):
                yield "plain"
            mock_gr.return_value = MagicMock(stream=fake)
            r = client.post("/api/agents/stream", json={
                "agent_id": "content-writer", "message": "hello there",
            }, timeout=30)
        assert '"type": "tool"' not in r.text


# ---------------------------------------------------------------------------
# 9. Export sanitization
# ---------------------------------------------------------------------------

class TestExportSanitization:
    def test_export_name_with_spaces_and_digits_parses(self, client, isolated):
        r = client.post("/api/agents/create", json=_payload(name=" 42 Rocket "))
        aid = r.json()["id"]
        code = client.get(f"/api/agents/{aid}/export?format=python").json()["code"]
        ast.parse(code)
        assert "class _42RocketAgent" in code

    def test_export_prompt_triple_quotes_and_backslashes_roundtrip(self, client, isolated):
        prompt = 'He said """hello""" then used C:\\path\\n and \\tt'
        r = client.post("/api/agents/create", json=_payload(name="EscBot", system_prompt=prompt))
        aid = r.json()["id"]
        code = client.get(f"/api/agents/{aid}/export?format=python").json()["code"]
        ast.parse(code)
        ns = {"__name__": "exported_agent"}
        exec(code, ns)
        cls = next(v for k, v in ns.items() if k.endswith("Agent") and isinstance(v, type))
        inst = cls()
        assert inst.config["system_prompt"] == prompt

    def test_export_all_template_names_parse(self, client, isolated):
        from templates.registry import TEMPLATES
        for t in TEMPLATES[:15]:
            code = client.get(f"/api/agents/{t.id}/export?format=python").json()["code"]
            ast.parse(code)

    def test_export_typescript_uses_json_strings(self, client, isolated):
        prompt = 'Use `backticks` and "quotes" and \\slashes'
        r = client.post("/api/agents/create", json=_payload(name="TsBot", system_prompt=prompt))
        aid = r.json()["id"]
        code = client.get(f"/api/agents/{aid}/export?format=typescript").json()["code"]
        assert "systemPrompt: `" not in code
        assert json.dumps(prompt) in code
