# OmniMem portability demo (other-agent integration)

`backends/omnimem/` is a **self-contained, portable** memory backend. It has
exactly **one** `from omniharness` line -- the ABC contract
(`from omniharness.agents.memory.manager import MemoryManager` in `omni_mem.py`).
Everything else is relative imports within the folder. So another agent can
adopt OmniMem in three steps, with **zero omni-harness code**.

## Three steps

1. **Vendor the host contract** -- copy `agents/memory/manager.py` (the `MemoryManager`
   ABC + `get_memory_manager()` factory + `_scan_backends()`) into your agent's
   tree. It is small and host-neutral (9 abstract methods + a drop-in factory).
   (A minimal ABC is enough if you instantiate `OmniMem` directly.)

2. **Drop the backend** -- copy the `backends/omnimem/` folder into your agent's
   `backends/`. Change exactly **one line** in `omni_mem.py`:
   ```python
   # from
   from omniharness.agents.memory.manager import MemoryManager
   # to (your agent's vendored contract)
   from <your_agent>.memory.manager import MemoryManager
   ```
   Nothing else in the folder needs editing (all other imports are relative).

3. **Configure** -- drop a `omnimem_manager.yaml` (see below) and call
   `get_memory_manager()` (or construct `OmniMem(backend_config=...)` directly).

OmniMem runs with **zero `backend_config`** (defaults: storage at
`$OMNIMEM_DATA_DIR` / `~/.omnimem/`, no LLM so non-LLM ops work; set `model` to
enable memory extraction). See `omnimem_manager.yaml`.

## Proof

`tests/test_omnimem_self_contained.py::test_portability_vendor_to_other_agent`
copies `backends/omnimem/` into a temp package, repoints the one ABC import to
a minimal vendored `manager.py`, imports it, and runs an `import_memory` ->
`get_context` round-trip -- with **zero omni-harness dependency at runtime**.

## Sample config

`omnimem_manager.yaml`:
```yaml
manager_class: omnimem
backend_config:
  storage_path: ~/.myagent/memory      # empty = $OMNIMEM_DATA_DIR / ~/.omnimem/
  model:                               # memory-update LLM (empty = no LLM)
    provider: openai                   # any langchain init_chat_model provider
    model: gpt-4o-mini
    api_key: ${OPENAI_API_KEY}
    base_url: https://api.openai.com/v1
  debounce_seconds: 30
  max_facts: 100
  # callbacks / should_keep_hidden_message: programmatic (cannot come from
  # YAML); the host factory injects them via from_config. Set programmatically
  # only if overriding the host defaults.
```
