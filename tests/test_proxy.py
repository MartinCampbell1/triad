import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from triad.core.config import TriadConfig
from triad.core.providers.base import StreamEvent
from triad.proxy import server
from triad.proxy.translator import translate_request, translate_to_provider_prompt


class FakeManager:
    def __init__(self, profiles_by_provider=None, pool_by_provider=None):
        self.profiles_by_provider = profiles_by_provider or {}
        self.pool_by_provider = pool_by_provider or {}
        self.marked_success: list[tuple[str, str]] = []
        self.marked_rate_limited: list[tuple[str, str]] = []
        self.requests: list[tuple[str, str | None]] = []

    def get_next(self, provider: str, preferred_name: str | None = None):
        self.requests.append((provider, preferred_name))
        profile = self.profiles_by_provider.get(provider)
        if isinstance(profile, list):
            return profile.pop(0) if profile else None
        return profile

    def mark_success(self, provider: str, profile_name: str) -> None:
        self.marked_success.append((provider, profile_name))

    def mark_rate_limited(self, provider: str, profile_name: str) -> None:
        self.marked_rate_limited.append((provider, profile_name))

    def pool_status(self, provider: str) -> list[dict]:
        return list(self.pool_by_provider.get(provider, []))


class FakeStreamAdapter:
    def __init__(self, provider: str = "claude"):
        self.provider = provider

    async def execute_stream(self, profile, prompt, workdir, timeout=1800, base_env=None, **kwargs):
        yield StreamEvent(kind="text", text="Hello")
        yield StreamEvent(kind="text", text="world")
        yield StreamEvent(kind="done", data={"returncode": 0})


class FakeRateLimitedStreamAdapter:
    def __init__(self, provider: str = "claude"):
        self.provider = provider

    async def execute_stream(self, profile, prompt, workdir, timeout=1800, base_env=None, **kwargs):
        yield StreamEvent(kind="error", text="429 rate limit exceeded")


class FakeFailThenStreamAdapter:
    def __init__(self, provider: str = "claude", *, error_text: str = "429 rate limit exceeded"):
        self.provider = provider
        self.error_text = error_text

    async def execute_stream(self, profile, prompt, workdir, timeout=1800, base_env=None, **kwargs):
        yield StreamEvent(kind="error", text=self.error_text)


class FakeNonStreamingAdapter:
    def __init__(self, *, success: bool, rate_limited: bool):
        self.success = success
        self.rate_limited = rate_limited
        self.prompts: list[str] = []

    async def execute(self, profile, prompt, workdir):
        self.prompts.append(prompt)
        return SimpleNamespace(
            success=self.success,
            rate_limited=self.rate_limited,
            stdout="done",
        )


class FakeResultAdapter:
    def __init__(self, provider: str, results: list[SimpleNamespace]):
        self.provider = provider
        self.results = list(results)
        self.prompts: list[str] = []

    async def execute(self, profile, prompt, workdir):
        self.prompts.append(prompt)
        if not self.results:
            raise AssertionError("No fake results left")
        return self.results.pop(0)


@pytest.fixture(autouse=True)
def reset_proxy_state(monkeypatch):
    monkeypatch.setattr(server, "_account_manager", None, raising=False)
    monkeypatch.setattr(server, "_config", None, raising=False)
    monkeypatch.setattr(server, "_thread_store", None, raising=False)
    monkeypatch.setattr(server, "_active_orchestrator", "codex", raising=False)
    yield


@pytest.fixture
def triad_config(tmp_path):
    return TriadConfig(
        profiles_dir=tmp_path / "profiles",
        triad_home=tmp_path / "triad-home",
        providers_priority=["codex", "claude", "gemini"],
    )


def test_translate_string_input():
    body = {"input": "Fix the auth bug"}
    assert translate_to_provider_prompt(body) == "Fix the auth bug"


def test_translate_messages_list():
    body = {"input": [
        {"role": "user", "content": "Fix the auth bug"},
    ]}
    result = translate_to_provider_prompt(body)
    assert "Fix the auth bug" in result


def test_translate_nested_content():
    body = {"input": [
        {"role": "user", "content": [
            {"type": "input_text", "text": "Review this code"}
        ]},
    ]}
    result = translate_to_provider_prompt(body)
    assert "Review this code" in result


def test_translate_chat_completions_fallback():
    body = {"messages": [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Help me"},
    ]}
    result = translate_to_provider_prompt(body)
    assert "Help me" in result


def test_translate_empty():
    assert translate_to_provider_prompt({}) == ""


def test_translate_prompt_field():
    body = {"prompt": "Simple prompt"}
    assert translate_to_provider_prompt(body) == "Simple prompt"


def test_translate_request_extracts_thread_context():
    translated = translate_request({
        "input": [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": [{"type": "input_text", "text": "Plan the rollout"}]},
        ],
        "previous_response_id": "resp_prev",
        "metadata": {"triad_thread_key": "thread-123"},
    })

    assert translated.prompt == "[system]: You are helpful\n\n[user]: Plan the rollout"
    assert translated.current_user_turn == "Plan the rollout"
    assert translated.previous_response_id == "resp_prev"
    assert translated.explicit_thread_key == "thread-123"


def test_provider_priority_deduplicates_and_filters(monkeypatch, triad_config):
    triad_config.providers_priority = ["gemini", "codex", "gemini", "unknown"]
    monkeypatch.setattr(server, "get_config", lambda: triad_config)

    assert server.provider_priority() == ["gemini", "codex", "claude"]


def test_resolve_provider_order_prefers_requested_provider(monkeypatch, triad_config):
    monkeypatch.setattr(server, "get_config", lambda: triad_config)
    monkeypatch.setattr(server, "_active_orchestrator", "gemini")

    assert server.resolve_provider_order(requested_provider="claude") == [
        "claude",
        "codex",
        "gemini",
    ]


def test_health_reports_provider_priority(monkeypatch, triad_config):
    client = TestClient(server.app)
    monkeypatch.setattr(server, "get_config", lambda: triad_config)
    monkeypatch.setattr(server, "_active_orchestrator", "claude")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "orchestrator": "claude",
        "providers_priority": ["codex", "claude", "gemini"],
    }


def test_list_models_endpoint_returns_catalog():
    client = TestClient(server.app)

    response = client.get("/api/models")

    assert response.status_code == 200
    assert response.json() == {"data": server.TRIAD_MODELS}


def test_set_orchestrator_rejects_unknown_provider():
    client = TestClient(server.app)

    response = client.post("/api/orchestrator", json={"provider": "unknown"})

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "Unknown provider: unknown"


def test_list_accounts_endpoint_returns_pool_status(monkeypatch, triad_config):
    client = TestClient(server.app)
    fake_manager = FakeManager(pool_by_provider={
        "codex": [{"name": "acc1", "available": True, "requests_made": 3, "errors": 0, "cooldown_remaining_sec": 0}],
        "claude": [{"name": "acc1", "available": False, "requests_made": 7, "errors": 2, "cooldown_remaining_sec": 120}],
    })
    monkeypatch.setattr(server, "get_config", lambda: triad_config)
    monkeypatch.setattr(server, "get_account_manager", lambda: fake_manager)

    response = client.get("/api/accounts")

    assert response.status_code == 200
    assert response.json() == {
        "accounts": {
            "codex": [{"name": "acc1", "available": True, "requests_made": 3, "errors": 0, "cooldown_remaining_sec": 0}],
            "claude": [{"name": "acc1", "available": False, "requests_made": 7, "errors": 2, "cooldown_remaining_sec": 120}],
            "gemini": [],
        }
    }


def test_accounts_health_summarizes_pool_counts(monkeypatch, triad_config):
    client = TestClient(server.app)
    fake_manager = FakeManager(pool_by_provider={
        "codex": [
            {"name": "acc1", "available": True, "requests_made": 1, "errors": 0, "cooldown_remaining_sec": 0},
            {"name": "acc2", "available": False, "requests_made": 4, "errors": 1, "cooldown_remaining_sec": 90},
        ],
        "claude": [
            {"name": "acc1", "available": True, "requests_made": 2, "errors": 0, "cooldown_remaining_sec": 0},
        ],
    })
    monkeypatch.setattr(server, "get_config", lambda: triad_config)
    monkeypatch.setattr(server, "get_account_manager", lambda: fake_manager)

    response = client.get("/api/accounts/health")

    assert response.status_code == 200
    assert response.json() == {
        "total": 3,
        "available": 2,
        "on_cooldown": 1,
    }


def test_account_diagnostics_endpoint_returns_snapshot(monkeypatch, triad_config):
    client = TestClient(server.app)
    fake_manager = FakeManager()
    payload = {
        "recorded_at": "2026-04-05T12:00:00+00:00",
        "providers_priority": ["codex", "claude", "gemini"],
        "providers": {"codex": {"provider": "codex"}},
    }
    monkeypatch.setattr(server, "get_config", lambda: triad_config)
    monkeypatch.setattr(server, "get_account_manager", lambda: fake_manager)
    monkeypatch.setattr(server, "build_account_diagnostics_snapshot", lambda config, manager: payload)

    response = client.get("/api/accounts/diagnostics")

    assert response.status_code == 200
    assert response.json() == payload


def test_refresh_account_diagnostics_uses_reloaded_manager(monkeypatch, triad_config):
    client = TestClient(server.app)
    fake_manager = FakeManager()
    payload = {"providers": {}}
    monkeypatch.setattr(server, "get_config", lambda: triad_config)
    monkeypatch.setattr(server, "reload_account_manager", lambda: fake_manager)
    monkeypatch.setattr(server, "build_account_diagnostics_snapshot", lambda config, manager: payload if manager is fake_manager else {})

    response = client.post("/api/accounts/diagnostics/refresh")

    assert response.status_code == 200
    assert response.json() == payload


def test_reload_accounts_returns_provider_status(monkeypatch, triad_config):
    client = TestClient(server.app)
    fake_manager = FakeManager(pool_by_provider={
        "codex": [{"name": "acc1", "available": True, "requests_made": 0, "errors": 0, "cooldown_remaining_sec": 0}],
    })
    monkeypatch.setattr(server, "get_config", lambda: triad_config)
    monkeypatch.setattr(server, "reload_account_manager", lambda: fake_manager)

    response = client.post("/api/accounts/reload")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "providers": {
            "codex": [{"name": "acc1", "available": True, "requests_made": 0, "errors": 0, "cooldown_remaining_sec": 0}],
            "claude": [],
            "gemini": [],
        },
    }


def test_open_provider_login_endpoint(monkeypatch):
    client = TestClient(server.app)
    monkeypatch.setattr(server, "open_login_terminal", lambda provider: f"{provider} login")

    response = client.post("/api/accounts/codex/open-login")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "provider": "codex",
        "command": "codex login",
        "message": "Login flow opened in a separate terminal window.",
    }


def test_import_provider_session_endpoint(monkeypatch, triad_config):
    client = TestClient(server.app)
    calls: list[str] = []
    monkeypatch.setattr(server, "get_config", lambda: triad_config)
    monkeypatch.setattr(server, "import_current_session", lambda provider, profiles_dir: "acc7")
    monkeypatch.setattr(server, "reload_account_manager", lambda: calls.append("reloaded") or FakeManager())

    response = client.post("/api/accounts/claude/import")

    assert response.status_code == 200
    assert calls == ["reloaded"]
    assert response.json() == {
        "status": "ok",
        "provider": "claude",
        "account_name": "acc7",
        "message": "Imported claude session as acc7.",
    }


def test_create_response_requires_profile(monkeypatch, triad_config):
    client = TestClient(server.app)
    fake_manager = FakeManager(profiles_by_provider={})
    monkeypatch.setattr(server, "get_config", lambda: triad_config)
    monkeypatch.setattr(server, "get_account_manager", lambda: fake_manager)
    monkeypatch.setattr(server, "get_adapter", lambda provider: FakeStreamAdapter(provider=provider))

    response = client.post("/api/responses", json={"input": "Hello", "stream": True})

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "error": "No available provider profiles",
        "providers_tried": ["codex", "claude", "gemini"],
    }


def test_create_response_falls_back_to_next_provider(monkeypatch, triad_config):
    client = TestClient(server.app)
    fake_manager = FakeManager(profiles_by_provider={
        "codex": None,
        "claude": SimpleNamespace(name="claude-2"),
        "gemini": SimpleNamespace(name="gemini-1"),
    })
    monkeypatch.setattr(server, "get_config", lambda: triad_config)
    monkeypatch.setattr(server, "get_account_manager", lambda: fake_manager)
    monkeypatch.setattr(server, "get_adapter", lambda provider: FakeNonStreamingAdapter(success=True, rate_limited=False))

    response = client.post("/api/responses", json={"input": "Hello", "stream": False})

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["provider"] == "claude"
    assert fake_manager.requests == [
        ("codex", None),
        ("claude", None),
    ]
    assert fake_manager.marked_success == [("claude", "claude-2")]


def test_model_selection_overrides_orchestrator(monkeypatch, triad_config):
    client = TestClient(server.app)
    fake_manager = FakeManager(profiles_by_provider={
        "gemini": SimpleNamespace(name="gemini-3"),
        "codex": SimpleNamespace(name="codex-1"),
    })
    monkeypatch.setattr(server, "get_config", lambda: triad_config)
    monkeypatch.setattr(server, "_active_orchestrator", "codex")
    monkeypatch.setattr(server, "get_account_manager", lambda: fake_manager)
    monkeypatch.setattr(server, "get_adapter", lambda provider: FakeNonStreamingAdapter(success=True, rate_limited=False))

    response = client.post(
        "/api/responses",
        json={"input": "Hello", "stream": False, "model": "gemini-2.5-pro"},
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "gemini"
    assert fake_manager.requests[0] == ("gemini", None)


def test_provider_switch_handoff_injects_prior_context(monkeypatch, triad_config):
    client = TestClient(server.app)
    first_adapter = FakeNonStreamingAdapter(success=True, rate_limited=False)
    second_adapter = FakeNonStreamingAdapter(success=True, rate_limited=False)
    fake_manager = FakeManager(profiles_by_provider={
        "codex": SimpleNamespace(name="codex-1"),
        "claude": SimpleNamespace(name="claude-1"),
    })
    monkeypatch.setattr(server, "get_config", lambda: triad_config)
    monkeypatch.setattr(server, "_active_orchestrator", "codex")
    monkeypatch.setattr(server, "get_account_manager", lambda: fake_manager)
    monkeypatch.setattr(
        server,
        "get_adapter",
        lambda provider: first_adapter if provider == "codex" else second_adapter,
    )

    first = client.post("/api/responses", json={"input": "Plan the rollout", "stream": False})
    first_response_id = first.json()["id"]

    monkeypatch.setattr(server, "_active_orchestrator", "claude")
    second = client.post(
        "/api/responses",
        json={
            "input": "Now convert that into implementation steps",
            "stream": False,
            "previous_response_id": first_response_id,
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first_adapter.prompts == ["Plan the rollout"]
    assert "Provider handoff: the previous assistant provider was codex." in second_adapter.prompts[0]
    assert "Plan the rollout" in second_adapter.prompts[0]
    assert "Current user request:\nNow convert that into implementation steps" in second_adapter.prompts[0]
    assert second.json()["provider"] == "claude"


def test_create_response_streams_openai_lifecycle(monkeypatch, triad_config):
    client = TestClient(server.app)
    fake_manager = FakeManager(profiles_by_provider={"claude": SimpleNamespace(name="profile-a")})
    triad_config.providers_priority = ["claude", "codex", "gemini"]
    monkeypatch.setattr(server, "get_config", lambda: triad_config)
    monkeypatch.setattr(server, "_active_orchestrator", "claude")
    monkeypatch.setattr(server, "get_account_manager", lambda: fake_manager)
    monkeypatch.setattr(server, "get_adapter", lambda provider: FakeStreamAdapter(provider=provider))

    response = client.post("/api/responses", json={"input": "Write a summary", "stream": True})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = []
    for chunk in response.text.strip().split("\n\n"):
        if not chunk.strip():
            continue
        assert chunk.startswith("data: ")
        events.append(json.loads(chunk.removeprefix("data: ")))

    event_types = [event["type"] for event in events]
    assert event_types[:4] == [
        "response.created",
        "response.in_progress",
        "response.output_item.added",
        "response.content_part.added",
    ]
    assert "response.output_text.delta" in event_types
    assert "response.output_text.done" in event_types
    assert event_types[-2:] == ["response.output_item.done", "response.completed"]

    created = events[0]
    assert created["response"]["status"] == "in_progress"
    assert created["sequence_number"] == 0

    added = next(event for event in events if event["type"] == "response.output_item.added")
    assert added["item"]["status"] == "in_progress"
    assert added["item"]["role"] == "assistant"

    completed = events[-1]
    assert completed["response"]["status"] == "completed"
    assert completed["response"]["output"][0]["status"] == "completed"
    assert fake_manager.marked_success == [("claude", "profile-a")]


def test_catch_all_returns_404():
    client = TestClient(server.app)

    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["error"] == "Unhandled proxy route"
    assert detail["path"] == "/api/does-not-exist"


def test_stream_rate_limit_marks_profile_unavailable(monkeypatch, triad_config):
    client = TestClient(server.app)
    fake_manager = FakeManager(profiles_by_provider={"claude": SimpleNamespace(name="profile-a")})
    triad_config.providers_priority = ["claude", "codex", "gemini"]
    monkeypatch.setattr(server, "get_config", lambda: triad_config)
    monkeypatch.setattr(server, "_active_orchestrator", "claude")
    monkeypatch.setattr(server, "get_account_manager", lambda: fake_manager)
    monkeypatch.setattr(server, "get_adapter", lambda provider: FakeRateLimitedStreamAdapter(provider=provider))

    response = client.post("/api/responses", json={"input": "Write a summary", "stream": True})

    assert response.status_code == 200
    assert fake_manager.marked_rate_limited == [("claude", "profile-a")]


def test_non_streaming_rate_limit_marks_profile_unavailable(monkeypatch, triad_config):
    client = TestClient(server.app)
    fake_manager = FakeManager(profiles_by_provider={"codex": SimpleNamespace(name="profile-a")})
    monkeypatch.setattr(server, "get_config", lambda: triad_config)
    monkeypatch.setattr(server, "_active_orchestrator", "codex")
    monkeypatch.setattr(server, "get_account_manager", lambda: fake_manager)
    monkeypatch.setattr(server, "get_adapter", lambda provider: FakeNonStreamingAdapter(success=False, rate_limited=True))

    response = client.post("/api/responses", json={"input": "Hello", "stream": False})

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert fake_manager.marked_rate_limited == [("codex", "profile-a")]


def test_non_streaming_rate_limit_retries_next_provider(monkeypatch, triad_config):
    client = TestClient(server.app)
    fake_manager = FakeManager(profiles_by_provider={
        "codex": SimpleNamespace(name="codex-a"),
        "claude": SimpleNamespace(name="claude-a"),
    })
    adapters = {
        "codex": FakeResultAdapter("codex", [
            SimpleNamespace(
                success=False,
                rate_limited=True,
                stdout="",
                stderr="429 rate limit exceeded",
            )
        ]),
        "claude": FakeResultAdapter("claude", [
            SimpleNamespace(
                success=True,
                rate_limited=False,
                stdout="recovered",
                stderr="",
            )
        ]),
    }
    triad_config.providers_priority = ["codex", "claude", "gemini"]
    monkeypatch.setattr(server, "get_config", lambda: triad_config)
    monkeypatch.setattr(server, "_active_orchestrator", "codex")
    monkeypatch.setattr(server, "get_account_manager", lambda: fake_manager)
    monkeypatch.setattr(server, "get_adapter", lambda provider: adapters[provider])

    response = client.post("/api/responses", json={"input": "Hello", "stream": False})

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["provider"] == "claude"
    assert response.json()["output"][0]["content"][0]["text"] == "recovered"
    assert fake_manager.marked_rate_limited == [("codex", "codex-a")]
    assert fake_manager.marked_success == [("claude", "claude-a")]


def test_stream_rate_limit_retries_next_provider_before_output(monkeypatch, triad_config):
    client = TestClient(server.app)
    fake_manager = FakeManager(profiles_by_provider={
        "codex": SimpleNamespace(name="codex-a"),
        "claude": SimpleNamespace(name="claude-a"),
    })
    triad_config.providers_priority = ["codex", "claude", "gemini"]
    monkeypatch.setattr(server, "get_config", lambda: triad_config)
    monkeypatch.setattr(server, "_active_orchestrator", "codex")
    monkeypatch.setattr(server, "get_account_manager", lambda: fake_manager)
    monkeypatch.setattr(
        server,
        "get_adapter",
        lambda provider: (
            FakeFailThenStreamAdapter(provider="codex")
            if provider == "codex"
            else FakeStreamAdapter(provider="claude")
        ),
    )

    response = client.post("/api/responses", json={"input": "Write a summary", "stream": True})

    assert response.status_code == 200
    events = []
    for chunk in response.text.strip().split("\n\n"):
        if not chunk.strip():
            continue
        assert chunk.startswith("data: ")
        events.append(json.loads(chunk.removeprefix("data: ")))

    event_types = [event["type"] for event in events]
    assert event_types[-2:] == ["response.output_item.done", "response.completed"]
    assert fake_manager.marked_rate_limited == [("codex", "codex-a")]
    assert fake_manager.marked_success == [("claude", "claude-a")]
    completed = events[-1]
    assert completed["response"]["output"][0]["content"][0]["text"] == "Hello\nworld\n"
