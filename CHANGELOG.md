# Changelog

All notable changes to OmniHarness are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [2.1.0] — 2026-09-24

### ⚠ Breaking changes

- **gateway:** Request trace ids are now issued unconditionally, and every
  Gateway HTTP response carries an `X-Trace-Id` header. Previously both were
  gated behind `logging.enhance.enabled`, which now controls **log output
  only** — whether records carry a `trace_id` field, and in which format. The
  header cannot be turned off; installations running the default
  `enabled: false` will start seeing it after upgrading. Scheduled tasks, MCP
  task notification runs, IM channel messages, and the embedded
  `OmniHarnessClient` bind an id per unit of work, so the id also reaches the run
  record, the checkpoint metadata, and Langfuse traces that previously had
  none. A `omniharness_trace_id` supplied in a run request's `metadata` or
  `config.context` is now ignored and overwritten so the response header, the
  logs, and the persisted run cannot disagree — send the `X-Trace-Id` request
  header to pin a correlation id across services. `logging` remains
  restart-required. No config keys were added or removed.
- **sandbox:** E2B now enforces `sandbox.replicas` as a process-local capacity
  limit. The default `wait` policy waits for `acquire_timeout`, then fails the
  agent turn. OmniHarness does not retry the turn automatically. Use `burst` with
  `burst_limit` to permit bounded extra VMs. The `reject` policy can remove one
  warm VM before it returns a capacity error.
- **memory:** The memory system is now pluggable (`memory.manager_class` selects
  a backend; default `omnimem` is self-contained). OmniMem-private settings moved
  from the top level of `memory:` into `memory.backend_config`, and the
  `/memory/config` response (and `client.get_memory_config()`) changed shape.
- **memory:** Custom `memory.storage_class` moved: the old default path
  `omniharness.agents.memory.storage.FileMemoryStorage` no longer exists (now
  `omniharness.agents.memory.backends.omnimem.omnimem.core.storage.FileMemoryStorage`).
  Custom `MemoryStorage` subclasses must accept `config` in `__init__` (was
  no-arg). A broken/old `storage_class` logs an error and falls back to
  `FileMemoryStorage` (won't crash) -- update the path + signature to restore it.
- **memory:** `memory.mode: tool` with a backend that does not implement
  `search()` now fails fast at Gateway startup with a `ValueError` from the
  `MemoryManager` invariant, instead of starting successfully and silently
  returning empty results on every `memory_search` call. Both shipping backends
  implement `search()` (OmniMem retrieves; `noop` returns `[]`), so this only
  affects a custom backend that onboards without overriding `search()`. It is
  intentional -- silent empties are worse than a loud startup error. Fix: switch
  to `mode: middleware` or override `search()` (and set `supports_search=True`).
- **docker:** The published entry port now binds to loopback (`127.0.0.1`) by
  default in both compose files, matching the documented local-trust deployment
  model. Deployments that relied on the old `0.0.0.0` binding must set
  `BIND_HOST` to expose the stack on other interfaces.
- **scheduled-tasks:** Upcoming cron occurrences can be inspected before a task
  is saved. `POST /api/scheduled-tasks/preview-cron` takes a five-field cron
  expression, a timezone, a `count` of 1–10 (default 5), and an optional aware
  reference time, and returns the normalized cron, the effective UTC reference,
  and the occurrences in both UTC and local time. It runs the scheduler's own
  calculator in a worker thread, so DST handling matches what a saved task will
  actually do, and it reserves nothing and touches no task, thread, or run
  store; invalid input and date-range failures return 422.
- **scheduled-tasks:** Run history can be filtered server-side by occurrence
  status. Finding a rare failure used to mean downloading every history page
  and filtering in the client, since a failure behind many newer successes
  could sit on any page; `GET /api/scheduled-tasks/{task_id}/runs` now accepts
  `?status=` with `queued`, `launching`, `running`, `success`, `failed`,
  `skipped`, and `interrupted`, applying the predicate before pagination so
  `?status=failed&limit=50&offset=0` returns the first page of real failures.
  Unknown values, including the parent task's own `completed`, return 422,
  empty results return `[]`, and the unfiltered array response is unchanged.

#### Authentication
- **auth:** Personal access tokens (PAT) for programmatic API access:
  `POST/GET/DELETE /api/v1/auth/pats` manage tokens (shown once, stored as
  SHA-256 digests); a default-deny route policy admits only the thread/run
  lifecycle routes, narrowed further by the token's `threads`/`runs` scopes,
  and any request dimension that carries cancel capability (`?action=`,
  `multitask_strategy`) additionally requires `runs:cancel`.
- **settings:** Account preferences survive a cleared browser or a move to
  another device. The notification toggle, default model, conversation mode,
  and reasoning effort are stored as independent `(user_id, key)` rows behind
  session-authenticated `GET`/`PATCH /api/v1/auth/preferences`, hydrated from
  the server before first paint, with a tab-local outbox and capped-backoff
  retry so a failed write is not silently dropped; `null` resets a field. Only
  those four allowlisted fields are transmitted — device notification
  permission, display settings, and thread-specific model overrides stay local,
  and an automatic composer fallback is never uploaded as an explicit account
  preference. Existing unscoped local settings are not migrated, since they
  carry no known owner, so users reselect these four once after upgrading. or a custom agent the owner already has. Unknown or malformed names
  return 422. The workspace create/edit form exposes the same choice.
- **gateway:** `GET /api/threads/{thread_id}/runs/page` walks thread run history
  with a `(created_at, run_id)` keyset cursor (`{data, has_more,
  next_before_created_at, next_before_run_id}`). `GET /api/threads/{thread_id}/runs`
  still returns a bare array of the newest 100 runs so LangGraph SDK clients keep
  working.
- **middleware:** New `TokenBudgetMiddleware` enforces a per-run token budget,
  shared additively across the lead agent and subagents.
- **context:** Record the effective memory identity per run and persist durable
  context (system messages, memory, and tool state) across summarization,
  emitting it as structured runtime metadata so compaction no longer drops it.
- **runtime:** Goal continuations let a run resume toward a goal across multiple
  agent turns, with `continuation_count` tracked and capped.
- **subagents:** A system-maintained delegation ledger prevents redundant
  re-delegation of an in-flight task, and a total delegation cap bounds fan-out
  per run.
- **subagents:** Persist and display subagent step history in the thread.
- **files:** Deterministic read-before-write version gate for file tools
  prevents clobbering concurrent edits.
- **gateway:** Cache-aware cost accounting attributes token costs to cached vs.
  uncached paths; a Redis stream bridge enables distributed event streaming; and
  manual context compaction is exposed to the user.
- **gateway:** The stream-bridge heartbeat interval is configurable via
  `stream_bridge.heartbeat_interval_seconds` (default 15s), so deployments
  behind aggressive proxy idle timeouts can tune SSE, `/wait`, and internal
  subscribers together.
- **runtime:** Delta-mode checkpoint history cache (memory/redis) with O(1)
  incremental composition, configured via `database.checkpoint_cache`.
- **agents:** Per-agent model and generation settings (`temperature`,
  `max_tokens`, `thinking_enabled`, `reasoning_effort`) override the shared
  model profile.
- **uploads:** Lazy-load historical files via a `list_uploaded_files` tool
  instead of injecting the full manifest.
- **runtime:** Every tool call now carries a runtime-stamped, tamper-evident
  tool receipt, and a bounded receipt ledger is injected into the model
  context so agents can cite execution evidence in their reports. Enabled
  by default via the new `verification` config section.
- **subagents:** Subagent delegations are now verifiable, layering the RFC:
  every subagent's report contract requires citing tool receipts (e.g.
  `[r3 write_file]`) and attaching a verifiable handle to each deliverable,
  the lead agent cross-checks those citations against the subagent's actual
  execution record, and `acceptance_criteria` on a `task` delegation are
  checked deterministically parent-side (file existence/non-emptiness,
  recorded test-command exit status) with anything undecidable reported
  UNVERIFIED instead of silently passed.
- **clarification:** Human-input (clarification) cards support structured
  form fields, so an agent can request exactly the input it needs instead
  of free text only.
- **subagents:** A Settings page manages a deployment-level Subagent catalog
  (admin-managed worker definitions alongside built-in and `config.yaml`
  ones), and Custom Agents can restrict delegation to an explicit worker
  allowlist enforced at both prompt and execution time.
- **agents:** The current-date context injected into lead- and subagent
  prompts honors the optional `OMNI_HARNESS_DATE_TIMEZONE` env var (IANA name,
  e.g. `Asia/Shanghai`), so users in non-UTC deployments are no longer told
  the wrong "today" around midnight; unset keeps server-local behavior.
- **agents:** The read-before-write gate now elides the dead payload of a
  blocked `write_file` / `str_replace` call (`content`, `old_str`, `new_str`)
  from model-bound requests. A blocked call never ran and must be re-issued
  after a re-read, so the original arguments only cost context; stored history,
  receipts, and the run journal keep them. Blocked results are paired with call
  occurrences (tool-call ids may repeat across turns), and a request whose
  history was rewritten drops OpenAI `resp_` response ids so
  `use_previous_response_id` chaining cannot resume the original server-side
  history. Controlled by `read_before_write.elide_blocked_payloads` (default
  on) and `read_before_write.elide_min_chars` (default 2000).
- **agents:** Custom Agent `config.yaml` accepts `memory_enabled: false` to run
  an agent as a stateless execution worker; omission defaults to `true`. The
  opt-out removes only that agent from the memory lifecycle — recalled-memory
  injection, passive capture, the `memory_search` / `memory_add` /
  `memory_update` / `memory_delete` tools, and tool-mode memory guidance are
  all suppressed, and both automatic summarization and manual `/compact` skip
  the durable memory flush. Switching an existing agent off clears only the
  frozen, server-tagged memory reminders from checkpoint state: date reminders,
  real user messages, and untagged lookalikes survive, and the global memory
  setting is unchanged for every other agent.
- **subagents:** Durable `batch_task` items accept the same optional
  `acceptance_criteria` that ordinary `task` delegations already take, so a
  batch worker can no longer claim a missing deliverable exists and still land
  as a succeeded item with no recorded check. Criteria are normalized before
  persistence (20 usable entries, 500 characters after neutralization; empty
  becomes `null`) and preserved across lease recovery, and a completed
  execution reuses the existing deterministic checker against owner-scoped
  thread files and recorded test-command evidence. Item queries and JSONL
  exports gain nullable `acceptance_criteria` and a separately validated
  `acceptance_verdict` (`holds`, `does not hold`, or `UNVERIFIED`): a completed
  item with a report, a missing CSV, and an unsupported quality claim stays
  `succeeded` with those three leaves and is not retried automatically. Items
  without criteria and legacy rows report no verdict.
- **context:** Opt-in task notes and compacted-history recall, gated by
  `task_continuity.enabled` (default `false`; the config schema gains the
  section with disabled defaults). Enabling it exposes `task_note`,
  `history_search`, and `history_read` to standard lead agents and
  `OmniHarnessClient` under the existing authorization and skill policies, with
  both sync and async tool execution. `task_note` keeps short checkpointed
  notes of constraints, decisions, failed attempts, and next steps in a shared
  state channel that enforces notebook limits and report shape on every write,
  rendered as escaped historical data in the durable-context human message.
  Automatic and manual compaction additionally preserve bounded message and
  tool text — including genuine hidden clarification-card answers — into a
  user/thread-local SQLite FTS5 archive outside the sandbox mount, which
  `history_search` and `history_read` then query; malformed checkpoint metadata
  is reported as unavailable instead of aborting a model call or compaction,
  and a storage failure leaves ordinary compaction working. This is lexical
  recall within one task: it does not resume runs, replicate archives across
  hosts, or create cross-thread memory, and it adds no embedding dependency.
- **gateway:** A Gateway run can be asked to read a specified earlier
  conversation. Opt-in `read_conversation` plus a `conversation_references` run
  field (up to three thread ids or same-origin chat URLs) grant the lead agent
  a model-facing read of a previous conversation while it continues the current
  task; ordinary message text never confers access, and the grant is bound to
  that run's references, the run's `runs:read` permission, and ownership of
  each source. Reads reuse the existing transcript pagination and visibility
  rules, returning bounded user and assistant text with source ids,
  continuation cursors, and truncation or unavailability notices while
  excluding hidden context, reasoning blocks, and raw tool results. The reader
  is never persisted in configuration and is released when the run ends, so
  resume and replay need the references again; bootstrap, subagent, and
  ordinary embedded paths do not receive it. Text is capped at 4,000 characters
  per message and 20,000 per page.
- **tools:** `list_uploaded_files` accepts optional `query` (a case-insensitive
  filename substring) and `extensions` (`"pdf"` or `".PDF"`, both meaning
  `.pdf`), and both filters run **before** the 20-file truncation that
  lazy-loading history already applied. Previously the cap hit the unfiltered
  mtime-sorted list, so "analyze those PDFs I uploaded before" in a thread full
  of newer screenshots pushed the PDFs into `omitted_summary` and left the
  agent with no path to hand `read_file`; `total_count`, `truncated`, and
  `omitted_summary` now describe the filtered set. Omitting both parameters
  keeps today's behavior, the two filters combine with AND, blank or invalid
  values count as no filter, and a filtered miss returns `No uploaded files
  matched the given filters.`.

#### Memory

- **memory:** Memory consolidation synthesizes fragmented facts, and a staleness
  review prunes silently-outdated facts using LLM-assigned per-fact
  `expected_valid_days` / `staleFactsToExtend`.
- **memory:** Guaranteed injection of correction facts (with graceful fallback)
  so user corrections always reach the model.
- **memory:** Incremental agent-scoped Markdown fact storage isolates per-agent
  facts and updates a single fact without rewriting or reindexing the whole
  collection.
- **memory:** A built-in FTS5/BM25 retrieval adapter provides full-text
  search over stored memories without an external retrieval service.
- **memory:** New pluggable memory backends: OpenViking and mem0 over HTTP,
  plus Honcho as a user-model memory provider.
- **memory:** A hybrid fact eviction policy blends multiple signals when
  deciding which stored facts to drop as memory fills.

#### Skills

- **skills:** The built-in image-generation skill can use OpenAI-compatible
  Images APIs for generation and reference-image editing, with configurable
  endpoint, model, size, and output format. statically analyzes skill packages at
  load, and `describe_skill` enables deferred discovery so the model fetches a
  skill's schema on demand instead of loading all skills up front.
- **skills:** Per-user custom skill isolation with sandbox mounting.
- **skills:** Install local `.skill` archives directly from the Skills
  settings page, reusing the existing per-user installer and security scan.
- **skills:** Custom skills can be exported from Settings, disabled ones
  included, so what you back up, move between installations, or send a teammate
  is the version actually installed rather than the original upload. A
  bilingual preview lists package size, paginated file paths, declared
  requirements, and actionable blockers, and the two new admin-only manifest
  and download endpoints bind that preview to a revision digest — a package
  changed in between returns `409` instead of a stale ZIP. Supporting files,
  empty directories, and normalized executable permissions survive the round
  trip, while links, special files, nonportable paths, nested skill roots, and
  executable binaries are rejected. Export copies raw saved files and is not a
  redaction step: it neither scans for secrets nor runs skill scripts, so
  credentials and account settings must still be configured separately.

#### Models & integrations

- **community:** New web search/fetch engines - GroundRoute, Crawl4AI
  (`web_fetch`), and a fastCRW provider - plus a Browserless `web_capture`
  screenshot tool and Brave `image_search`.
- **mcp:** Per-server `tool_call_timeout` for MCP tool calls, and routing hints
  that guide the model to the right server.
- **mcp:** Add an official OpenViking `/mcp` example that exposes the native
  tool set through OmniHarness's generic MCP client.
- **community:** Lark/Feishu CLI integration bundles the runtime install, the
  official `lark-*` skill pack, and an interactive auth flow so the integration
  is no longer environment-dependent.
- **acp:** MiniMax Code (`mcode acp`) is supported and documented as a
  native external coding agent, and ACP thought chunks are no longer
  concatenated into tool results.
- **community:** New web search providers - Serply (with news and scholar
  verticals) and Tencent Cloud WSA - plus native recency filters
  (day/week/month/year) shared across DDGS, Brave, Tavily, and SearXNG.
- **community:** New Sofya `web_search` and `web_fetch` provider - search
  results carry the content of each page, capped per result so a default
  search stays inline.
- **knowledge:** Opt-in read-only LightRAG retrieval is an alternative
  `knowledge_search(query)` provider for the same `knowledge` group —
  operators pick RAGFlow or LightRAG by which entry is configured. It queries
  LightRAG's structured `/query/data` endpoint (no LLM generation), formats
  the ranked chunks as citation-numbered text, redacts the optional
  `X-API-Key` on every model-visible path, and maps server error messages to
  actionable tool errors.
- **models:** Bounded concurrency does not bound request rate: several
  concurrent runs could still exhaust a provider's requests-per-minute
  allowance, and nothing paced the demand before dispatch, so a 429 was the
  first signal anything was wrong. A new optional `models[].request_admission`
  block admits model calls through a process-local queue, taking
  `requests_per_minute` (required), an optional `group` (defaults to the model
  config name), `max_wait_seconds` (default `300`) and `max_queue_size`
  (default `256`); at 60 RPM admissions land at least a second apart, and idle
  periods accumulate no burst credit. One bounded FIFO is shared across
  synchronous callers, independent asyncio loops and every model instance in an
  explicit group, whose policies must be identical — a conflicting setting
  fails construction and needs a restart. Cancellation and timeout drop a
  waiter without consuming an admission, and a full queue fails before
  dispatch. The limiter attaches through the LangChain `BaseChatModel` hook, so
  agent models, the invoke and stream paths and factory-created auxiliary
  models are all covered, and the factory strips the policy from provider
  kwargs and sets the exposed SDK `max_retries` to zero so retries cannot
  silently bypass the hook — existing agent middleware retries re-enter
  admission, while non-middleware callers lose SDK retries. Budgets are per
  process, so an operator must partition an account allowance across workers,
  replicas and other clients; the limiter counts requests, not tokens, and
  unconfigured models behave exactly as before.

#### MCP

- **mcp:** A durable task runtime for MCP: long-running tool tasks survive
  Gateway restarts through a durable driver, and their progress and
  completion notifications surface in the chat UI.
- **mcp:** Shared MCP servers can inject per-user credentials: a single
  server entry authenticates each OmniHarness user with their own header
  value, unmapped users are denied by default, and stored credentials are
  masked in Gateway API responses.
- **mcp:** Settings > Tools can add, edit, and delete MCP servers through
  targeted Gateway endpoints, with a copy-paste JSON workflow that preserves
  advanced fields and masked secret placeholders.
- **mcp:** An optional `parallel-search` server entry
  (`https://search.parallel.ai/mcp`, HTTP, no auth by default) ships in
  `extensions_config.example.json`, disabled by default; enabling it exposes
  `parallel-search_web_search` and `parallel-search_web_fetch`, with optional
  Bearer authentication documented.

#### Channels

- **channels:** Expose the IM `channel_user_id` to sandbox commands as
  `OMNIHARNESS_CHANNEL_USER_ID`.
- **channels:** Inbound webhook deduplication moves to Postgres, so several
  Gateway pods can serve the same IM channel without double-processing
  events.
- **channels:** New Buzz (Nostr) channel connector, including the frontend
  experience for the channel.
- **channels:** `/agent list` and `/agent use <name>` IM commands let a
  conversation switch to the owner's Custom Agents: the selection is
  persisted in thread metadata (restored after restart) and wins over stale
  channel defaults, IM-created threads route through the same agent when
  opened in the web UI, and `/agent` is reserved across the slash-skill
  parser, frontend, and TUI so no skill can shadow the command.
- **guardrails:** Authenticated runtime context is exposed in `GuardrailRequest`,
  and security interventions are persisted as run events.
- **auth:** "Keep me signed in" login option with a centralized session-cookie
  policy (persistent `Secure` cookies on HTTPS, session cookies on public HTTP).
- **authz:** Built-in RBAC authorization provider with a unified factory, plus
  tool-authorization enforcement at both assembly (tools removed before the
  model sees them) and runtime (denied calls blocked).
- **authz:** Gateway route permissions are derived from the configured
  AuthorizationProvider rather than a fixed table.
- **authz:** Model authorization is enforced at Gateway routes and again in
  the agent runtime, and `sandbox:execute` is checked when a sandbox is
  acquired - users can no longer reach models or sandboxes they are not
  authorized for.
- **authz:** `GET /auth/me` now surfaces the caller's effective route
  permissions (the RFC Phase 4), read from the `AuthContext` the auth
  middleware already stamps on every authenticated request — no extra
  provider evaluations — so the frontend can hide actions the caller's role
  cannot perform.

#### Sandbox & provisioner

- **sandbox:** New E2B and BoxLite (micro-VM) sandbox providers; BoxLite ships
  with a warm pool.
- **provisioner:** ClusterIP Services and scoped per-skill PVC mounts, plus a
  configurable sandbox container port.
- **sandbox:** New cloud sandbox providers: Tenki and OpenSandbox.
- **sandbox:** An optional lark-cli credential broker sidecar (K8s
  provisioner mode) keeps Lark app secrets and OAuth tokens out of the
  sandbox filesystem entirely - the sandbox sees only a shim that forwards
  commands to a loopback broker in the pod. Off by default.
- **sandbox:** An E2B sandbox carries a structured `MountUploadResult`
  (`truncated`, `reason`, upload totals) after creation — preserved across
  warm-pool reclaim within the process — so mount truncation by a resource
  limit is observable in code instead of only in Gateway logs.

#### Extensions & plugins

- **extensions:** An out-of-tree Python extension system: extensions can
  contribute middleware, task-lifecycle and system-model observers, Gateway
  services, and HTTP routers, and are managed with `omniharness extensions`
  install/enable/disable/remove.
- **extensions:** Extensions can observe what the agent did - message
  provenance, middleware policy declarations, agent-assembly fingerprints,
  context-compaction records, guardrail decisions, and the MCP origin of a
  tool. `omniharness-extension-api` moves to 0.2.0; extensions written against
  0.1 are refused at startup with an install hint.
- **extensions:** `omniharness extensions upgrade SOURCE` (also exposed as `make
  extension-upgrade SOURCE=...`) replaces a managed local snapshot, or re-pins
  a requirement already in the `extensions` group, and adopts the existing
  `plugins:` record so its private `config` and `required` survive. Moving to a
  newer pin used to mean `remove` then `install`, and `remove` deletes the
  whole record — secrets included — while an already-snapshotted local
  directory could not be reinstalled at all without editing the managed copy by
  hand. Plain `install` is unchanged and still refuses an existing local
  snapshot, upgrading a source that is not installed fails closed with an
  install hint, and a failed upgrade restores the previous snapshot even when a
  concurrent `pyproject.toml` / `uv.lock` edit blocks dependency-file rollback.

#### Persistence

- **persistence:** A custom PostgreSQL schema can be selected via
  `postgres_schema`; ORM, LangGraph checkpointer, and store tables are all
  created there, and the schema is created automatically at startup.

#### Frontend

- **frontend:** Branching support for assistant turns and side conversations for
  quoted follow-ups.
- **frontend:** Regenerate the latest answer.
- **frontend:** Citation-sources evidence panel, workspace change review for
  agent runs, and a visualized `ask_clarification` card.
- **frontend:** Voice dictation, prompt-history recall with arrow keys, composer
  input polishing, and a "(thought for N seconds)" thinking-duration chip.
- **frontend:** Feature-gate the agents UI behind the `agents_api` flag, and
  persist AI turn duration in backend and UI.
- **frontend:** Render slash-skill activations as inline chips.
- **frontend:** Pin recent chats.
- **frontend:** Real-time context window usage is shown as a conversation
  grows.
- **frontend:** Replies can be typed and sent while a clarification card is
  pending.
- **artifacts:** Text artifacts can be edited inline in the artifact panel., and all files presented in a run
  can be downloaded as one zip archive derived from the run's delivery
  receipt.
- **frontend:** Browser Live is available in Custom Agent chats.
- **frontend:** Scheduled tasks can be duplicated into an editable draft that
  carries over the configuration but not the run history.
- **frontend:** Chats can be archived and restored: an Archive sidebar
  action with an Undo toast, Recent chats / Archived tabs above search, and
  per-chat restore controls; SQL and Memory stores apply the archive filter
  before pagination while messages, files, links, pin state, and the current
  URL are preserved.
- **artifacts:** Completed CSV/TSV artifacts preview as bounded tables (up to
  200 rows × 50 columns, 50 rows per page, sticky headers, optional
  first-row header) parsed off the main thread over the existing 1 MiB
  range loader — literal strings, leading zeros, and multiline quoted cells
  survive, long cells open in a copyable dialog, and source view remains
  one toggle away.
- **projects:** Projects MVP Phase 2 makes a project do its job rather than
  just name a folder. Project instructions — previously stored, editable, and
  read by nothing — now reach the model on every member-thread run as a
  bounded, user-role `<project>` block in that run's request only, never the
  system prompt or persisted history, with renames taking effect on the next
  run and oversized text rejected at write time rather than truncated. A
  per-project document shelf gains a Documents tab (upload, list with
  provenance, preview, download, move-to-trash, content-hash dedup) that the
  agent reads on demand through `list_project_documents` /
  `read_project_document` — registered only in project runs, text only — plus
  promotion in both directions: *Save to project* copies any thread file onto
  the shelf with provenance, and *Attach to thread* ingests a shelf document
  back into a conversation through the normal upload pipeline. A read-only
  conversation-files view aggregates member threads' uploads and outputs, and
  project deletion finally has a trash tier.
- **frontend:** Conversations can be referenced from the composer. A "Reference
  a conversation" button sits beside the attachment button, rendered only while
  `/api/features` reports the capability, and opens a picker over the same
  recent-conversation list the sidebar uses — never offering the current
  conversation, and capped at the reported `max_references` (3 today), where
  rows past the cap are disabled and selected ones stay clickable to remove.
  Attached conversations appear as removable chips in the composer and as
  read-only chips linking back to the source in the transcript. References are
  per message: not saved with a draft, cleared on send or thread change, and
  regenerating or editing a turn runs without them unless re-attached.

#### Observability & tooling

- **observability:** Trace-id correlation with enhanced logging and agent
  observability via Monocle.
- **tooling:** A Hermes-like terminal workbench (`omniharness` CLI) backed by
  `OmniHarnessClient`, plus a redacted community support-bundle generator.
- **setup:** The setup wizard now asks whether OpenAI-compatible gateway models
  support thinking, and a Volcengine Coding Plan quick-setup path was added.
- **tui:** `clear` command.
- **gateway:** New `GET /health/ready` readiness probe runs a bounded
  database `SELECT 1` and returns 503 while the database is unreachable
  (200 `not_configured` for the memory backend); `/health` stays pure
  liveness, and the production compose healthcheck now gates on readiness.
- **client:** Context compaction stores its result in
  `ThreadState.summary_text`, outside `messages`, but the embedded client's
  `values` event selected only the title, messages and artifacts — so a
  consumer outside the Gateway, such as a benchmark runner, had no way to
  observe the summary through the public event stream. Every embedded `values`
  event now carries `summary_text`, `None` when absent, forwarding updates,
  repeats and clears as state snapshots. Message serialization, AI-delta
  deduplication, tool artifacts and usage accounting are unchanged, and no
  checkpoint internals are exposed. An initial snapshot can already contain a
  restored summary, so a changed value alone is not a causal compaction event.
- **skills:** An active restrictive skill must explicitly list `task` in
  `allowed-tools` to delegate to a subagent. Read-only discovery infrastructure
  (`tool_search` and `describe_skill`) remains available, but cannot grant schema
  visibility or execution for a denied business tool.
- **memory:** Added `memory.mode` (`middleware` | `tool`); `tool` mode registers
  memory tools (`memory_search`/`add`/`update`/`delete`) the model calls directly
  instead of passive per-turn summarization. `manager_class` resolution is now
  fail-fast (raises `ValueError` on an unknown backend instead of silently
  falling back).
- **sandbox:** The host->virtual output-masking regex now has a single owner,
  eliminating duplicated pattern compilation.
- **memory:** The OpenViking memory backend now uses the official OpenViking
  adapter; the old trusted-mode `auth_mode`/`account` fields are rejected in
  favor of a credential-bound USER API key.
- **agents:** Subagent delegation is now routed by net benefit: the lead agent
  defaults to direct execution unless parallel latency, specialist capability,
  or context isolation clearly pays off.
- **persistence:** Heal databases that silently skipped the run-change clock
  schema. `0023_run_change_seq` was inserted ahead of the already-shipped
  `0023_user_preferences` revision, so databases stamped at that revision (or
  later) treat it as an applied ancestor and never execute it — leaving the
  `run_change_clock` table and the `runs.change_seq` column permanently
  missing, and the first thread deletion (any run-store change-clock bump)
  fails with `no such table: run_change_clock`. The new
  `0025_repair_run_change_seq` revision re-applies the same guarded DDL on
  upgrade and no-ops on healthy shapes. `RunChangeClockRow` and
  `UserPreferenceRow` are also registered in the ORM model registry so
  `create_all` and autogenerate see every table through explicit imports
  instead of module side effects.
- **models:** Guard the Claude Code credential loader against a malformed
  `claudeAiOauth` container. `~/.claude/.credentials.json` can hold a
  syntactically valid JSON payload whose `claudeAiOauth` value is not an
  object — a `null` left by a partial export, a raw string, an array, a
  number — and the extractor called `.get` on it, raising `AttributeError`
  out of `ClaudeChatModel.model_post_init` and aborting model construction,
  the opposite of the loader's documented degrade-gracefully behavior (the
  sibling Codex loader already guarded the identical shape). A non-object
  top-level payload or `claudeAiOauth` value now logs at debug level and
  counts as "no credential from this source", so loading falls through to
  the next source and ultimately returns `None` when every source is
  unusable.
- **setup:** Honor a custom sandbox image in BOM-prefixed configs.
  `setup-sandbox.sh` matched `^sandbox:` against a first line still carrying
  its UTF-8 BOM, never matched, and silently chose and pulled the default
  image instead of the configured one, although the runtime YAML loader
  accepts the same configuration. The script now strips a UTF-8 BOM at the
  beginning of the first line before the image-selection pipeline, with no
  new runtime dependency.
- **models:** Pair Codex invalid tool calls with their tool results. A Codex
  model that emits a `function_call` whose `arguments` are not valid JSON
  does not fail the turn: the call is parked on `invalid_tool_calls` and
  answered with a placeholder `ToolMessage` by `DanglingToolCallMiddleware`,
  so the model sees a recoverable tool error. But the Codex Responses
  serializer emitted input items for valid `tool_calls` only, so the
  placeholder reached the provider as a `function_call_output` whose
  `call_id` had no matching `function_call` in the same request, and the
  Responses API requires the pair — the exact case the middleware exists to
  recover from ended in a provider error instead of a retry. Chat
  Completions providers already replay invalid calls through LangChain's
  converter, and the OpenAI-compatible path had the same failure class
  repaired in the middleware; Codex requests now also replay
  `invalid_tool_calls` as `function_call` input items next to the valid
  ones. The valid-call path, the parse side, and the middleware are
  unchanged.
- **middleware:** Stop loop detection from cutting off an agent that pages
  through a file. `read_file` calls were keyed by 200-line buckets, so every
  read shorter than a bucket collapsed onto its neighbours: five sequential
  40-line reads hashed identically and tripped the hard stop, ending the run
  with a forced final answer and `stop_reason=loop_capped` — on exactly the
  ranged reads `read_file`'s own truncation notice tells the model to make. The
  key now uses the exact line window, with an omitted `end_line` kept
  open-ended so a bare read and an explicit `start_line=1` still share one key.
  Repeating a single range is still caught at the same threshold, and a read
  loop that varies its bounds remains covered by the per-tool frequency layer.
- **scheduler:** Enforce the global `max_concurrent_runs` budget on SQLite,
  which previously only held on Postgres. Claiming a queued occurrence counts
  the executing rows and then promotes one row to `launching`, and Postgres
  serializes that pair with an advisory lock. SQLite's deferred transaction
  reserved the writer only at the promoting UPDATE, so claimants racing on
  distinct rows — a manual trigger overlapping the poller, or a second Gateway
  process sharing the database file — all read the same stale count, all passed
  the budget check, and the configured cap was exceeded.
- **middleware:** Stop a guard that removes tool calls from breaking every later
  turn of a Claude or OpenAI Responses thread. Token-budget and loop-detection
  hard stops, subagent-limit truncation, and safety suppression cleared
  `tool_calls` but left the provider's own tool-call blocks in the message
  content. Anthropic and the Responses API resend those blocks, so the next
  request carried a tool call with no result and the provider rejected it, and
  a hard stop saved to the checkpoint kept failing on each new message. All
  guards now remove the matching content blocks through one shared helper,
  which also keeps a Responses call that clarification retains.
- **sandbox:** Stop host paths reaching the model when output joins them with
  `:`, as `$PATH` and `$PYTHONPATH` do. The matched path ran on through the
  rest of the list, so every later entry under the same root was left
  unmasked; extra masking passes recovered one entry each, which hid the leak
  for short lists. Masking now ends a matched path at `:`. A symlink inside a
  mount whose target lies outside every mount is now shown by its mount path
  instead of the target's host path in command output and `glob` results.
- **models:** Stop every Claude model after the first from losing its
  credential when the Claude Code OAuth token is handed off through
  `CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR`. Every `ClaudeChatModel` instance
  loaded credentials again, but a descriptor can be drained only once, so the
  title, summarization, and subagent models — and every later run — had no
  credential and failed with `TypeError: Could not resolve authentication
  method`. The token is now read once per process and reused.
- **runtime:** Stop a keyed run retry from failing with 500 on the SQL run
  store. HTTP admissions do not pass a `user_id`; the SQL store stamps the
  request user on the row, but the process-local run record kept `None`. A
  retry with the same `Idempotency-Key` that reached another Gateway worker, or
  the same worker after the finished run was cleaned up, compared the two
  owners, took its own run for another user's, and raised. The same mismatch
  dropped HTTP runs from owner-scoped history reads and skipped the MCP
  `background_tasks` projection for them, so `values` events for these runs now
  include `background_tasks`. `RunManager` now resolves an omitted owner from
  the request user the way the SQL store does, so every store records the same
  owner.
- **skills:** Stop writing resolved secrets into `extensions_config.json` when a
  skill is toggled. The Gateway skill toggle and `OmniHarnessClient.update_skill`
  loaded the file through `ExtensionsConfig.from_file()`, which replaces every
  `$VAR` value with the environment value, and wrote that model back — so a
  `"$GITHUB_TOKEN"` reference was persisted as the plaintext token and an unset
  variable was permanently replaced with `""`. `OmniHarnessClient.update_mcp_config`
  did the same for every key other than `mcpServers`. These writers now edit the
  raw on-disk JSON and validate the candidate the way the runtime loads it, so
  placeholders and hand-written structure survive; the MCP router shares the same
  raw loader. Files rewritten by an earlier toggle keep their plaintext values:
  restore the `$VAR` references and rotate the exposed credentials.
- **gateway:** Honor `disable_clarification` and `github_token` only for
  internally-authenticated callers, the way `non_interactive` already was.
  Both keys were forwarded from `body.context` regardless of the caller and
  were not scrubbed from the free-form `body.config` that the run config
  copies verbatim, so any session or PAT caller could set them.
  `disable_clarification` is the stronger of the two: `ClarificationMiddleware`
  answers every clarification — `risk_confirmation` included — with "proceed
  without asking", and `SandboxMiddleware` reads it as the same
  non-interactive signal as `non_interactive`. `github_token` reached
  `runtime.context`, where the bash tool exports it as `GH_TOKEN`/`GITHUB_TOKEN`,
  and a copy smuggled through `body.config['configurable']` was persisted in
  the checkpoint store. The scheduler, IM channels, and the GitHub webhook
  channel authenticate over the internal request channel and are unaffected.
- **gateway:** Stop persisting a caller-supplied `omniharness_trace_id` on the run
  record. `body.metadata` reaches both the live run config, which the run
  worker restamps, and the run record echoed verbatim by the runs API; only the
  first was covered, so a client could make the most durable surface of a run
  disagree with the `X-Trace-Id` and the log lines from the same request. The
  id is now stamped once at the trust boundary, `config.context` is closed off
  the same way, and a thread's own metadata is no longer seeded with the
  run-scoped id of whichever run created it.
- **gateway:** Keep `X-Trace-Id` on unhandled-exception 500s. Starlette's
  `ServerErrorMiddleware` emits those through the raw send outside every user
  middleware, so the 500 for a server bug — the response most in need of
  correlation — was the only one shipped without the id. `TraceMiddleware` now
  sends its own 500 carrying the header before re-raising; the server's
  exception logging is untouched and mid-stream failures propagate unchanged.
  This fallback is emitted outside `CORSMiddleware` and stays CORS-opaque, so
  split-origin browser clients cannot read the id on this one response — same
  as the `ServerErrorMiddleware` 500 it replaces.
- **artifacts:** Keep explicit full-file loading scoped to the source thread, so a same-path artifact in another conversation keeps its 1 MiB preview. are no longer false positives.
- **mcp:** Isolate Settings > Tools enable/disable updates to one MCP server, so
  an unrelated disallowed stdio command no longer blocks every switch; allow
  disabling a disallowed target while still rejecting its re-enable, preserve
  the raw extensions config, honor the MCP-spec `transport` alias when enabling
  SSE/HTTP servers, surface backend validation details in the UI, and atomically
  replace the shared config for MCP, skill, and embedded-client updates so
  interrupted writes cannot leave it truncated.
- **runtime:** Thread metadata now switches to `running` only after the run passes
  the startup barrier, so pending-cancelled runs no longer briefly project
  `running`; clients may observe the prior thread status during worker startup.
- **runtime:** Re-check orphan candidates through an atomic, lease-aware takeover
  claim so a successful heartbeat after the scan keeps the run active and only
  one reconciler reports recovery.
- **skills:** Apply `allowed-tools` only to slash-activated or actually loaded
  lead-agent skills, preventing passive enabled skills and evaluation fixtures
  from removing MCP, web, file, and delegation tools from every run.
- **models:** Honor `api_base` on every `BaseChatOpenAI` subclass (`VllmChatModel`,
  `MindIEChatModel`, `PatchedChatMiMo`, `PatchedChatStepFun`, `PatchedChatMiniMax`),
  not just `ChatOpenAI` / `PatchedChatOpenAI`. Those five previously dropped the
  configured endpoint silently and then failed every request with an opaque
  `unexpected keyword argument 'api_base'`; the unknown-config-key warning was
  disabled for them as well. Both now gate on `issubclass(BaseChatOpenAI)`.
- **agents:** Coalesce `SystemMessage`s before the LLM request; ensure a visible
  response after tool runs; avoid a default LLM title call before stream end;
  reserve ellipsis room so the local title respects `max_chars`; and snap the
  tool-output tail forward so fallback truncation respects `max_chars`.
- **agents:** Skip dateless reminders in the dynamic-context date scan; load
  `SOUL.md` from agent dirs without `config.yaml`; require `config.yaml` in
  `update_agent`'s legacy-agent guard; and refuse empty `SOUL.md` updates.
- **middleware:** Window the loop-detection tool-frequency counter so long runs
  no longer false-trip; prevent the title middleware from streaming tokens;
  fix positional fallback consuming an unrelated todo when the same-content list
  is exhausted; acquire the token-budget lock across `_apply`, `before_agent`,
  `_clear_run_state`, and `_drain_pending_warnings`; drop orphan `ToolMessage`s
  so strict providers don't 400; sanitize invalid tool-call arguments; and
  recover from empty tool-call names and malformed tool-call ids in dangling
  repair.
- **subagents:** Inherit `LoopDetectionMiddleware` and summarization middleware
  so tool loops break and steps are captured; surface the turn-budget cap as
  `MAX_TURNS_REACHED` with a partial result; unify guardrail caps on the additive
  `stop_reason` + `token_budget`; inject durable context before compaction;
  preserve the parent checkpoint namespace; prohibit the `task` tool in the
  general-purpose system prompt; re-buffer subagent events on flush failure to
  avoid losing steps; and fix the lost `loop_capped` stop reason when a
  subagent's `run_id` is `None`.
- **memory:** Harden against null/empty edge cases - skip whitespace-only facts;
  coerce null `confidence` / `source.confidence` in updates, searches, and the
  three remaining raw reads; treat explicit `null` `backend_config` values as
  omitted; fix `KeyError` / `UnboundLocalError` when a fact has no id or the
  facts list is empty; stop the busy-spin in the debounced update queue; and
  flush the memory queue on graceful shutdown to prevent loss.
- **runs:** Close multi-worker ownership gaps in run atomicity; fail-stop local
  execution when lease renewal cannot be confirmed before its deadline and
  fence late completion writes after peer takeover; degrade cancel to lease
  takeover for multi-worker; keep `create_thread` idempotent when the insert
  loses a race; read `stop_reason` from runtime context; and persist run duration
  in checkpoints for history reads.
- **runtime:** Serialize SQLite event-store writes to prevent per-thread
  sequence collisions; skip hidden human messages in the journal; and drop the
  silent delta-discard in `_merge_stream_text`.
- **gateway:** Attach thread-message feedback by real `event_type`; offload
  blocking filesystem IO in artifact serving, gateway uploads, and the Discord
  channel; limit the uploaded-file context manifest; and live-tail malformed
  Redis reconnect ids.
- **uploads:** Claim the converted-Markdown companion filename before writing
  it, so two convertible uploads sharing a stem (or a convertible plus a
  same-stem `.md` upload) no longer silently clobber each other within one
  request. When `uploads.auto_convert_documents` is on, the companion `.md` now
  gets a unique name (e.g. `a_1.md`); `POST /threads/{id}/uploads` and
  `OmniHarnessClient.upload_files` both report the actual name in `markdown_file`.
- **config:** Coerce null object config sections to their defaults; honor the
  unified database configuration in the store and sync checkpointer; and have
  legacy DB backfill create missing `Index` objects on existing tables.
- **models:** Apply the `stream_chunk_timeout` default to all `BaseChatOpenAI`
  subclasses; and normalize `api_base` -> `base_url` for `ChatOpenAI` with a
  warning on unknown config keys.
- **mcp:** Isolate tool-discovery failures per server; synchronize the
  session-pool singleton lifecycle; invalidate the tools cache on config content
  + path (not just newer mtime); validate MCP tool names at load so deferred
  prompts stay inert; and route tools by source server, not name prefix.
- **skills:** Activate a slash skill once per run, not per model call; close the
  skill-install security-scan coverage gap; recognize fully deleted skill
  packages in review CI and remaining `requests` / `httpx` methods as network
  sinks in SkillScan; reuse the resolved app config in the no-arg skills prompt
  section; and reload mounted skills without restarting the Gateway.
- **sandbox:** Guard the reverse path-translation and output-masking regexes
  with segment boundaries; handle one-sided line ranges and empty files in
  `read_file` / `str_replace`; align the AIO bash working directory; use
  `os.sep` in the reverse-resolve containment check on Windows; normalize
  Windows backslash paths in bash commands; stop `glob` / `grep` / `ls` from
  surfacing disabled skills' files; and allow valid heredoc commands in the
  sandbox audit.
- **sandbox:** Synchronize the sandbox provider singleton lifecycle (with
  concurrency regression tests) and keep k8s calls off the event loop in the
  provisioner.
- **sandbox:** Align sandbox artifact mounts with the channel user; fix
  local-dev (`make dev`) on non-root / NFS hosts; reap macOS nginx processes on
  stop; and fix production Postgres UV-extras detection in Docker.
- **channels:** Validate the channel provider before resolving its config;
  dedupe GitHub webhook redeliveries and drop redundant GitHub review-comment
  webhook fan-out; scope the slash-skill whitelist check to the run's owner;
  batch Feishu file messages into one thread and dispatch Feishu group commands
  prefixed with a bot @mention; accept leading @mentions before `/connect` bind
  codes and don't treat a bare "connect" as a bind command; stop Feishu from
  creating thread topics and throttle card updates; let the UI runtime channel
  config win over `config.yaml`; fix `require_mention` gating on
  whitespace-only `bot_login` / `mention_login`; guard null quote fields in
  WeCom; and key inbound dedupe on chat-scoped workspaces so Telegram, Feishu,
  WeChat and DingTalk redeliveries stop re-running the agent on a default
  (unbound) configuration, releasing the dedupe key on transient failures so a
  redelivery can still recover.
- **frontend:** Preserve messages and durable context across summarization;
  preserve artifacts and stabilize artifact paths during streaming; resolve
  relative artifact image paths; retain presented artifacts in the header
  dropdown; keep orphan tool messages visible; show assistant text during tool
  steps; reset new chat on client-side navigation; prevent stream cancellation
  on concurrent submit; fix stale-run reconnect and cancel handling; fix chat
  math rendering, single-tilde markdown, double reasoning rendering, UTF-16
  markdown binary classification, and `<memory>` tags in Streamdown; make
  recent-chat rows fully clickable; validate attachment limits before upload and
  fix uploaded-file metadata in message copy; fix mobile workspace and
  accessibility blockers, the card tool-message bug, and side-chat toolbar /
  panel-button behavior; block unresolved suggestion-template placeholders;
  refresh notification permissions; show the branch action only for completed
  turns; enable regenerate in custom agent chats; and generate a fallback title
  for interrupted first-turn runs.
- **tui:** Interrupt an active run before `/quit` exits.
- **tracing:** Attach Langfuse trace metadata to the goal evaluator.
- **threaddata:** Fix `AttributeError` when `runtime.context` is `None`.
- **circuit-breaker:** Stop wedging after a non-retriable half-open probe.
- **community:** `image_search` now returns the full-resolution image URL.
- **skills:** Don't treat a lazily evaluated PEP 695 type alias as a network
  sink in SkillScan.
- **tracing:** Resolve the Langfuse trace user from runtime context.
- **subagents:** Clamp the subagent limit consistently with
  `MIN_SUBAGENT_LIMIT`.
- **mcp:** Per-server fail-soft OAuth priming, and persist rotated refresh
  tokens.
- **auth:** Resolve email accounts case-insensitively.
- **scheduler:** Close a dispatch race that could launch two runs for one
  scheduled task.
- **channels:** Escape Slack reserved characters before mrkdwn conversion.
- **channels:** Drop inbound DingTalk messages that carry no conversation
  identity.
- **memory:** Consolidated facts inherit `expected_valid_days` from their
  sources.
- **postgres:** Harden the async engine with `pool_recycle` and
  `command_timeout` to stop stale-connection 504s.
- **community:** Surface the target-page error status in `web_fetch`
  (Browserless).
- **sandbox:** Make an empty `old_str` a no-op in `str_replace` on any file.
- **sandbox:** Bound E2B output-synchronization resources.
- **sandbox:** Bypass proxies for local AIO traffic.
- **streaming:** Keep large file generation responsive.
- **streaming:** Signal replay history gaps.
- **runtime:** Remove transient image context after model calls.
- **runtime:** Reject unsupported run options and stream modes.
- **runtime:** Serialize checkpoint writes with active runs, linearize
  delta-mode checkpoint resume, and accept the SDK's default
  `stream_resumable=false` to avoid resume races.
- **checkpoint:** Unwrap `Overwrite` first writes into empty channels.
- **gateway:** Prefer `X-Trace-Id` over `metadata.omniharness_trace_id` when the
  header is set.
- **gateway:** Scope branch-history seed run ids per inherited turn.
- **frontend:** Classify a symlink replacing a file distinctly from deleted in
  workspace-change review.
- **frontend:** Encode artifact URL path segments.
- **frontend:** Preserve regenerate state in branched threads.
- **frontend:** Strip and parse the `<current_uploads>` upload-context tag.
- **frontend:** Keep completed subtask cards stable after reload.
- **frontend:** Restore resizing for the artifacts and sidecar panels.
- **safety:** Backfill empty content-filter responses so they don't poison the
  thread.
- **mcp:** Bound MCP server bring-up — tool discovery (subprocess spawn +
  `initialize` + `tools/list`) and persistent stdio session initialization —
  with a new per-server `session_init_timeout` (default 60s, `null` disables),
  so a hung stdio server can no longer block agent construction, or the whole
  Gateway event loop, indefinitely. `tool_call_timeout` still bounds individual
  stdio tool calls.
- **frontend:** Hide stale follow-up suggestion chips while a turn is still
  streaming.
- **frontend:** Fix streaming render glitches: stop the word animation from
  replaying, keep step text stable, preserve message order during long runs,
  and keep reasoning above the answer.
- **frontend:** Encode thread IDs in chat routes so IDs with special
  characters no longer break navigation.
- **frontend:** Localize conversation export failure messages.
- **frontend:** Render one workspace-change card per run instead of
  duplicates.
- **gateway:** Reject non-positive read limits in API requests.
- **gateway:** Unify thread id validation across API routes.
- **gateway:** Expose the run metadata response header to cross-origin
  clients, so a split-origin frontend learns new run ids instead of staying
  stuck on the new-thread placeholder route until reload., and keep a manual rename through the
  rerun.
- **runtime:** Cancel a run from any live gateway worker, not only the one
  that owns it, so the stop button no longer depends on request routing.
- **runtime:** Regenerating a response now preserves the thread's current
  title and supports the latest interrupted response whose partial message
  never reached a checkpoint.
- **agents:** Classify web_fetch error pages such as 404s as errors rather
  than successful evidence, so retries and stagnation guards can react.
- **subagents:** Run delegated subagents with isolated callbacks and lazy
  skill activation, fixing cross-event-loop failures and passive skills
  stripping baseline tools like `write_file`.
- **sandbox:** Reconcile E2B sandboxes safely: pick the first healthy
  candidate, adopt the canonical instance per user and thread, defer a
  peer's live duplicates, and reap orphans after a grace window.
- **sandbox:** Allow grep to search a single file.
- **skills:** Activate managed integration skills from the managed
  integrations root on slash invocation.
- **mcp:** Ignore oversized path-like text.
- **memory:** Harden long-term memory: reject duplicate facts inside the
  create critical section, truncate injected mem0 context on entry
  boundaries, and keep task-scoped instructions such as "inspect only" out
  of long-term memory.
- **scheduler:** Keep a successfully launched scheduled run's slot and run
  id when post-launch bookkeeping fails, preventing a later dispatch from
  launching a duplicate run.
- **config:** Normalize the `postgres://` short scheme for the async ORM
  engine.
- **browserless:** Accept the `timeout` config key and harden its coercion.
- **runtime:** Group JSONL batch event writes by run, so a batch covering
  several runs no longer lands all events in the first run's file and makes
  later runs unreadable through per-run APIs.
- **runtime:** Restore standalone LangGraph Studio compatibility: the graph
  entrypoint and file-based app load again, the Studio identity can discover
  system assistants, and the documented `langgraph dev` workflow works.
- **gateway:** Stamp `turn_duration` on a run's last AI message only in
  `/messages/page`, so multi-step turns no longer repeat the same run
  lifetime as thinking latency on every intermediate message.
- **gateway:** Reject MCP task cancellation with HTTP 503 when the task
  worker is stopped, instead of acknowledging a cancellation that would
  never run.
- **middleware:** Correct four context-handling defects: fallback
  dynamic-context injection targets the latest user message instead of
  resurrecting an old prompt as the current turn; bare string blocks in
  list-form user content are sanitized like all other user text; duplicate
  placeholders are no longer emitted for the same invalid tool call; and
  summarization no longer compresses away the current request's user message
  while leaving the previous turn's behind.
- **middleware:** Restore the system-prompt injection that teaches the model
  about the `write_todos` tool, which the todo middleware's model-call
  override had silently dropped.
- **tools:** Resolve presented files with the runtime user, so `present_files`
  no longer rejects valid artifacts as outside the outputs directory when
  the request user context is unavailable.
- **subagents:** Give every background subagent run a server-side execution
  ID, so concurrent runs that reuse a provider tool-call ID can no longer
  overwrite, poll, or cancel each other's state.
- **mcp:** Reject non-finite `poll_after_seconds` values on task snapshots
  when they arrive, so a bad polling interval no longer crashes scheduling
  and persistence after a successful poll.
- **runtime:** A slow or hung stdio MCP server no longer stalls the whole
  Gateway. Agent construction assembled MCP tools synchronously on the event
  loop, so a wait for an in-flight MCP initialization blocked SSE delivery, run
  cancellation, and timers for every other request, not just the caller waiting
  for its tools. Tool assembly is now dispatched to a worker thread at each
  async entry point: the subagent spawn path in `task_tool`,
  `SubagentBatchService._execute_item` for durable batches, `run_agent`'s agent
  factory (which covers both `get_available_tools` call sites in lead-agent
  assembly), and the checkpoint state-accessor build, whose cold-cache reads
  pay the MCP-init wait in the worker thread instead of stopping the loop. The
  four offloads ride a dedicated bounded pool (`run_assembly()` in
  `utils/assembly_io.py`, 8 workers, overridable with
  `OMNI_HARNESS_ASSEMBLY_WORKERS`) rather than the loop's default executor, so a
  worker parked for the full MCP timeout cannot queue every other `to_thread`
  caller behind it; contextvars are copied across the hop so the extension
  build-context snapshot still propagates, and pending assemblies are logged
  with a throttled warning once they exceed the worker count. Because assembly
  can now be parked, a durable batch re-checks its item's durable state
  immediately before launching, so a batch cancelled during assembly no longer
  starts a model call.
- **agents:** `LoopDetectionMiddleware` no longer spends one turn's budget on
  another turn's legal work. It scoped its identical-call hashes and per-tool
  frequency windows only by `thread_id`, so a compiled agent reused across
  turns — `OmniHarnessClient` retains the graph and assigns a fresh `run_id` per
  turn — counted earlier turns' ordinary calls toward the later turn's limit,
  producing a false loop warning on the third separate turn and stripping a
  legitimate tool call on the fifth at the default identical-call thresholds.
  State is now scoped by `(thread_id, run_id)`, with evidence still accumulated
  across repeated graph entries inside one run, including hidden goal
  continuations, and independent warning queues for concurrent sibling runs.
  LRU eviction drops a whole run scope, `reset(thread_id)` still clears every
  scope that thread owns, and thresholds and warning/hard-stop behavior are
  unchanged.
- **middleware:** A Human Input Card reply is now recognized as the user's
  current request. The card answer arrives as a hidden `HumanMessage` carrying
  a valid `human_input_response`, and the turn-detection helpers used
  `is_real_user_message`, which rejects every hidden message with no carve-out
  — so a run started from a card reply kept the older visible request as
  "current" while the answer itself was treated as a framework injection. In
  summarization, the current-request rescue therefore locked onto the stale
  message: after compaction the model saw the original request word for word
  and the user's region and year constraints only inside the summary. In
  `McpRoutingMiddleware`, a routing keyword that appeared only in the card
  answer matched nothing, so the deferred MCP tool was never auto-promoted and
  the model had to call `tool_search` by hand — the identical answer sent as a
  visible message promoted it, so behavior depended only on how the answer was
  transported. Both now use `is_genuine_user_message`, which skips hidden
  messages unless they carry a valid `human_input_response`; hidden messages
  without one still stay skipped.
- **goal:** A goal that a token-capped run already satisfied is no longer
  followed by a pointless continuation. Now that continuations share the run's
  token budget, a continuation queued after the hard stop made one model call
  and then had its tool calls stripped, so it could not make progress — yet the
  worker still queued it, paying for an evaluator call and a model call each
  time until the continuation or no-progress limit stopped the goal.
  `run_agent` now passes the run's `stop_reason` into goal-continuation
  preparation, and when it is `token_capped` the goal stands down with
  `stand_down_reason: "token_capped"` instead of queueing another continuation.
  The evaluator still runs first, so a goal the capped run did satisfy is still
  cleared, and other stop reasons behave as before.
- **agents:** The token budget works again for runs that have no `run_id` —
  LangGraph Server, `langgraph dev`, and direct `create_omniharness_agent`
  callers. Two defects rode the runtime-local fallback key. A subagent's hard
  stop was stored under the id string but read back with
  `consume_stop_reason(None)`, because `SubagentExecutor` propagates the
  parent's `run_id` and the parent has none, so a token-capped subagent was
  reported to the parent as a clean `Task Succeeded` instead of a capped
  failure. And LangGraph gives each node its own `Runtime` wrapper, so
  `id(runtime)` differed between `after_model`, the next `wrap_model_call`, and
  `before_agent`: the queued budget warning was never delivered, `after_model`
  missed the `before_agent` baseline and counted every `AIMessage` in the
  thread, and a second invocation on the same thread was charged with the first
  invocation's tokens. Invocations without a non-empty string context `run_id`
  are now keyed by LangGraph's run-scoped `Runtime.control` object, the same
  anchor loop detection uses, and the stop reason is stored under the context
  `run_id` exactly as given, `None` included.
- **agents:** Three `create_omniharness_agent` features now do what they
  advertise. Factory graphs were built without `DurableContextMiddleware`,
  which is what writes the `delegations` ledger — so `SubagentLimitMiddleware`
  always counted zero earlier delegations and only the per-response limit
  applied — and which is the only thing that puts `summary_text` back into a
  model request, so after the first compaction the model saw only the kept tail
  and the summary was lost. Separately, `RuntimeFeatures(token_budget=True)`
  built a `TokenBudgetConfig()` whose `enabled` defaults to `false`, so every
  hook returned early and there was no warning, no hard stop, and no
  `token_capped`. `_assemble_from_features` now always adds
  `DurableContextMiddleware` in the same position as the lead-agent chain,
  factory model requests carry the hidden durable-context block when the graph
  has a summary, delegations, or loaded skill files, and `token_budget=True`
  builds `TokenBudgetConfig(enabled=True)`.
- **sandbox:** Concurrent subagents stopped working once their count passed the
  AIO image's shell-session ceiling. Each concurrent subagent gets its own
  persistent scoped shell, but the AIO image caps `MAX_SHELL_SESSIONS` at 10,
  so the eleventh shell evicted the oldest idle session while OmniHarness still
  held its scoped id — the subagent's next command then failed with `404
  Session not found`, and recreating sessions without raising the capacity only
  evicted another subagent and lost its shell state. New local containers now
  receive `subagent_runtime.max_running + 1` (the extra slot leaves room for
  the lead shell) as `MAX_SHELL_SESSIONS`, provisioner mode forwards the same
  value to the sandbox Pod, and an explicit
  `sandbox.environment.MAX_SHELL_SESSIONS` set below the required capacity now
  fails at provider startup naming both values. When a scoped session is lost
  anyway — to a timeout or external cleanup — OmniHarness recreates it once, and
  only for the structured `404 Session not found` response.
- **subagents:** A subagent keeps its instructions after its context is
  compacted. The executor builds the agent with `system_prompt=None` and puts
  the assembled prompt into state as the first message, so it holds the role
  prompt, the `<report_contract>` citation rules, the acceptance-criteria note,
  the skills index, and the deferred MCP tools and routing hints — and
  compaction cuts by index, so index 0 always fell in the summarized part.
  Every model call after the first compaction ran with no system prompt at all,
  and the summary did not stand in for it because it is injected as hidden data
  the authority contract tells the model not to follow. Dynamic-context
  preservation now rescues `SystemMessage`s as well as tagged reminders and the
  latest user message, keeping their order so the prompt stays first and is not
  sent to the summarizer; when the prompt plus the current request are all that
  remains, compaction is skipped instead of summarizing the prompt away. The
  lead agent is unaffected — its prompt is the request's system message, not a
  message in state.
- **worker:** A delegated subagent's error no longer fails the parent run. When
  a subagent's model call ended in an error after its retries, the executor
  reported `task_failed` and the lead agent still answered, but the worker also
  saw the `omniharness_error_fallback` marker inside the root-level `task_running`
  custom event — each carries a subagent message with `additional_kwargs` — and
  marked the parent run `error` with the subagent's error text. Goal
  continuation stopped, and an edit-and-rerun rolled the thread back,
  discarding the edited question and the new answer. Custom frames no longer
  feed parent error-fallback detection, while the lead's own error fallback
  still arrives through `values`, `messages`, and `updates` frames; the parent
  run now ends `success` when the lead finishes.
- **sandbox:** Reverse-resolve forward-slash spellings of Windows host paths.
  Forward resolution spells resolved paths with `/`, since backslashes would
  break bash escape sequences like `\U`, but the reverse scanner that maps host
  paths in output back to their `/mnt/...` form still anchored its matches on
  the native backslash base — so every forward-resolved path that came back in
  command output or in an agent-written file failed to match and leaked the raw
  host path, real username and full directory tree, to the model instead of the
  container path the agent is meant to reference. The scanner now matches
  separator-agnostically, the same contract the sandbox tools already use;
  POSIX hosts, where the two spellings coincide, are unaffected.
- **sandbox:** Stop remote `list_dir` from reporting failures as an empty
  directory. `find ... 2>/dev/null` on a missing path produced empty stdout and
  client errors were swallowed as `[]`, so `ls` told the agent the directory
  was `(empty)` — a dead sandbox, a closed client, and a nonexistent path all
  looked like a writable empty tree, letting the agent write over existing
  files or skip recovery. AIO, E2B, BoxLite, OpenSandbox, and Tenki now raise
  `OSError` on command or client failure and `FileNotFoundError` when nothing
  is listed, matching what the local sandbox already did for a path that is not
  a directory; a genuinely empty directory still reports `(empty)`, and `find
  -H` keeps a symlinked root listable.
- **sandbox:** Stop remote `grep` and `glob` from reporting failures as "no
  matches". The searches ran with stderr discarded and took the pipeline status
  from `head`, so a missing search root, a missing `grep`/`find` binary, or an
  unreadable tree printed nothing and exited 0 — and the tools told the agent
  "No matches found" where the local sandbox reports `Error: Directory not
  found`. A shared wrapper now records the search command's own status: a
  missing root raises `FileNotFoundError`, and any other failure — including
  `grep` 2 or `find` 1 after some results were already printed, since a caller
  cannot tell a partial result from a complete one — raises `OSError` telling
  the agent that some paths could not be read. A genuine no-match still returns
  `[]`. E2B, OpenSandbox, BoxLite, and Tenki also raise on a closed client
  instead of returning empty.. Continue with start_line=744]`; a
  ranged read reports file line numbers rather than the provider's
  slice-relative ones. A single line longer than the budget still cuts at the
  character limit, since dropping it would discard most of the budget, and the
  marker then points at `bash` rather than at a `read_file` call that cannot
  return it.
- **sandbox:** Force a UTF-8 console in PowerShell so CJK tool output is no
  longer garbled on Windows. The command runner captures stdout through a UTF-8
  pipe reader, but Windows PowerShell 5.1 writes console output in the legacy
  OEM codepage — GBK on zh-CN Windows — unless explicitly switched, so every
  CJK character arrived as mojibake, and because the reader replaces
  undecodable bytes rather than raising, the corruption was silent. Every
  PowerShell `-Command` payload now sets `InputEncoding`, `OutputEncoding`, and
  `$OutputEncoding` to UTF-8 before the user command runs.
- **sandbox:** Default the Docker-outside-of-Docker sandbox port bind to
  loopback on Docker Desktop. `OMNI_HARNESS_SANDBOX_HOST` defaults to
  `host.docker.internal` in DooD mode, which resolves inside containers to the
  Docker Desktop VM gateway, and publishing the sandbox port to that address
  made the host socket layer reject the bind with `WSAEADDRNOTAVAIL` — so the
  first sandbox shell action failed with `ports are not available` even though
  startup had succeeded. When the Docker server is Docker Desktop and no
  `OMNI_HARNESS_SANDBOX_BIND_HOST` override is configured, the bind host is now
  `127.0.0.1`, which Docker Desktop forwards; an explicit override still wins,
  and native Linux DooD is unaffected.
- **frontend:** Keep a human-input card with the turn that requested it. An
  existing `needYourHelp` card could drift below the next user message during a
  multi-turn conversation, so the chronology became misleading and an answered
  request could read as part of the new turn. A pre-submit baseline message
  could be woven in after the newly persisted human message, a card confirmed
  only through REST history might never enter the checkpoint baseline, and
  steps already persisted for the current run could be lifted into the previous
  turn after an interrupt. Baseline messages are restored before the pending
  human message, REST-confirmed cards count as established history, and the
  current run's own steps stay below the message that started them.
- **frontend:** Restore the user's input after an incremental stream reconnect.
  Refreshing during a later turn could let the reconnect stream replay AI and
  tool chunks before the current human input had entered the durable history
  feed, so the user's message briefly vanished and its reasoning steps were
  grouped under the previous turn. The active run's input is now hydrated from
  `kwargs.input` and merged with the latest durable thread state before the
  incremental stream is joined, deduplicated by id; if the metadata or state
  read is unavailable, the previous reconnect path is used unchanged.
- **frontend:** Show an agent's skill badge even when its tool groups are
  explicitly empty. The badge container's nullish-coalescing chain stopped at
  the tool-group count `0`, so an agent declared as `tool_groups: []` with
  `skills: ["data-analysis"]` lost its badge in the Agents gallery — even
  though an explicit empty tool-group list is valid and supported by the Agent
  API and the `update_agent` tool. The container now shows when either list has
  at least one entry.
- **frontend:** Confirm before a sidebar chat is deleted. Choosing Delete in a
  recent chat's menu removed the conversation and its files immediately, with
  no confirmation step despite deletion being irreversible. A dialog now names
  the conversation and warns that deletion is irreversible, focuses Cancel, and
  leaves the chat intact on Cancel, Escape, or close; actions are disabled and
  dismissal blocked while deletion is pending, and a failed deletion keeps the
  dialog open with the underlying error so it can be retried by keyboard. The
  dialog is hosted outside the virtualized sidebar rows, so a list refresh
  cannot remove the retry UI after a partial deletion.
- **frontend:** Keep the MCP configuration dialog within the viewport. Opening
  a long MCP server definition in the Capability Center let the JSON textarea
  grow past the window, so the centered dialog clipped its title, close
  control, and Save/Cancel buttons and became hard to edit or dismiss on
  smaller windows. The dialog is now viewport-contained with more horizontal
  room on desktop, long JSON scrolls inside the editor, and the title, Close,
  Save, and Cancel stay outside the scrolling region even at very small
  viewports or with a long server name or validation message.
- **frontend:** Localize Chinese documentation links. MDX links and Nextra
  cards in the localized docs were rewritten without knowing the active docs
  language, so a Chinese reader following a quick-start link was sent to the
  English page. The localized docs layout now provides the language through
  context and link rewriting honors it.
- **events:** Read JSONL event records that contain U+0085, U+2028, or U+2029.
  All three readers split on those Unicode separators as if they were record
  boundaries, so a record carrying one was skipped on read — which reused event
  sequence numbers after a reopen and turned idempotent inserts into
  duplicates. Thread reads, run reads, and sequence recovery now split on
  physical line feeds; existing valid files need no rewrite.
- **events:** Stop JSONL thread mutations from splitting onto two lock
  generations across a deletion. `delete_by_thread()` removed the per-thread
  lock from its registry while still holding it, so a mutation already queued
  on the old lock could run concurrently with a later mutation that resolved a
  freshly created lock for the same thread — overlapping sequence assignment
  and file mutation right after a delete boundary. The registry is now a
  `WeakValueDictionary` and the entry is no longer popped, so holders and
  queued waiters keep the same generation alive until they drain, after which
  the entry disappears on its own.
- **gateway:** Read a thread's runs as the data owner, not as the authorization
  identity. The list, keyset-page, and single-run read endpoints filtered run
  rows by the caller's authorization identity, while `start_run` stamps them
  with the data identity — the two only coincide for already-safe owner values,
  so trusted internal callers always saw an empty runs list and 404s even on
  threads they were authorized to act on, and the symptom was easily misread as
  run loss. Internal callers now skip the per-user store filter, which thread
  visibility on these endpoints already authorizes, while browser and API
  sessions keep their exact per-user filter; the two message-read endpoints had
  the same conflation and are corrected the same way.
- **conversation:** Keep conversation-reader pages inline and say when text was
  dropped. A page was filled to its 20,000-character cap by cutting the last
  message that did not fit, and a cut suffix could never be paged back — the
  oldest of six 3,500-character messages came back as about 2,500 characters
  with `has_more: false`. Worse, a page over the default 12,000-character
  tool-output budget was externalized by `ToolOutputBudgetMiddleware`, so the
  model saw only a synopsis plus a file copy of the source text in the
  destination thread. Pages are now sized by the budget that actually applies
  to `read_conversation` (per-tool override, else `externalize_min_chars`, and
  `fallback_max_chars`), still capped at 20,000 text characters, and a message
  that does not fit starts the next page intact — so one operator setting stays
  in charge, and `tool_output.tool_overrides.read_conversation` tunes this tool
  alone. Truncated results now carry a notice asking the agent to acknowledge
  the omission and ask for the missing material before claiming full coverage.
- **client:** Emit text a later node appends to an AI message already sent.
  `LoopDetectionMiddleware`, `TokenBudgetMiddleware`,
  `SafetyFinishReasonMiddleware`, `SubagentLimitMiddleware`, and
  `TerminalResponseMiddleware` each rewrite the last AI message under the same
  id from their own node, but the stream marks an id seen once and then skips
  it, so the rewrite never reached `messages-tuple` consumers: `chat()` and
  headless `--print` returned the text from before the rewrite instead of the
  terminal error or the forced-stop notice, the TUI never showed the stop or
  safety notice, and `token_usage_attribution` added after the model node never
  arrived. The values path now remembers the message object last seen per id
  and re-examines it when a snapshot holds a different one, emitting only the
  added text as one more delta and routing new `additional_kwargs` through the
  existing metadata-only follow-up; unchanged messages are still skipped
  without re-extracting text. A replacement that does not extend the sent text
  is not re-emitted.
- **mcp:** Stop parallel synchronous MCP calls from cancelling each other's
  connection. When an embedded client dispatched two synchronous calls to the
  same stdio server, each wrapper ran on its own event loop and the pool
  treated the sibling loop's live session and in-flight creation as stale —
  cancelling or closing them and aborting a tool step with `CancelledError`
  instead of returning both results. Established sessions and in-flight
  creation are now keyed by `(server_name, scope_key, owning_loop)`, so
  same-loop callers still share creation and state while separate loops get
  their own, and each owner retires only its own records, including after a
  normal `asyncio.run()` shutdown. Synchronous calls still use independent
  subprocess sessions and gain no shared server-side state.
- **web-fetch:** Resolve relative destinations in extracted Markdown against
  the page they came from. Jina, Browserless, and InfoQuest returned links
  exactly as written in the HTML, so a page at
  `https://example.com/docs/current` yielded `[Next](../next)` and left the
  agent with no URL it could follow up on. The three providers now pass the
  requested URL to the shared extractor, which resolves anchor and image
  destinations against that URL or against the first usable document `<base>`;
  only destination attribute values are rewritten rather than serializing a
  different parse tree, so malformed markup, comments, scripts, and attribute
  formatting survive untouched and still reach Readability.js unchanged. Fetch
  validation, the 4096-character output limit, and off-thread extraction are
  unchanged, and the Python fallback keeps its text-only behavior.
- **community:** Tavily extraction reads its credentials from the `web_fetch`
  entry instead of the search configuration. With `web_search` on Serper and
  `web_fetch` on Tavily, fetching built its client from the Serper key and
  ignored a separate Tavily fetch key entirely. Each tool now reads `api_key`
  from its own entry and falls back to the SDK's `TAVILY_API_KEY` when omitted,
  matching the existing Exa helper. Configurations that put a shared Tavily key
  only under `web_search` must also set it under `web_fetch`, or rely on
  `TAVILY_API_KEY` for both.
- **browser:** Keep browser session teardown alive across caller cancellation.
  `BrowserSessionManager.close_session()` removed a session from the registry
  before awaiting its close, and that close awaited the private Playwright loop
  directly, so a cancellation at that point propagated through
  `asyncio.wrap_future()` into the cleanup itself — leaving the browser process
  and context orphaned, with the session already out of the registry and no
  owner left to retry. `close_all_sessions()` had the same ownership problem at
  a larger scale: it cleared the whole registry first, so a cancellation while
  closing the first session stranded every later session with no teardown
  scheduled at all. Teardown is now submitted to the private loop before any
  cancellable await and awaited behind `asyncio.shield()`, and close-all
  schedules every session before its first await and shields the group wait.
  The caller still receives `CancelledError`; only ownership of the
  already-started cleanup is isolated from it.
- **setup:** The same pre-sync extras detector now reads `config.yaml` as
  `utf-8-sig`. PyYAML accepts a leading UTF-8 BOM but the detector read the
  file as plain `utf-8`, leaving the BOM attached to the first line, so its
  anchored section patterns failed to recognize a valid config's opening
  section and omitted the extras it declared — `postgres`, `browser`, and
  `ollama` detection all failed the same way when their section came first,
  while a plain-UTF-8 copy of the same file worked.
- **channels:** Both WeCom outbound paths sent unbounded text while the bot
  protocol caps content at 20480 UTF-8 bytes, a bar a deep-research report
  clears easily. Over the cap, `_send_with_retry` retried three times and gave
  up: the stream path left the reply stuck mid-way without ever sending
  `finish=true`, and the push path dropped the reply entirely. Stream replies
  now clip on a UTF-8 character boundary behind a visible truncation marker —
  one stream carries the whole reply, so it cannot split mid-way — while
  proactive pushes with no replyable frame, such as scheduled-task
  notifications, split into sequential markdown messages at newline boundaries
  so the full content still arrives. Both paths now measure the payload in
  UTF-8 bytes rather than characters.
- **channels:** Keep one undecodable WeChat message from dropping the rest of
  its batch. `_poll_loop` persisted the `get_updates_buf` cursor for the entire
  batch immediately on receipt, then iterated `data["msgs"]` with no per-message
  error isolation, so a single message whose processing raised — a corrupt or
  undecryptable attachment, such as a truncated encrypted image payload, is the
  realistic trigger — aborted the loop with the cursor already advanced past the
  whole batch. Every message after the failing one was permanently dropped and
  the next poll never re-fetched it. `_handle_update` now runs inside a
  per-message `try`/`except`, so siblings still reach the bus, the failure is
  logged with its message id, and the cursor still advances once the batch has
  been fully attempted.
- **channels:** Discord thread mappings are persisted off the event loop after
  a thread is created, so a process killed between the creation and its
  background write could still lose the newest mapping and leave a Discord
  thread unreachable after the restart. `stop()` now flushes the in-memory
  mappings to disk, wrapped so a shutdown path is never blocked — a best-effort
  net over the hard-kill window rather than a new write path.
- **channels:** Enabling `rich_messages` in the Telegram channel config made
  every final outbound message render as a mangled single line: command menus
  such as `/help` and plain error replies were sent through `sendRichMessage`
  with `rich_message.markdown`, which collapses single newlines and strips the
  `<name>` / `<skill-name>` / `<task>` angle-bracket tokens the menus rely on.
  A message is now sent as rich only when `rich_messages` is enabled *and* the
  text actually contains a rich construct — a fenced code block, a table row or
  separator, a task list, a `[text](url)` link, bold, italic, a `<details>`
  block, or `$$` math. The detector is deliberately conservative, requiring a
  table to lead its line with `|`, so a line like `/goal [condition|clear]` in
  `/help` never trips it.
- **models:** The request-admission limiter decided immediate admission and
  queue insertion under two separate lock acquisitions, so a blocking caller
  could observe that the next permit was not yet due, be descheduled before it
  enqueued, and then be overtaken by a newer caller once the permit came due
  while the waiter queue was still empty — the newcomer took the permit and the
  older caller waited a further interval, or under a short `max_wait_seconds`
  timed out while the later request succeeded. Immediate admission and FIFO
  insertion are now a single lock-protected decision. Non-blocking calls still
  fail fast and never enter the queue, and queued pacing, cancellation,
  timeout, queue-capacity and no-burst behavior are unchanged.
- **uploads:** A single 200,000-character paragraph produced a
  199,999-character upload preview despite the five-line limit, and long valid
  headings bypassed the 50-entry limit as a practical context-size bound.
  Outline titles are now capped at 200 characters and fallback preview text at
  2,000 characters across all lines, with the omission markers counted inside
  those budgets. Physical line numbers, short text, the existing heading and
  preview counts, and the original file bytes are preserved; this bounds
  returned summary text only, not file-scan memory or a budget across uploads.
- **doctor:** On a fresh clone, `make config` followed by `make doctor`
  reported four errors where only one was real: `config.example.yaml` ships a
  `models:` key with every entry commented out, which parses as `None`, so the
  `[]` default in `.get("models", [])` never applied and a broad `except`
  rendered the resulting `TypeError` as three `'NoneType' object is not
  iterable` check results. A new user saw what looked like a broken install at
  the exact moment `make doctor` is meant to reduce confusion, when they had
  simply not configured a model yet. The LLM checks now skip when no models are
  configured, leaving the actionable `models configured` failure and its `make
  setup` hint; nothing changes once a model is configured.
- **docker:** On Windows Git Bash, `make docker-start` and `make up` aborted
  unconditionally with `Docker socket not found at /var/run/docker.sock —
  AioSandboxProvider (DooD) will not work.` MSYS2/Git Bash has no physical Unix
  socket at that path — Docker Desktop uses named pipes — even though the
  daemon natively handles mounting `/var/run/docker.sock` into Linux
  containers, so the check could never pass. Under `MINGW*`, `MSYS*` and
  `CYGWIN*` the preflight now verifies `docker info` connectivity instead of
  requiring a socket file; POSIX hosts still fail fast on a missing socket.
- **mcp:** Exclude the internal stdio MCP temp directory (`.mcp/tmp`) from
  workspace changes, so MCP temporary and debug files no longer appear
  alongside user deliverables or crowd real changes out of the file budget.
- **sandbox:** Accept the documented E2B reconciliation config fields, so
  valid E2B configuration no longer produces misleading startup warnings., so large mounts can no longer spike Gateway memory
  or hold sandbox capacity indefinitely.
- **sandbox:** Preserve trailing whitespace in E2B-synced filenames and
  tolerate out-of-range remote mtimes, so output sync no longer re-downloads
  files repeatedly or aborts mid-sync.
- **sandbox:** Resolve structured skill reads through the sandbox provider's
  path mappings, so `read_file` opens legacy and per-user custom skills
  under the same enabled-state projection as `ls` and shell execution.
- **memory:** Reject non-positive and non-finite timeout and character-limit
  settings in the Honcho and Mem0 backends at config parse time, so a bad
  value fails fast instead of silently truncating stored text or crashing on
  the first HTTP call.
- **memory:** Scope custom-agent bootstrap facts to the selected agent's
  bucket, so facts learned during setup no longer leak into the default
  bucket and influence ordinary lead-agent conversations.
- **artifacts:** Support atomic saves on Windows, and serve a SHA-256 ETag on
  artifact reads so inline preview and editing work on non-secure contexts
  such as plain-HTTP LAN origins where `crypto.subtle` is unavailable.
- **frontend:** Keep conversation order stable around long runs: the
  submitted user message no longer renders twice or sinks below its own
  processing steps, and after a mid-run page reload a turn's steps can no
  longer appear above the user message that started the run.
- **frontend:** Stop matching `<header>` as `<head>` when injecting the base
  href into HTML artifact previews, so relative assets in report fragments
  that begin with `<header>` now load in the sandboxed preview iframe.
- **frontend:** Sort the chats page by pinned state, so pinned threads no
  longer render below unpinned ones.
- **frontend:** Surface model-loading failures with a workspace error banner
  and retry action instead of a silently empty model list.
- **frontend:** Preserve copy and other actions on completed assistant
  messages while a later turn is still streaming.
- **frontend:** Reuse the shared clipboard fallback when copying the Lark
  authorization link, so the copy action works in browsers without the
  Clipboard API.
- **channels:** Bound inbound intake with a fixed worker pool and bounded
  admission queues, and await real cross-thread tasks on shutdown, so
  message floods are rejected promptly instead of accumulating and channel
  shutdown no longer tears down transports with work still in flight.
- **channels:** Offload outbound attachment file IO for Feishu, Telegram, and
  WeCom to worker threads, so sending a large artifact no longer stalls the
  Gateway event loop.
- **feishu:** Keep file receiving off the event loop and preserve every
  inbound attachment: duplicate provider filenames no longer overwrite each
  other, writes can no longer be redirected outside the thread bucket, and a
  failed attachment no longer blocks the rest of the message.
- **dingtalk:** Strip leading `@bot` mentions before command classification,
  so slash commands like `/new` sent in group chats are recognized instead
  of treated as plain chat.
- **wecom:** Serialize WebSocket start/stop transitions and await the SDK's
  real receive-task shutdown, so stopping the WeCom channel can no longer
  return before the socket closes or clear a newer connection's state.
- **lark:** Keep the CLI lock directory writable inside sandboxes while the
  credential-bearing config root stays read-only, restoring Lark API
  commands that previously failed with a read-only filesystem error.
- **scheduler:** Coerce serialized task timestamps on read, so
  scheduled-task operations no longer fail when string-form timestamp values
  reach the database layer.
- **scheduler:** Enqueue busy scheduled task runs instead of skipping them:
  occurrences that hit a busy reused thread now wait in a durable queue
  (bounded by `scheduler.queue_timeout_seconds`) and survive Gateway
  restarts, and the UI explains the queueing behavior.
- **dev:** Exclude backend runtime state from the Uvicorn reload watcher in
  the backend `make dev` launcher, so an agent task writing files under the
  runtime tree can no longer restart the Gateway and reset concurrent
  users' requests.
- **docker:** Harden local and container startup: `make up` waits for the
  Gateway health probe before declaring the stack ready, Docker startup no
  longer aborts when `.env` is missing, the Gateway can write
  `extensions_config.json` in production, runtime data stays out of the
  image build context, log commands resolve the checkout root correctly,
  and the default loopback origins are allowed so the dev setup page can
  hydrate.
- **gateway:** Stamp the server-authoritative feed position onto persisted
  messages, so an early user message no longer vanishes or jumps into the
  middle of the step stream once history exceeds one page and context
  compaction has fired.
- **messages:** Drop legacy `<uploaded_files>` tag handling: the backend treats
  the pre-#4174 spelling as ordinary content and strips only
  `<current_uploads>`, while the frontend keeps stripping the legacy tag so
  old threads still render cleanly.
- **sandbox:** Make the model-facing `description` argument optional (empty by
  default) across `bash`, `ls`, `glob`, `grep`, `read_file`, `write_file`,
  `str_replace`, and `task`, so providers that omit it are no longer rejected
  before execution.
- **sandbox:** Scope the Windows MSYS path-conversion exclusion to safe virtual
  path prefixes instead of disabling conversion globally, so host-native CLI
  launchers that need normal conversion work again.
- **skills:** Tokenize portable `allowed-tools` scalars with parenthesis
  awareness, so `Bash(tvly *)`-style entries stay intact, unmatched
  parentheses are rejected instead of silently fragmenting, and
  argument-scoped entries remain literal rather than broadening access.
- **config:** `use_previous_response_id` works in a `config.yaml` model entry —
  it is not a `ModelConfig` field and reaches `ChatOpenAI` only through the
  model factory's `extra="allow"` passthrough — but was never documented, and
  reads like a synonym for `use_responses_api`. It is not: `use_responses_api`
  picks the endpoint, while `use_previous_response_id` switches the Responses
  API from replaying the full history each turn to chaining on server-side
  state. The OpenAI Responses API example in `config.example.yaml` gains a
  commented `use_previous_response_id: false` line noting that it is forwarded
  to `ChatOpenAI` as-is, that chained context is still billed as input tokens,
  and that client-side history rewrites only apply when the history is
  replayed. Comment only — no schema change, no new `ModelConfig` field, no
  `config_version` bump.
- **mcp:** Reconnect ordinary stdio tools after a transport disconnect: the
  failed pooled session is evicted (only if still registered), the original
  error surfaces without automatic replay, and a later retry starts a fresh
  subprocess.
- **mcp:** Reject credentials that cannot travel as HTTP header values
  (trailing newline or whitespace, non-ASCII) at the config boundary, so the
  transport's exception - which echoes the full value - can no longer leak a
  secret into model context, checkpoints, and traces.
- **subagents:** Stop the zombie PENDING registry entry on the submit-failure
  path, and derive the capacity snapshot's queued count from the waiters'
  length instead of iterating a deque other threads mutate.
- **discord:** Retain strong references to ack-reaction tasks and drain them
  on shutdown, so a GC pass can no longer silently drop a reaction or pin the
  channel across restart cycles.
- **streaming:** Stop an `IndexError` in `MemoryStreamBridge._make_gap` when a
  subscriber reconnects to an empty or drained stream with an expired cursor.
- **frontend:** Format structured upload error details (FastAPI validation
  issues, objects, arrays) instead of showing `[object Object]`.
- **frontend:** Truncate selected model names to the selector button width, so
  long model names ellipsize in the composer and sidecar instead of
  overflowing.
- **dev:** Default the frontend dev server to Webpack on all platforms
  (`OMNI_HARNESS_DEV_BUNDLER=turbo` opts back into Turbopack), avoiding
  Turbopack's macOS PostCSS worker leak and its Windows runtime panics.
- **scripts:** Run repo shell scripts through an explicit interpreter
  (`bash scripts/...`), so a lost executable bit - zip/tarball downloads,
  `core.fileMode=false`, non-POSIX filesystems - no longer breaks
  `make docker-start` and friends with `Permission denied`.
- **memory:** Memory reads configured to stop the turn now raise a
  backend-neutral `MemoryReadError` that prompt assembly preserves instead
  of swallowing: strict OpenViking (`read: raise`), Mem0, and Honcho reads
  propagate, OpenViking scope-resolution failures follow the configured read
  policy, and the 5-second injection deadline honors the same policy
  (fail-open continues without the context; strict raises with the timeout
  as its cause).
- **scripts:** On native Windows, `shutil.which("pnpm")` follows
  `PATH`/`PATHEXT` resolution and can select a generic `pnpm` match — an `.exe`
  or `.bat`, or an earlier-path wrapper — ahead of the npm-installed `pnpm.cmd`
  wrapper. The shared host runner now checks `pnpm.cmd` and `corepack.cmd`
  before the generic names, matching the Windows command-selection order the
  repo already documents; POSIX resolution order is unchanged.
- **tests:** The backend suite failed 68 shell-script tests across seven files
  on a Windows contributor host, none of them for anything wrong with the code
  under test. CreateProcess searches `System32` before `PATH`, so the WSL
  `bash.exe` launcher won every `["bash", ...]` spawn and could not run the
  repo scripts against Windows checkout paths — on non-English Windows its
  localized UTF-16LE warning crashed the harness's pipe decoding and buried the
  real failure behind a `TypeError`; `sh` does not exist outside MSYS2; and
  `dev-entrypoint.sh`'s `command -v python3` probe selected the Microsoft Store
  alias stubs, which exit 49 when executed. The suites now resolve a shell
  through a shared helper that mirrors the repo's Git Bash wrapper discovery
  and explicitly rejects the WSL launcher and the Store stubs, and skip cleanly
  where no Git Bash exists. POSIX and CI behavior is unchanged.
- **tests:** Five tests in the skill request-scoped-secrets suite failed on a
  Windows host and two negative checks passed vacuously, because the probes
  embedded POSIX syntax: `LocalSandbox._get_shell()` resolves to PowerShell
  there, where `$VAR` is an undefined PowerShell variable and expands to
  nothing, so the positive checks could never see an injected value and the
  `"secret" not in out` assertions were comparing against empty output. Probes
  are now rendered in the syntax of the shell production actually resolved —
  `$env:NAME` under PowerShell, `%NAME%` under cmd.exe, `$NAME` under POSIX
  shells — so the negative checks genuinely verify scrubbing on Windows, and
  the per-call-scoping case also proves the injected value reached the first
  subprocess. POSIX output is unchanged in form.
- **tests:** Checkpoint retention needs an executable statement of what a
  deletion may never break — a newest-N proposal had to be withdrawn once
  review showed it would silently break branch and time-travel parent-chain
  semantics. The new suite pins six retention scenarios across the memory,
  SQLite and Postgres checkpointers: growth baselines per step for the full and
  delta schemas; deleting a branch ancestor fails loudly with
  `CheckpointLineageError` instead of silently corrupting branch/regenerate;
  deleting an explicit resume target removes the resume surface; pending writes
  are retained state rather than garbage; and a trailing duration-only leaf and
  a leaf sibling branch — the real fork path — can be deleted safely. A
  companion draft documents the protected set, the provably safe deletion
  shapes, and joint-table mechanics with orphan accounting, for any future
  `max_checkpoints_per_thread` or TTL work to be validated against.
- **agents:** Conversation titles are generated from the user's original
  message content when upload (or other) context wrappers have been injected
  into the text, so titles no longer quote server-injected
  `<current_uploads>` context; attachment-only messages keep the
  `New Conversation` fallback.
- **agents:** Custom-agent storage falls back to file-backed storage only
  when search mode cannot resolve the main application config — invalid
  configuration and missing config paths surface instead of silently
  switching storage backends — and store IO moves off the event loop in
  async agent routes.
- **sandbox:** `list_dir` and `glob` in the five remote sandbox providers
  (E2B, OpenSandbox, AIO, Tenki, BoxLite) return filenames verbatim instead
  of stripping whitespace, so files whose names begin or end with spaces are
  no longer listed under paths that then do not exist.
- **sandbox:** The Bash tool guides the agent to detect its execution
  environment with evidence (`uname -s`, `sw_vers`, `uname -a`) instead of
  model assumptions, and rejected host paths direct it to command-only
  probes or allowed virtual paths rather than repeating the blocked command.
- **sandbox:** File appends no longer destroy existing content when the
  pre-read fails: E2B append treats only missing-file errors as an empty
  file and re-raises anything else instead of overwriting the file with just
  the appended tail, and AIO appends use the server's native append mode
  without a pre-read at all.
- **skills:** Skill markdown is read explicitly as UTF-8, so localized skills
  validate on Windows hosts whose default code page is not UTF-8 instead of
  failing with `UnicodeDecodeError`.
- **mcp:** Sync-wrapped MCP tools keep LangGraph `ToolRuntime` injection (the
  annotation-less sync wrapper is now `functools.wraps`-transparent), so
  per-user scope resolution and durable task submission no longer run with
  `runtime=None` — which had routed completion-notification runs under the
  default lead agent instead of the thread's custom agent.
- **frontend:** The mobile sidebar trigger stays clickable on regular and
  custom-agent welcome pages, where multi-line (longer localized) welcome
  text in a same-`z-index` overlay could cover the header's tappable area.
- **browser:** Background live-frame scheduler tasks retain strong
  references, so garbage collection can no longer silently stop the Browser
  Live view from refreshing by stranding a pending guard that was cleared
  only in a collected task's `finally`.
- **runtime:** Terminal finalization completes after a cancellation raised
  inside the completion hook or task-stop fan-out, so extension observers
  run and the stream END marker is published before the interruption is
  re-raised; the finalization tail stays interruptible.
- **runtime:** The embedded `OmniHarnessClient` keys its graph cache by
  effective user in every authorization mode and materializes the same user
  in runtime context, so sequential reuse for different users can no longer
  serve a graph assembled with another user's prompt and workspace state.
- **runtime:** Cancelled workspace-change snapshot captures drain their
  already-running scan and clean up the per-run text cache instead of
  leaking `omniharness-workspace-changes-*` directories, while metadata-only
  captures propagate cancellation promptly without waiting on the scan.
- **persistence:** Gateway startup tolerates a database already migrated to
  the explicitly-reviewed newer revision (`0019_thread_incarnations`), so
  rolling back to this image after a newer deployment stays possible; other
  unknown revisions, an empty version table, and multiple version rows
  still fail closed.
- **uploads:** Fenced code blocks are excluded from uploaded-document
  outlines, so code comments and bold examples inside fences no longer
  crowd real sections out of the 50-entry heading budget.
- **dev:** `_pick_python()` validates interpreter candidates through
  `/usr/bin/env`, mirroring how the frontend is launched, so `make dev`
  starts the frontend on Windows where Microsoft Store Python stubs satisfy
  Bash-side probes but not `env`. scans.
- **subagents:** Deduplicate streamed AI messages via a seen-id set (O(n²) ->
  O(n)).
- **sandbox:** Cache `LocalSandbox` path-rewrite regexes and local-path masking
  patterns per instance instead of recompiling per search match.
- **messages:** Index tool-call results per group.
- **frontend:** Stop re-deriving message content on every stream chunk.
- **browser:** Encode Browser Live progress frames as JPEG to cut progress
  payload size.
- **frontend:** Cache settled copy-data derivation across streaming chunks, so
  each chunk no longer re-derives toolbar/copy text for every settled
  message.
- **frontend:** Chat streams request `messages-tuple` + `updates` + `custom`
  instead of full `values` state snapshots — the retransmitted historical
  `values` messages were ~75% of SSE payload — folding reducer events into
  rendered state locally while keeping full snapshots only for replay-gap
  recovery.
- **prompt-injection:** New input-sanitization middleware defends against
  prompt-injection, forged framework tags in the input guardrail are blocked,
  and system context is injected as a `SystemMessage` for role isolation.
- **prompt-injection:** HTML-escape untrusted content rendered into model prompts
  - memory facts and summaries, `SOUL.md`, subagent descriptions, skill metadata,
  and the conversation block in the memory-update prompt - and neutralize
  prompt-injection tags in `web_capture` tool results.
- **prompt-injection:** Escape MindIE tool-response framing. The provider's
  `_fix_messages` escaped tool-call names and arguments before rendering them
  into `<tool_call>` / `<function=...>` tags, but the sibling path that wraps a
  `ToolMessage` in `<tool_response>` passed its text through unescaped — and
  that output arrives largely unsanitized, because the tool-result sanitizer
  covers only the remote-content tools on its allowlist (`web_fetch`,
  `web_search`, `image_search`, `web_capture`) and deliberately leaves local
  `bash` / `read_file` output and differently named MCP tools alone. A literal
  `<tool_response>` in a `read_file` result therefore closed the framing early,
  and everything after it was presented to the MindIE model as though it sat
  outside the tool response, so a payload planted in an untrusted file could
  forge a `<system-reminder>`. Content is now HTML-escaped with `quote=False`,
  matching the tool-call path; the model still decodes the entities back, so
  only the framing is protected and legitimate results are understood exactly
  as before.
- **secrets:** Scrub inherited secret environment variables (`MYSQL_PWD`,
  `REDISCLI_AUTH`, abbreviated `*_PASS`, and Postgres `PGPASSFILE`) from the
  skill environment; request-scoped secrets are bound for both slash-activated
  and autonomously-invoked skills.
- **web_fetch:** SSRF guard for self-hosted providers.
- **authz:** Global skills-management endpoints now require admin; the legacy
  skills mount is gated by user visibility; artifacts honor a trusted
  `owner-user-id` header; and the trusted authorization principal is propagated
  through the runtime.
- **auth:** Persist the `csrf_token` cookie for the access-token lifetime.
- **mcp:** Reject legacy MCP credentials in run metadata.
- **auth:** Harden validation of the post-login `next` path.
- **frontend:** Send the session cookie on model, workspace-change, and
  ranged artifact reads in split-origin deployments.
- **skills:** Copy projected skill files instead of hardlinking them, so a
  sandboxed write can no longer mutate the canonical skill source, and fail
  closed on a drifted projection namespace on every platform, including
  Windows.
- **scripts:** Redact secret-shaped keys (`db_pass`, `signing_key`, ...)
  wherever they appear in bundled config, not only under well-known key
  names.
- **sandbox:** Harden local Docker sandbox containers: published ports bind
  the Docker bridge gateway instead of `0.0.0.0` when the sandbox host is
  non-loopback (`OMNI_HARNESS_SANDBOX_BIND_HOST=0.0.0.0` restores the broad
  bind), Docker's default seccomp profile replaces unconditional
  `seccomp=unconfined` (opt back in with `OMNI_HARNESS_SANDBOX_SECCOMP_UNCONFINED=1`),
  and containers drop all capabilities, get `no-new-privileges`, and run with
  bounded resources.
- **authz:** Re-check the authorization policy before reusing a persisted
  sandbox, so a revoked `sandbox:execute` grant takes effect on the next
  sandbox-backed turn instead of outliving the policy in the cached sandbox.
- **runs:** Reject cancel/rollback actions on GET stream joins with
  `405 Method Not Allowed` - cancel-then-stream is a POST operation - closing
  a state change that CSRF middleware deliberately exempted on safe methods;
  action-less GET joins are unchanged.
- **sandbox:** `SSH_AUTH_SOCK` is scrubbed from the sandbox subprocess
  environment — inheriting the host ssh-agent socket lets sandboxed code
  sign and authenticate with every key the agent holds — unless a skill
  explicitly declares it via required-secrets.

### Documentation

- **docs:** Clarify how `LocalSandboxProvider` resolves `sandbox.mounts[].host_path`
  under production Docker, with gateway bind-mount and config examples.
- **docs:** Document the GitHub inbound-dedupe TTL semantics, including what
  redeliveries are not deduped, and tighten the redelivery tests.
- **docs:** Document the Honcho memory backend with a dedicated guide and a
  long-term memory section entry in the README.
- **docs:** Restructure the subagent documentation into an eleven-chapter user
  manual under `harness/subagents/` in both languages: concepts, quick start,
  the catalog, delegating work, results and acceptance, limits and capacity,
  sandbox and isolation, observability, troubleshooting by symptom, developer
  integration, and a reference appendix with the June to September 2026
  change log. The former single page becomes the section index, so existing
  page links keep working; deep links to sections of the old page now land
  on the index.

### Internal

- **tests:** Migrate frontend unit tests to rstest and run hook-level tests in
  a DOM environment.
- **tests:** Require explicit opt-in for live client tests.
- **tests:** Replace the magic unwritable absolute path in tool-output tests
  with a self-constructed failure condition.
- **tests:** Add trace-based behavioral tests with Monocle Test Tools,
  asserting agent routing, tool calls, and token/duration cost.
- **tests:** Add SQL and concurrent-reconciler coverage for lease-aware orphan
  recovery.
- **tests:** Lock in POST logout from the gateway-offline banner.
- **refactor:** Extract frontend placeholder detection into a tested utility.
- **refactor:** Consolidate E2B client lifecycle helpers and reuse the kill
  helper during warm-pool eviction.
- **refactor:** Name the E2B capacity-ledger meta-field count so the admission
  offset is explicit.
- **ci:** Publish the lark-cli-init and lark-broker images.
- **bench:** Add an isolated checkpoint channel-mode benchmark comparing `full`
  and `delta` across latency, storage, and replay metrics.
- **deps:** Bump `cryptography` 49.0.0 -> 50.0.0, `postcss` 8.4.31 -> 8.5.25,
  `h2` 4.3.0 -> 4.4.1, `langgraph-checkpoint-sqlite` and
  `langgraph-checkpoint-postgres` 3.1.0 -> 3.1.1, `nanoid` 5.1.6 -> 5.1.16,
  `h3` 1.15.6 -> 1.15.9, and `next` 16.2.11 -> 16.3.3. The `next` bump closes
  two unauthenticated remote code execution advisories — one in the Image
  Optimization API's AVIF path, one on Windows-hosted servers — while `h3`
  stops a double-encoded dot segment from traversing out of the static route.
- **bench:** Add a reproducible hybrid memory-eviction evaluation under
  `backend/scripts/benchmark/omnimem_eviction/` with a deterministic,
  blind-by-construction grader for the #4789 policy.
- **tests:** Exclude `tests/blocking_io/` from `make test`; the dedicated
  `make test-blocking-io` suite (and its CI workflow) remains the owner.
- **ci:** Split the backend unit-test workflow into four parallel shards —
  each on its own runner with isolated Postgres/Redis — using `pytest-split`
  with a committed duration baseline and failing closed when the baseline is
  missing; `make test` remains the canonical full offline suite.
- **tests:** Skip the POSIX mode-bit skill-permission assertions on Windows,
  where the `chmod` contract is unobservable, so Windows contributors can
  reach a green backend-suite baseline.: a caller whose `skills` policy allows nothing
  — or a fresh install with no skills — receives `[]` from `GET /api/skills`,
  and the composer must degrade to a builtin-only dropdown, never a broken
  or fully vanishing one. New tests drive the matcher and mount the real
  `InputBox` with an empty catalog: typing `/` offers exactly the builtin
  commands, and an unmatched query renders no listbox. No production code
  changed; all four `useSkills()` consumers were audited and already
  degrade gracefully.


## [2.0.0] — 2026-06-15

OmniHarness 2.0 is a ground-up rewrite around a "super agent" harness with
sub-agents, persistent memory, sandbox execution, and an extensible
skills/tools system. It shares no code with the 1.x line, which now lives on
the [`main-1.x` branch](https://github.com/jokerking-oss/omni-harness/tree/main-1.x).

This release closes the 2.0.0 milestone with a full release cycle since the first 2.0 tag.

### ⚠ Breaking changes

- **harness:** Hydrate runs from `RunStore` and persist interrupted status. Run
  cancellation/multitask semantics now require a working RunStore on the
  worker that owns the run; cross-worker cancels return 409 instead of
  silently appearing successful.
- **loop-detection:** Make loop detection configurable with per-tool frequency
  overrides; keep configurable on/off switch.
- **loop-detection:** Defer warning injection so detector pairs cleanly with
  tool-call lifecycle.
- **subagents:** Stream subagent token usage to the header via terminal task
  events.
- **suggest:** Make AI follow-up question suggestions optional.
- **community:** Add Brave Search web search tool.
- **im:** Add user-owned IM channel connections — users can bind their own
  Slack/Telegram/Discord/Feishu/DingTalk/WeChat/WeCom accounts on top of the
  operator-configured bots.
- **models:** Add MiniMax provider for image/video/podcast skills plus a new
  music-generation skill.
- **community:** Add Serper Google Images provider for `image_search`.

#### Observability
- **trace:** Set the LangGraph trace name to `lead_agent` (or the custom
  agent's `agent_name`) for cleaner Langfuse/LangSmith traces.
- **defaults:** Enable token usage tracking by default.
- **trace:** Attribute subagent spans to the parent thread's Langfuse trace.
- **skill:** Add maintainer issue and PR workflow skill.

### Performance

- **harness:** Push thread metadata filters into SQL instead of post-filtering
  in Python.
- **runtime:** Index messages in `MemoryRunEventStore` to avoid O(n) scans.
- **sandbox:** Speed up `should_ignore_name` in glob/grep walks.
- **uploads:** Add Windows support for safe symlink-protected uploads.
- **mcp:** Harden the MCP config endpoint against malformed input.
- **gateway:** Cap skill artifact preview decompression to prevent
  zip-bomb-style abuse.
- **sandbox:** Do not bind-mount host CLI auth dirs by default.
- **runtime:** Persist run message summaries.
- **runtime:** Protect the sync singleton's init and reset paths.
- **runs:** Restore historical runs from persistent store after a gateway
  restart.
- **gateway:** Make cancel idempotent for already-interrupted runs.
- **events:** Serialize structured DB event content.
- **persistence:** Reuse token usage model grouping expression.
- **nginx:** Defer CORS to the gateway allowlist instead of double-applying it.
- **gateway:** Enforce thread ownership on stateless run endpoints.
- **serialization:** Strip base64 image data from streamed values events.
- **gateway:** Attribute token usage to the actual models.
- **subagents:** Use model override for tools and middleware.
- **subagent:** Isolate subagents from the parent run's checkpointer.
- **agents:** Resolve duplicate `todos` channel type conflict in
  `TodoMiddleware`.
- **agents:** Keep new agent bootstrap in user scope.
- **middleware:** Sync raw tool-call metadata.
- **middleware:** Prevent todo completion reminder IM-message leak.
- **agents:** Require `config.yaml` in `resolve_agent_dir` to skip memory-only
  directories.
- **middleware:** Offload the uploads scan in `UploadsMiddleware` off the event
  loop.
- **middleware:** Externalize oversized tool output into the sandbox for
  non-mounted sandboxes.
- **subagents:** Raise general-purpose `max_turns` to 150 and default timeout to
  30 min.
- **memory:** Isolate queued memory updates by agent.
- **tracing:** Propagate `session_id` and `user_id` into Langfuse traces.

#### Tools, sandbox & MCP
- **mcp:** Fix env resolution in MCP config lists.
- **sandbox:** Supplement `list_running` in `RemoteSandboxBackend`.
- **sandbox:** Avoid blocking sandbox readiness polling.
- **sandbox:** Scope provisioner PVC data by user.
- **tools:** Introduce `Runtime` type alias to eliminate Pydantic serialization
  warnings.
- **harness:** Wrap async-only config tools for sync client execution.
- **tool-search:** Reliably hide deferred MCP schemas by removing the
  ContextVar.
- **web_fetch:** Support a proxy for the Jina reader in restricted networks.
- **sandbox:** Fix stale AIO sandbox cache reuse.
- **sandbox:** Stop flagging string-literal path fragments as unsafe absolute
  paths.
- **mcp:** Make stdio MCP-produced files resolvable via virtual sandbox paths.
- **mcp:** Add a tools cache reset endpoint.

#### Skills & channels
- **skills:** Enforce `allowed-tools` metadata.
- **skills:** Fix custom skill install permissions.
- **skills:** Surface the offending line and a quoting hint on SKILL.md YAML
  errors.
- **channels:** Ignore hidden control messages when extracting replies.
- **channels:** Surface WeCom WebSocket connection failures.
- **channels:** Require a bound identity for user-owned IM messages.
- **channels:** Make runtime provider state authoritative.
- **channels:** Make the channel connect flow deterministic.
- **channels:** Add operational guardrails.

#### Auth
- **auth:** Replace setup-status 429 rate limit with a cached response.
- **auth:** Align auth-disabled mode with mock history loading.
- **chat:** Prevent the first user message from being swallowed in new
  conversations.
- **frontend:** Wait for async chat submit before clearing the input.
- **frontend:** Deduplicate restored thread messages.
- **frontend:** Hide the copy button for streaming assistant messages.
- **frontend:** Isolate new chat thread messages.
- **frontend:** Cap deeply nested list indentation to prevent render crashes.
- **token-usage:** Dedupe token usage aggregation by message id.
- **frontend:** Remove the Backspace shortcut for deleting prompt attachments.
- **suggestions:** Strip inline `<think>` reasoning before parsing follow-up
  questions.
- **frontend:** Paginate the workspace chat list beyond 50 threads.
- **frontend:** Keep the workspace interactive when the SSR auth probe cannot
  reach the gateway.
- **frontend:** Reset the active chat after deletion.
- **frontend:** Render full content for multi-part AI messages.
- **harness:** Resolve runtime paths from the project root.
- **docker:** Default Gateway to a single worker to prevent multi-worker
  breakage.
- **scripts:** Preserve `uv` extras across `make dev` restarts.
- **scripts:** Clean up local nginx on stop.
- **config:** Make the reload boundary discoverable from code.
- **replay-e2e:** Key replay fixtures by caller and conversation.
- **config:** Coerce null `config.yaml` list sections to an empty list.
- **scripts:** Create the backend/sandbox dir before the uvicorn reload-exclude.
- **makefile:** Fix per-commit hooks installation.

### Changed

- **provider (refactor):** Share assistant payload replay matching across
  providers.
- **todo (refactor):** Remove the unused completion reminder counter.
- Clean standalone LangGraph server remnants from docs.
- Document custom AIO sandbox images.
- **runtime:** Add lifecycle end-to-end coverage.
- **blocking-io:** Fail-loud repo-root resolution and shared detector CLI
  shim.
- **ci:** Consolidate PR/issue labeling and fix the reviewing-job crash and
  label thrash.

[2.0.0]: https://github.com/jokerking-oss/omni-harness/releases/tag/v2.0.0

