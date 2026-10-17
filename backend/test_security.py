"""AgentVerse Hub — security tests (sanitization, rate limit, auth)."""

import time
import pytest
from fastapi.testclient import TestClient

from security import (
    sanitize_text,
    sanitize_body,
    TokenBucket,
    RateLimiter,
    _key_valid,
    _expected_key,
    resolve_client_ip,
    SecurityMiddleware,
)


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------

class TestSanitizeText:
    def test_strips_script_closed(self):
        assert "<script" not in sanitize_text("<script>alert(1)</script>hi")

    def test_strips_script_unclosed(self):
        assert "<script" not in sanitize_text("before<script>after")

    def test_strips_iframe(self):
        assert "<iframe" not in sanitize_text('<iframe src="x"></iframe>ok')

    def test_strips_union_select(self):
        assert "union select" not in sanitize_text("1 union select 2").lower()

    def test_strips_drop_table(self):
        assert "drop table" not in sanitize_text("drop table users").lower()

    def test_strips_path_traversal(self):
        assert ".." not in sanitize_text("../../etc/passwd")

    def test_strips_null_byte(self):
        assert "\x00" not in sanitize_text("a\x00b")

    def test_truncates_long(self):
        assert len(sanitize_text("x" * 20000)) <= 8000

    def test_custom_limit(self):
        assert len(sanitize_text("y" * 500, max_len=50)) == 50

    def test_normal_text_unchanged(self):
        assert sanitize_text("Hello world!") == "Hello world!"

    def test_non_string_passthrough(self):
        assert sanitize_text(42) == 42  # type: ignore[arg-type]

    def test_empty(self):
        assert sanitize_text("") == ""

    def test_multiline_preserved(self):
        assert sanitize_text("line1\nline2") == "line1\nline2"


class TestSanitizeBody:
    def test_nested_dict(self):
        out = sanitize_body({"a": {"b": "<script>x"}})
        assert "<script" not in out["a"]["b"]

    def test_list_of_strings(self):
        out = sanitize_body({"t": ["<script>1", "ok"]})
        assert "<script" not in out["t"][0]
        assert out["t"][1] == "ok"

    def test_list_of_dicts(self):
        out = sanitize_body({"items": [{"cmd": "<script>"}]})
        assert "<script" not in out["items"][0]["cmd"]

    def test_message_truncated(self):
        out = sanitize_body({"message": "x" * 20000})
        assert len(out["message"]) <= 8000

    def test_short_field_truncated(self):
        out = sanitize_body({"model": "z" * 2000})
        assert len(out["model"]) <= 500

    def test_non_strings_preserved(self):
        out = sanitize_body({"n": 1, "f": 1.5, "b": True, "null": None})
        assert out == {"n": 1, "f": 1.5, "b": True, "null": None}

    def test_system_prompt_truncated(self):
        out = sanitize_body({"system_prompt": "p" * 20000})
        assert len(out["system_prompt"]) <= 8000


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class TestTokenBucket:
    def test_within_capacity(self):
        b = TokenBucket(capacity=3, refill_rate=0.001)
        assert all(b.consume() for _ in range(3))

    def test_exhaustion(self):
        b = TokenBucket(capacity=1, refill_rate=0.001)
        b.consume()
        assert b.consume() is False

    def test_refill(self):
        b = TokenBucket(capacity=1, refill_rate=1000.0)
        b.consume()
        time.sleep(0.05)
        assert b.consume() is True

    def test_cap_never_exceeded(self):
        b = TokenBucket(capacity=2, refill_rate=10000.0)
        time.sleep(0.1)
        assert b.tokens <= 2


class TestRateLimiter:
    def test_allows_burst(self):
        rl = RateLimiter(capacity=4, refill_rate=0.001)
        assert all(rl.check("a") for _ in range(4))

    def test_blocks_after(self):
        rl = RateLimiter(capacity=2, refill_rate=0.001)
        rl.check("b"); rl.check("b")
        assert rl.check("b") is False

    def test_client_isolation(self):
        rl = RateLimiter(capacity=1, refill_rate=0.001)
        rl.check("x")
        assert rl.check("x") is False
        assert rl.check("y") is True

    def test_reset(self):
        rl = RateLimiter(capacity=1, refill_rate=0.001)
        rl.check("z"); rl.check("z")
        rl.reset()
        assert rl.check("z") is True


# ---------------------------------------------------------------------------
# API key
# ---------------------------------------------------------------------------

class TestApiKey:
    def test_off_when_unset(self, monkeypatch):
        monkeypatch.delenv("AGENTVERSE_API_KEY", raising=False)
        assert _expected_key() == ""
        assert _key_valid("") is True

    def test_valid(self, monkeypatch):
        monkeypatch.setenv("AGENTVERSE_API_KEY", "k1")
        assert _key_valid("k1") is True

    def test_invalid(self, monkeypatch):
        monkeypatch.setenv("AGENTVERSE_API_KEY", "k1")
        assert _key_valid("bad") is False

    def test_empty_when_auth_on(self, monkeypatch):
        monkeypatch.setenv("AGENTVERSE_API_KEY", "k1")
        assert _key_valid("") is False


# ---------------------------------------------------------------------------
# Middleware integration
# ---------------------------------------------------------------------------

class TestMiddleware:
    @pytest.fixture
    def app(self):
        from main import app as _app
        return _app

    def test_health_public(self, app):
        with TestClient(app) as c:
            for _ in range(3):
                assert c.get("/health").status_code == 200

    def test_auth_401_without_key(self, monkeypatch):
        monkeypatch.setenv("AGENTVERSE_API_KEY", "av-secret")
        from main import app as _app
        with TestClient(_app) as c:
            assert c.get("/api/agents/").status_code == 401

    def test_auth_200_with_key(self, monkeypatch):
        monkeypatch.setenv("AGENTVERSE_API_KEY", "av-secret")
        from main import app as _app
        with TestClient(_app) as c:
            r = c.get("/api/agents/", headers={"x-api-key": "av-secret"})
            assert r.status_code == 200

    def test_auth_bearer(self, monkeypatch):
        monkeypatch.setenv("AGENTVERSE_API_KEY", "av2")
        from main import app as _app
        with TestClient(_app) as c:
            r = c.get("/api/agents/", headers={"authorization": "Bearer av2"})
            assert r.status_code == 200

    def test_auth_off_by_default(self, monkeypatch):
        monkeypatch.delenv("AGENTVERSE_API_KEY", raising=False)
        from main import app as _app
        with TestClient(_app) as c:
            assert c.get("/api/agents/").status_code == 200

    def test_rate_limit_429(self, monkeypatch):
        monkeypatch.delenv("AGENTVERSE_API_KEY", raising=False)
        from security import get_limiter
        get_limiter().reset()
        from main import app as _app
        with TestClient(_app) as c:
            codes = [c.get("/api/agents/").status_code for _ in range(35)]
            assert 429 in codes
            assert codes[0] == 200
        get_limiter().reset()

    def test_sanitizes_create_body(self, monkeypatch):
        monkeypatch.delenv("AGENTVERSE_API_KEY", raising=False)
        from main import app as _app
        with TestClient(_app) as c:
            r = c.post("/api/agents/create", json={
                "name": "<script>x</script>Bot",
                "description": "desc",
                "category": "productivity",
                "system_prompt": "You are helpful.",
                "model": "llama3.2",
                "tools": [],
                "temperature": 0.5,
            })
            # Should succeed (sanitizer strips script from name)
            assert r.status_code == 200
            agent_id = r.json()["id"]
            # Verify stored name has no script tag
            got = c.get(f"/api/agents/{agent_id}")
            assert "<script" not in got.json().get("name", "")

    def test_middleware_flags(self, app):
        m = SecurityMiddleware(app, rate_limit=False, sanitize=False, auth=False)
        assert m._rate_limit is False
        assert m._sanitize is False
        assert m._auth is False


# ---------------------------------------------------------------------------
# Client IP resolution (trusted proxies)
# ---------------------------------------------------------------------------

def _fake_request(peer: str = "127.0.0.1", headers: dict | None = None):
    from starlette.requests import Request
    hdrs = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({
        "type": "http", "method": "GET", "path": "/", "headers": hdrs,
        "client": (peer, 12345),
    })


class TestResolveClientIP:
    def test_xff_first_hop_when_trusted(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXIES", "127.0.0.1,::1")
        req = _fake_request("127.0.0.1", {"X-Forwarded-For": "9.9.9.9, 8.8.8.8"})
        assert resolve_client_ip(req) == "9.9.9.9"

    def test_x_real_ip_when_trusted(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXIES", "127.0.0.1")
        req = _fake_request("127.0.0.1", {"X-Real-IP": "7.7.7.7"})
        assert resolve_client_ip(req) == "7.7.7.7"

    def test_xff_ignored_when_peer_untrusted(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXIES", "127.0.0.1,::1")
        req = _fake_request("203.0.113.5", {"X-Forwarded-For": "9.9.9.9"})
        assert resolve_client_ip(req) == "203.0.113.5"

    def test_no_headers_returns_peer(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXIES", "127.0.0.1")
        req = _fake_request("127.0.0.1")
        assert resolve_client_ip(req) == "127.0.0.1"

    def test_middleware_keys_bucket_by_xff_when_trusted(self, monkeypatch):
        monkeypatch.delenv("AGENTVERSE_API_KEY", raising=False)
        monkeypatch.setenv("TRUSTED_PROXIES", "testclient")
        from security import get_limiter
        get_limiter().reset()
        from main import app as _app
        with TestClient(_app) as c:
            r = c.get("/api/agents/", headers={"X-Forwarded-For": "9.9.9.9, 8.8.8.8"})
            assert r.status_code == 200
            buckets = set(get_limiter()._buckets)
        assert "9.9.9.9" in buckets
        get_limiter().reset()

    def test_middleware_ignores_xff_when_untrusted(self, monkeypatch):
        monkeypatch.delenv("AGENTVERSE_API_KEY", raising=False)
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")
        from security import get_limiter
        get_limiter().reset()
        from main import app as _app
        with TestClient(_app) as c:
            r = c.get("/api/agents/", headers={"X-Forwarded-For": "9.9.9.9"})
            assert r.status_code == 200
            buckets = set(get_limiter()._buckets)
        assert "9.9.9.9" not in buckets
        get_limiter().reset()


# ---------------------------------------------------------------------------
# Rate limiter pruning
# ---------------------------------------------------------------------------

class TestRateLimiterPruning:
    def test_idle_buckets_pruned(self):
        rl = RateLimiter(capacity=2, refill_rate=0.001, idle_ttl=600.0)
        rl.check("idle-client")
        rl._buckets["idle-client"].updated = time.monotonic() - 700
        rl.check("new-client")
        assert "idle-client" not in rl._buckets
        assert "new-client" in rl._buckets

    def test_active_buckets_kept(self):
        rl = RateLimiter(capacity=2, refill_rate=0.001, idle_ttl=600.0)
        rl.check("active")
        rl.check("new")
        assert "active" in rl._buckets

    def test_cap_evicts_oldest(self):
        rl = RateLimiter(capacity=10, refill_rate=0.001, idle_ttl=99999.0, max_buckets=5)
        now = time.monotonic()
        for i in range(5):
            rl.check(f"c{i}")
            rl._buckets[f"c{i}"].updated = now - (100 - i)
        rl.check("newest")
        assert len(rl._buckets) <= 5
        assert "c0" not in rl._buckets
        assert "newest" in rl._buckets
