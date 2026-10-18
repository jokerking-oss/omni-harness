"""Offline request evidence: provider conversion, privacy and run isolation."""

import asyncio
import json
from unittest.mock import patch

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from omniharness.models.request_evidence import build_request_evidence, with_request_evidence
from omniharness.runtime.events.store.memory import MemoryRunEventStore
from omniharness.runtime.journal import RunJournal


class ConvertedModel(BaseChatModel):
    """Synthetic provider with a final payload transformation and no network."""

    @property
    def _llm_type(self):
        return "synthetic-evidence"

    def _get_request_payload(self, messages, **kwargs):
        return {"messages": [{"role": "user", "content": "provider-transformed"}], "tools": kwargs.get("tools", []), "api_key": "NEVER-STORE-KEY"}

    def _generate(self, messages, stop=None, run_manager: CallbackManagerForLLMRun | None = None, **kwargs):
        self._get_request_payload(messages, **kwargs)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        self._get_request_payload(messages, **kwargs)
        yield ChatGenerationChunk(message=AIMessageChunk(content="ok"))


def test_evidence_hashes_content_and_schema_without_persisting_originals():
    payload = {
        "messages": [{"role": "system", "content": "SECRET-SYSTEM"}, {"role": "user", "content": "PRIVATE-USER"}],
        "tools": [{"type": "function", "function": {"name": "lookup", "description": "PRIVATE-SCHEMA"}}],
        "api_key": "API-KEY",
        "extra_headers": {"Authorization": "BEARER"},
    }
    evidence = build_request_evidence(payload, boundary="provider_payload")
    encoded = json.dumps(evidence)
    assert evidence["message_count"] == 2
    assert evidence["tool_count"] == 1
    assert evidence["tools"][0]["name"] == "lookup"
    assert len(evidence["sha256"]) == 64
    assert all(secret not in encoded for secret in ("SECRET-SYSTEM", "PRIVATE-USER", "PRIVATE-SCHEMA", "API-KEY", "BEARER"))
    assert build_request_evidence({**payload, "api_key": "DIFFERENT"}, boundary="provider_payload") == evidence


def test_evidence_bounds_component_output_without_losing_total_counts():
    evidence = build_request_evidence({"messages": [{"role": "user", "content": str(i)} for i in range(600)], "tools": [{"name": "x" * 10000}]}, boundary="provider_payload")
    assert evidence["message_count"] == 600
    assert evidence["truncated"] is True
    assert len(evidence["components"]) <= 256
    assert len(json.dumps(evidence)) < 70000


@pytest.mark.anyio
async def test_factory_wrapped_model_captures_provider_payload_and_reuse_in_real_invoke():
    store = MemoryRunEventStore()
    journal = RunJournal("run", "thread", store)
    model = with_request_evidence(ConvertedModel)()
    messages = [SystemMessage("logical system"), HumanMessage("logical user")]
    for _ in range(2):
        await model.ainvoke(messages, config={"callbacks": [journal]})
    await journal.flush()
    events = await store.list_events("thread", "run", event_types=["llm.request.evidence"])
    assert len(events) == 2
    first, second = [event["content"] for event in events]
    assert first["boundary"] == "provider_payload"
    assert first["message_count"] == 1
    expected = build_request_evidence({"messages": [{"role": "user", "content": "provider-transformed"}], "tools": []}, boundary="provider_payload")
    assert first["sha256"] == expected["sha256"]
    assert second["delta"] == {"added": 0, "removed": 0, "reused": 1, "bytes": 0}
    assert events[0]["metadata"]["llm_call_index"] == 1
    assert events[1]["metadata"]["llm_call_index"] == 2


@pytest.mark.anyio
async def test_capture_survives_provider_error_without_logging_error_text():
    store = MemoryRunEventStore()
    journal = RunJournal("run", "thread", store)
    model = with_request_evidence(ConvertedModel)()
    with patch.object(ConvertedModel, "_generate", side_effect=RuntimeError("PRIVATE-ERROR")):
        with pytest.raises(RuntimeError):
            await model.ainvoke([HumanMessage("PRIVATE")], config={"callbacks": [journal]})
    await journal.flush()
    events = await store.list_events("thread", "run", event_types=["llm.request.evidence"])
    assert len(events) == 1
    assert events[0]["content"]["boundary"] == "model_input"
    assert "PRIVATE" not in json.dumps(events)


@pytest.mark.anyio
async def test_parallel_invocations_keep_run_and_caller_evidence_separate():
    stores = [MemoryRunEventStore(), MemoryRunEventStore()]
    journals = [RunJournal(f"r{i}", f"t{i}", store) for i, store in enumerate(stores)]
    model = with_request_evidence(ConvertedModel)()
    await asyncio.gather(*(model.ainvoke([HumanMessage(str(i))], config={"callbacks": [journal], "tags": [f"middleware:test{i}"]}) for i, journal in enumerate(journals)))
    await asyncio.gather(*(journal.flush() for journal in journals))
    for i, store in enumerate(stores):
        events = await store.list_events(f"t{i}", f"r{i}", event_types=["llm.request.evidence"])
        assert len(events) == 1
        assert events[0]["metadata"]["caller"] == f"middleware:test{i}"


def test_wrapper_is_cached_and_preserves_provider_type():
    assert with_request_evidence(ConvertedModel) is with_request_evidence(ConvertedModel)
    assert isinstance(with_request_evidence(ConvertedModel)(), ConvertedModel)


@pytest.mark.anyio
@pytest.mark.parametrize("async_mode", [False, True])
async def test_streaming_records_exactly_one_provider_evidence_event(async_mode):
    store = MemoryRunEventStore()
    journal = RunJournal("run", "thread", store)
    model = with_request_evidence(ConvertedModel)()
    config = {"callbacks": [journal]}
    if async_mode:
        chunks = [chunk async for chunk in model.astream([HumanMessage("input")], config=config)]
    else:
        chunks = list(model.stream([HumanMessage("input")], config=config))
    assert chunks
    await journal.flush()
    events = await store.list_events("thread", "run", event_types=["llm.request.evidence"])
    assert len(events) == 1 and events[0]["content"]["boundary"] == "provider_payload"


def test_worst_case_unicode_evidence_fits_default_database_trace_limit():
    evidence = build_request_evidence(
        {"messages": [{"role": "user", "content": "private"} for _ in range(600)], "tools": [{"name": "😀" * 10000} for _ in range(600)], "system": "private", "instructions": "private"}, boundary="provider_payload"
    )
    assert len(json.dumps(evidence).encode()) < 9500


class InvocationOnlyModel(BaseChatModel):
    @property
    def _llm_type(self):
        return "invocation-only"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="fallback"))])


@pytest.mark.anyio
async def test_wrapper_preserves_non_streaming_provider_fallback():
    store = MemoryRunEventStore()
    journal = RunJournal("run", "thread", store)
    model = with_request_evidence(InvocationOnlyModel)()
    assert type(model)._stream is BaseChatModel._stream
    assert type(model)._astream is BaseChatModel._astream
    assert [chunk.content async for chunk in model.astream("hello", config={"callbacks": [journal]})] == ["fallback"]
    await journal.flush()
    events = await store.list_events("thread", "run", event_types=["llm.request.evidence"])
    assert len(events) == 1 and events[0]["content"]["boundary"] == "model_input"


class InterleavedModel(ConvertedModel):
    def _get_request_payload(self, messages, **kwargs):
        return {"messages": [{"role": "user", "content": messages[-1].content}]}

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        self._get_request_payload(messages, **kwargs)
        yield ChatGenerationChunk(message=AIMessageChunk(content="first"))
        yield ChatGenerationChunk(message=AIMessageChunk(content="last"))


@pytest.mark.anyio
@pytest.mark.parametrize("async_mode", [False, True])
async def test_interleaved_streams_keep_private_provider_payloads_isolated(async_mode):
    stores = [MemoryRunEventStore(), MemoryRunEventStore()]
    journals = [RunJournal(f"r{i}", f"t{i}", store) for i, store in enumerate(stores)]
    model = with_request_evidence(InterleavedModel)()
    streams = [(model.astream if async_mode else model.stream)(f"private-{i}", config={"callbacks": [journal]}) for i, journal in enumerate(journals)]
    # Keep both generators suspended after provider conversion, then finish in reverse order.
    for stream in streams:
        if async_mode:
            await anext(stream)
        else:
            next(stream)
    for stream in reversed(streams):
        if async_mode:
            assert [chunk async for chunk in stream]
        else:
            assert list(stream)
    for i, (journal, store) in enumerate(zip(journals, stores, strict=True)):
        await journal.flush()
        events = await store.list_events(f"t{i}", f"r{i}", event_types=["llm.request.evidence"])
        expected = build_request_evidence({"messages": [{"role": "user", "content": f"private-{i}"}]}, boundary="provider_payload")
        assert len(events) == 1 and events[0]["content"]["sha256"] == expected["sha256"]
