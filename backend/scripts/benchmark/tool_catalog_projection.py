"""Synthetic projection comparison. run-live explicitly makes two configured model calls."""

import argparse
import json
import subprocess

from omniharness_extension_api import provenance_kwargs
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from omniharness.agents.middlewares.catalog_projection import project_catalog_messages
from omniharness.models.request_evidence import build_request_evidence


@tool
def lookup(city: str) -> str:
    """Look up a city's weather. This benchmark never executes the tool."""
    return city


def fixture():
    schema = {"name": "lookup", "description": "Synthetic catalog context. " * 300, "parameters": lookup.args_schema.model_json_schema()}
    messages = [
        HumanMessage("Load lookup for weather queries."),
        AIMessage(content="", tool_calls=[{"id": "catalog", "name": "tool_search", "args": {"names": ["lookup"]}}]),
        ToolMessage(content=json.dumps([schema]), tool_call_id="catalog", name="tool_search", additional_kwargs=provenance_kwargs("tool_catalog", "tool_search_selection", producer_entity_id="synthetic-v1")),
        HumanMessage("Call lookup once with city exactly Paris. Do not answer in text."),
    ]
    projected = project_catalog_messages(messages, catalog_hash="synthetic-v1", bound_names={"lookup"})
    assert projected is not None
    return messages, projected


def compare():
    original, projected = fixture()
    return {label: build_request_evidence({"messages": messages}, boundary="model_input") for label, messages in [("original", original), ("projected", projected)]}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("mode", choices=["offline", "run-live"])
    parser.add_argument("--model")
    args = parser.parse_args()
    result = {"case": "synthetic-v1", "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), "inputs": compare()}
    if args.mode == "run-live":
        from omniharness.models.factory import create_chat_model

        if not args.model:
            parser.error("run-live requires --model naming a configured model; credentials come from normal model config/environment")
        model = create_chat_model(args.model, model_overrides={"temperature": 0}, attach_tracing=False).bind_tools([lookup])
        result["model"] = args.model
        result["live"] = {}
        for label, messages in zip(("original", "projected"), fixture(), strict=True):
            response = model.invoke(messages)
            calls = response.tool_calls
            accepted = len(calls) == 1 and calls[0]["name"] == "lookup" and calls[0]["args"] == {"city": "Paris"}
            result["live"][label] = {"accepted": accepted, "usage": response.usage_metadata}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
