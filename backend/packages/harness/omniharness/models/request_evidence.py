"""Content-free request fingerprints captured at provider conversion when available."""

import asyncio
import hashlib
import json
from contextvars import ContextVar, copy_context
from functools import lru_cache

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables.config import ensure_config

_CAPTURE: ContextVar[list | None] = ContextVar("request_evidence_capture", default=None)


def _bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=lambda obj: obj.model_dump() if hasattr(obj, "model_dump") else str(obj)).encode("utf-8")


def _fingerprint(value):
    data = _bytes(value)
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def build_request_evidence(payload: dict, *, boundary: str) -> dict:
    # Whitelist content surfaces. Credentials, headers, endpoints and arbitrary provider kwargs never enter evidence.
    messages = payload.get("messages", payload.get("input", []))
    if not isinstance(messages, list):
        messages = [messages]
    tools = payload.get("tools", [])
    if not isinstance(tools, list):
        tools = []
    components = []
    for index, message in enumerate(messages[:16]):
        message = message.model_dump() if hasattr(message, "model_dump") else message
        role = message.get("role", message.get("type", "unknown")) if isinstance(message, dict) else "unknown"
        role = role if role in {"system", "developer", "human", "user", "ai", "assistant", "tool", "function"} else "unknown"
        components.append({"index": index, "kind": role, **_fingerprint(message)})
    tool_evidence = []
    for candidate in tools[:8]:
        function = candidate.get("function", candidate) if isinstance(candidate, dict) else {}
        name = function.get("name", "unknown") if isinstance(function, dict) else "unknown"
        tool_evidence.append({"name": str(name)[:64], **_fingerprint(candidate)})
    surfaces = {"messages": messages, "tools": tools}
    for key in ("system", "instructions"):
        if key in payload:
            surfaces[key] = payload[key]
            components.append({"kind": key, **_fingerprint(payload[key])})
    return {"version": 1, "boundary": boundary, **_fingerprint(surfaces), "message_count": len(messages), "tool_count": len(tools), "components": components, "tools": tool_evidence, "truncated": len(messages) > 16 or len(tools) > 8}


def capture_provider_payload(payload: dict) -> None:
    """Provider-owned adapters may mark their last content conversion boundary."""
    capture = _CAPTURE.get()
    if capture is not None:
        try:
            capture[:] = [build_request_evidence(payload, boundary="provider_payload")]
        except Exception:
            pass


def _start(messages, kwargs):
    try:
        capture = [build_request_evidence({"messages": messages, "tools": kwargs.get("tools", [])}, boundary="model_input")]
    except Exception:
        capture = []
    return capture, _CAPTURE.set(capture)


def _finish(capture, token, manager):
    _CAPTURE.reset(token)
    if manager is None or not capture:
        return
    for handler in manager.handlers:
        record = getattr(handler, "record_request_evidence", None)
        if callable(record):
            try:
                record(str(manager.run_id), capture[-1])
            except Exception:
                # Observability cannot change provider outcomes.
                pass


class _StreamRecorder(BaseCallbackHandler):
    run_inline = True

    def __init__(self, capture, handlers):
        self.capture, self.handlers, self.run_id = capture, handlers, None

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        self.run_id = str(run_id)
        try:
            self.capture[:] = [build_request_evidence({"messages": messages[0], "tools": kwargs.get("invocation_params", {}).get("tools", [])}, boundary="model_input")]
        except Exception:
            pass

    def _record(self):
        if self.run_id is None or not self.capture:
            return
        for handler in self.handlers:
            record = getattr(handler, "record_request_evidence", None)
            if callable(record):
                try:
                    record(self.run_id, self.capture[-1])
                except Exception:
                    pass
        self.run_id = None

    def on_llm_end(self, response, **kwargs):
        self._record()

    def on_llm_error(self, error, **kwargs):
        self._record()


def _stream_config(config, model, capture):
    config = ensure_config(config)
    callbacks = config.get("callbacks")
    handlers = list(callbacks if isinstance(callbacks, list) else getattr(callbacks, "handlers", []))
    own = model.callbacks
    handlers.extend(own if isinstance(own, list) else getattr(own, "handlers", []))
    recorder = _StreamRecorder(capture, handlers)
    if callbacks is None or isinstance(callbacks, list):
        config["callbacks"] = [*(callbacks or []), recorder]
    else:
        manager = callbacks.copy()
        manager.add_handler(recorder)
        config["callbacks"] = manager
    return config


def _next_chunk(iterator):
    try:
        return True, next(iterator)
    except StopIteration:
        return False, None


async def _anext_chunk(iterator):
    try:
        return True, await anext(iterator)
    except StopAsyncIteration:
        return False, None


@lru_cache(maxsize=64)
def with_request_evidence(model_class):
    if issubclass(model_class, RequestEvidenceMixin):
        return model_class
    return type(f"Evidence{model_class.__name__}", (RequestEvidenceMixin, model_class), {"__module__": model_class.__module__})


class RequestEvidenceMixin:
    def _get_request_payload(self, *args, **kwargs):
        payload = super()._get_request_payload(*args, **kwargs)
        capture_provider_payload(payload)
        return payload

    def _generate_with_cache(self, messages, stop=None, run_manager=None, **kwargs):
        capture, token = _start(messages, kwargs)
        try:
            return super()._generate_with_cache(messages, stop=stop, run_manager=run_manager, **kwargs)
        finally:
            _finish(capture, token, run_manager)

    async def _agenerate_with_cache(self, messages, stop=None, run_manager=None, **kwargs):
        capture, token = _start(messages, kwargs)
        try:
            return await super()._agenerate_with_cache(messages, stop=stop, run_manager=run_manager, **kwargs)
        finally:
            _finish(capture, token, run_manager)

    def stream(self, input, config=None, **kwargs):
        # BaseChatModel.stream does not pass its run manager to provider _stream.
        # A private context per iterator prevents interleaved consumers from sharing capture state.
        context = copy_context()
        capture, token = context.run(_start, [], kwargs)
        iterator = super().stream(input, config=_stream_config(config, self, capture), **kwargs)
        try:
            while True:
                present, chunk = context.run(_next_chunk, iterator)
                if not present:
                    break
                yield chunk
        finally:
            context.run(iterator.close)
            context.run(_CAPTURE.reset, token)

    async def astream(self, input, config=None, **kwargs):
        context = copy_context()
        capture, token = context.run(_start, [], kwargs)
        iterator = super().astream(input, config=_stream_config(config, self, capture), **kwargs)
        try:
            while True:
                present, chunk = await asyncio.create_task(_anext_chunk(iterator), context=context)
                if not present:
                    break
                yield chunk
        finally:
            await asyncio.create_task(iterator.aclose(), context=context)
            context.run(_CAPTURE.reset, token)
