from pathlib import Path

from triad.proxy.compact_runtime import CompactConfig
from triad.proxy.runtime_state import ThreadRuntimeStore
from triad.proxy.translator import PromptTurn


def test_runtime_store_uses_fallback_prompt_for_first_turn(tmp_path):
    store = ThreadRuntimeStore(storage_dir=tmp_path / "runtime")
    thread_key = store.resolve_thread_key(fallback_response_id="resp_1")
    store.record_request_context(
        thread_key,
        cwd="/tmp/project",
        turns=[PromptTurn(role="user", text="Plan the rollout")],
    )

    prompt = store.build_prompt(
        thread_key,
        provider="codex",
        current_user_turn="Plan the rollout",
        fallback_prompt="Plan the rollout",
        cwd="/tmp/project",
    )

    assert prompt == "Plan the rollout"


def test_runtime_store_compacts_and_persists_thread_state(tmp_path):
    store = ThreadRuntimeStore(
        storage_dir=tmp_path / "runtime",
        compact_config=CompactConfig(
            micro_keep_turns=2,
            prompt_recent_turns=1,
            micro_threshold_tokens=10,
            session_threshold_tokens=15,
            full_threshold_tokens=20,
            max_micro_chars=500,
            max_session_chars=700,
            max_full_chars=900,
        ),
    )
    thread_key = store.resolve_thread_key(fallback_response_id="resp_2")
    store.record_request_context(
        thread_key,
        cwd="/Users/martin/triad",
        metadata={"triad_thread_key": "thread-2"},
        turns=[PromptTurn(role="user", text="Use /Users/martin/triad/README.md and preserve the current plan.")],
    )

    for idx in range(6):
        store.record_user_turn(thread_key, f"User request {idx} with /Users/martin/project/file{idx}.py and keep the constraints intact.")
        store.record_assistant_turn(thread_key, f"Assistant answer {idx} with implementation details and follow-up notes.")

    store.mark_provider(thread_key, "claude", "acc2")
    store.register_response(thread_key, "resp_saved")

    thread = store.threads[thread_key]
    assert thread.summary
    assert thread.transcript_path
    assert Path(thread.transcript_path).exists()

    prompt = store.build_prompt(
        thread_key,
        provider="codex",
        current_user_turn="Switch provider and continue",
        fallback_prompt="Switch provider and continue",
        cwd="/Users/martin/triad",
    )

    assert "Provider handoff: the previous assistant provider was claude." in prompt
    assert "Runtime restore bundle:" in prompt
    assert "Important files and paths:" in prompt
    assert "If specific earlier details are needed, consult the full transcript at:" in prompt

    reloaded = ThreadRuntimeStore(storage_dir=tmp_path / "runtime")
    assert reloaded.response_to_thread["resp_saved"] == thread_key
    restored = reloaded.threads[thread_key]
    assert restored.summary
    assert restored.last_provider == "claude"
