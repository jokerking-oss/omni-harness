# 更新日志

本文件记录 OmniHarness 的所有重要变更。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本规范](https://semver.org/lang/zh-CN/)。

[English](./CHANGELOG.md) | 中文


## [2.1.0] — 2026-09-24

### ⚠ 不兼容变更（Breaking Changes）

- **网关：** 现在会无条件签发请求 trace id，且每个 Gateway HTTP 响应都会携带
  `X-Trace-Id` header。此前二者均受 `logging.enhance.enabled` 控制；该配置现在
  **仅控制日志输出**——即日志记录是否包含 `trace_id` 字段及其格式。此 header
  无法关闭；使用默认 `enabled: false` 的安装在升级后也会开始收到它。定时任务、
  MCP 任务通知 run、IM 渠道消息以及内嵌 `OmniHarnessClient` 都会为每个工作单元绑定
  一个 id，因此此前没有 trace id 的 run 记录、checkpoint 元数据和 Langfuse trace
  现在也会包含它。run 请求的 `metadata` 或 `config.context` 中提供的
  `omniharness_trace_id` 现在会被忽略并覆盖，以确保响应 header、日志和持久化 run
  保持一致；如需跨服务固定关联 id，请发送 `X-Trace-Id` 请求 header。`logging`
  仍需重启后生效。未新增或移除任何配置键。
- **沙箱：** E2B 现在将 `sandbox.replicas` 作为进程级容量上限来强制执行。默认的
  `wait` 策略会等待 `acquire_timeout`，随后令当前智能体回合失败。OmniHarness 不会自
  动重试该回合。可使用 `burst` 配合 `burst_limit` 允许有限地超出额度多开 VM。`reject`
  策略可在返回容量错误前先回收一个预热 VM。
- **记忆：** 记忆系统现已可插拔（`memory.manager_class` 选择后端；默认 `omnimem`
  自包含）。OmniMem 私有配置从 `memory:` 顶层移入 `memory.backend_config`，`/memory/config`
  响应（以及 `client.get_memory_config()`）的结构也发生了变化。
- **记忆：** 自定义 `memory.storage_class` 发生迁移：旧的默认路径 `omniharness.agents.memory.storage.FileMemoryStorage`
  已不存在（现为 `omniharness.agents.memory.backends.omnimem.omnimem.core.storage.FileMemoryStorage`
  ）。自定义 `MemoryStorage` 子类的 `__init__` 必须接受 `config`（此前为无参）。
  损坏或过期的 `storage_class` 会记录错误并回退到 `FileMemoryStorage`（不会崩溃
  ）——请更新路径与签名以恢复使用。
- **记忆：** 当 `memory.mode: tool` 搭配一个未实现 `search()` 的后端时，现在会在
  Gateway 启动时由 `MemoryManager` 的不变量校验快速失败并抛出 `ValueError`，而不
  是启动成功后在每次 `memory_search` 调用时静默返回空结果。两个内置后端都实现了
  `search()`（OmniMem 会检索，`noop` 返回 `[]`），因此仅影响未覆盖 `search()` 就
  接入的自定义后端。这是有意为之——静默返回空比启动期报错更糟。修复方式：切换到 `mode:
  middleware`，或覆盖 `search()`（并设置 `supports_search=True`）。
- **Docker：** 两份 compose 文件发布的入口端口现在默认只绑定回环地址
  (`127.0.0.1`)。依赖旧 `0.0.0.0` 绑定的部署必须设置 `BIND_HOST` 才能向其他网卡
  暴露服务。

- **scheduled-tasks：** 保存任务前即可查看即将到来的 cron 触发时刻。
  `POST /api/scheduled-tasks/preview-cron` 接受五段式 cron 表达式、时区、1–10
  的 `count`（默认 5）与一个可选的带时区（aware）参考时间，返回规范化后的
  cron、生效的 UTC 参考时间，以及 UTC 与本地时间下的触发时刻。
  它在工作线程中运行调度器自己的计算器，因此 DST 处理与保存后的任务实际
  行为一致；它不预留任何资源，也不触碰任何 task、thread 或 run 存储；输入
  非法与日期范围失败都会返回 422。

- **scheduled-tasks：** 可以在服务端按触发状态过滤 run 历史。过去要找一个罕见
  的失败，只能把每一页历史都下载下来在客户端过滤，因为埋在大量较新成功记录
  后面的失败可能出现在任何一页；`GET /api/scheduled-tasks/{task_id}/runs`
  现在接受 `?status=`，取值有 `queued`、`launching`、`running`、`success`、
  `failed`、`skipped` 与 `interrupted`，并在分页之前应用该谓词，因此
  `?status=failed&limit=50&offset=0` 返回的就是第一页真正的失败记录。未知
  取值（包括父任务自身的 `completed`）返回 422，空结果返回 `[]`，
  未过滤时的数组响应保持不变。

#### 认证
- **认证：** 新增用于程序化 API 访问的个人访问令牌（PAT）：
  `POST/GET/DELETE /api/v1/auth/pats` 用于管理令牌（仅展示一次，以 SHA-256
  摘要存储）；默认拒绝的路由策略只允许会话/run 生命周期路由，并进一步受令牌的
  `threads`/`runs` scope 限制；任何具有取消能力的请求维度（`?action=`、
  `multitask_strategy`）还额外要求 `runs:cancel`。

- **settings：**账户偏好可以跨浏览器清理或设备更换保留。通知开关、默认模型、对
  话模式与推理力度以独立的 `(user_id, key)` 行存储，位于需会话认证的
   `GET`/`PATCH /api/v1/auth/preferences` 之后，并在首帧渲染前从服务端拉取，同
  时配备标签页本地的发件箱与有上限的退避重试，因此失败的写入不会被静默丢弃；
  `null` 会重置某个字段。只有这四个白名单字段会被传输——设备通知权限、显示设置
  与线程级模型覆盖都保留在本地，自动的输入框回退也不会作为显式账户偏好上传。现
  有的无作用域本地设置不会被迁移，因为它们没有已知归属，因此用户升级后需要重新
  选择这四项。

#### 智能体与运行时
- **scheduler：**定时任务可以把 `assistant_id` 固定为 `lead_agent`（默认）或创
  建者已有的自定义智能体。未知或格式错误的名称返回 422。工作区的创建/编辑表单
  提供同样的选择。

- **gateway：**`GET /api/threads/{thread_id}/runs/page` 以
   `(created_at, run_id)` 键集游标翻页遍历线程 run 历史（
  `{data, has_more, next_before_created_at, next_before_run_id}`）。
  `GET /api/threads/{thread_id}/runs` 仍返回仅含最新 100 条 run 的裸数组，以便
   LangGraph SDK 客户端继续工作。

- **中间件：** 新增 `TokenBudgetMiddleware`，强制单个 run 的 token 预算，在主智
  能体与子智能体之间累加共享。
- **上下文：** 每个 run 记录生效的记忆身份，并在摘要过程中持久化持久上下文（系统
  消息、记忆与工具状态），以结构化运行时元数据的形式发出，压缩（compaction）不再
  丢失这些信息。(、、)
- **运行时：** 目标延续（goal continuation）允许 run 跨多个智能体回合朝目标继续
  执行，并跟踪、限制 `continuation_count`。
- **子智能体：** 系统维护的委派账本（delegation ledger）防止对在途任务重复委派，
  并设总委派上限以约束单个 run 的扇出。
- **子智能体：** 在会话中持久化并展示子智能体的步骤历史。
- **文件：** 文件工具引入确定性的“写前读”版本门控，避免覆盖并发编辑。
- **网关：** 感知缓存的成本核算将 token 成本归因到缓存 / 未缓存路径；Redis stream
  桥接启用分布式事件流；并向用户暴露手动上下文压缩。(、、)
- **网关：** 可通过 `stream_bridge.heartbeat_interval_seconds` 配置 stream bridge
  的心跳间隔（默认 15 秒），使位于激进 proxy 空闲超时之后的部署可以统一调节 SSE、
  `/wait` 和内部订阅者。
- **智能体：** 配置声明的主智能体中间件，让部署方无需修改运行时链即可加入自定义
  `AgentMiddleware` 类。
- **运行时：** 记录终态的 artifact 投递回执，使预期要 `present_files` 的 run 在
  投递失败时不再误报成功。

- **运行时：** Delta 模式 checkpoint 历史缓存（内存/Redis）支持 O(1) 增量合成，
  通过 `database.checkpoint_cache` 配置。
- **运行时：** 每次工具调用都会携带由运行时签发且可防篡改的工具回执；有界回执账本
  会注入模型上下文，使智能体能在报告中引用执行证据。默认通过新的 `verification`
  配置节启用。
- **子智能体：** 子智能体委派现在可验证，并按 the RFC 分层实现：每份子智能体
  报告都必须引用工具回执（例如 `[r3 write_file]`），并为每个交付物附上可验证
  handle；主智能体会将这些引用与子智能体的实际执行记录交叉核对，`task` 委派的
  `acceptance_criteria` 也会在父侧确定性检查（文件是否存在/非空、记录的测试命令
  退出状态），无法判定的项目会报告为 UNVERIFIED，而不是静默通过。(、、)
- **澄清：** 人工输入卡片支持结构化表单字段，智能体可精确请求所需信息。
- **子智能体：** 设置页新增部署级子智能体目录；自定义智能体可配置显式 worker
  allowlist，并在 prompt 与执行阶段同时强制执行。
- **智能体：** 注入 lead / 子智能体 prompt 的当前日期上下文遵循可选的
  `OMNI_HARNESS_DATE_TIMEZONE` 环境变量（IANA 名称，如 `Asia/Shanghai`），非 UTC
  部署的用户在午夜前后不再被告知错误的“今天”；未设置时保持服务器本地时区行为。

- **agents：**读取先于写入的拦截现在会把被阻止的 `write_file` / `str_replace`
  调用中无用的负载（`content`、`old_str`、`new_str`）从发往模型的请求中剔除。
  被阻止的调用从未执行，必须在重新读取后重新发出，因此原始参数只会占用上下文；
  已存储的历史、回执与 run 日志都会保留它们。被阻止的结果会与调用出现位置配对
  （工具调用 id 可能跨回合重复），而历史被重写的请求会丢弃 OpenAI 的 `resp_`
  响应 id，使 `use_previous_response_id` 链无法恢复原始的服务端历史。由
   `read_before_write.elide_blocked_payloads`（默认开启）与
   `read_before_write.elide_min_chars`（默认 2000）控制。

- **agents：**自定义智能体的 `config.yaml` 接受 `memory_enabled: false`，以把
  该智能体作为无状态的执行 worker 运行；省略时默认为 `true`。该退出选项只把该
  智能体从记忆生命周期中移除——召回记忆注入、被动捕获、
  `memory_search` / `memory_add` / `memory_update` / `memory_delete` 工具以及
  工具模式的记忆指引全部被抑制，自动摘要与手动 `/compact` 也会跳过持久记忆刷写。
  关闭一个已有智能体只清除 checkpoint 状态中被冻结的、由服务端标记的记忆提醒：
  日期提醒、真实的用户消息与未标记的相似内容都会保留，其他每个智能体的全局记忆
  设置都不受影响。

- **subagents：**持久化的 `batch_task` 条目现在接受与普通 `task` 委派相同的可
  选 `acceptance_criteria`，因此批处理 worker 无法再声称某个缺失的交付物存在却
  仍作为成功条目落地、且没有任何记录在案的检查。判据在持久化前会被规范化（20
  条可用条目、中性化后 500 个字符；空值变为 `null`），并在租约恢复后保留；已完
  成的执行会复用现有的确定性检查器，对照归属方作用域内的线程文件与已记录的测试
  命令证据。条目查询与 JSONL 导出新增可空的 `acceptance_criteria` 和单独校验的
   `acceptance_verdict`（`holds`、`does not hold` 或 `UNVERIFIED`）：一个已完
  成、带有报告、缺少 CSV 且含不受支持的质量声明的条目会保持 `succeeded`，并带
  上这三个叶子，也不会被自动重试。没有判据的条目与遗留行不报告任何结论。

- **context：**可选的任务笔记与压缩历史召回，由 `task_continuity.enabled`（默
  认 `false`；配置 schema 新增该小节并带禁用默认值）控制。启用后，`task_note`、
  `history_search` 与 `history_read` 会在现有授权与技能策略下对标准主智能体和
   `OmniHarnessClient` 暴露，并同时支持同步与异步工具执行。`task_note` 在共享状态
  通道中保存关于约束、决策、失败尝试与下一步的简短检查点笔记，每次写入都强制执
  行笔记本容量限制与报告形态，并在持久化上下文的人类消息中渲染为已转义的历史数
  据。自动与手动压缩还会把有界的消息和工具文本——包括真正的隐藏澄清卡片答案——保
  留到沙箱挂载之外的 user/thread 本地 SQLite FTS5 归档中，随后由
   `history_search` 与 `history_read` 查询；格式错误的 checkpoint 元数据会报告
  为不可用，而不会中断模型调用或压缩，存储故障也不会影响普通压缩。这是单一任务
  内的字面召回：它不会恢复 run、跨主机复制归档，也不会创建跨线程记忆，且不引入
  任何 embedding 依赖。

- **gateway：**Gateway run 可以被要求读取一段指定的更早对话。可选的
   `read_conversation` 加上 `conversation_references` run 字段（最多三个线程
   id 或同源的聊天 URL）会授予主智能体对上一段对话的面向模型读取权限，同时继续
  当前任务；普通消息文本从不授予访问权，该授权绑定到该次 run 的引用、该 run 的
   `runs:read` 权限以及每个来源的归属。读取复用现有的转录分页与可见性规则，返
  回有界的用户与助手文本，并带上来源 id、续接游标以及截断或不可用声明，同时排
  除隐藏上下文、推理块与原始工具结果。读取器从不持久化到配置中，并在 run 结束
  时释放，因此恢复与重放需要再次提供引用；bootstrap、子智能体与普通嵌入式路径
  都不会获得它。文本上限为每条消息 4000 字符、每页 20000 字符。

- **tools：**`list_uploaded_files` 接受可选的 `query`（大小写不敏感的文件名子
  串）与 `extensions`（`"pdf"` 或 `".PDF"`，两者都表示 `.pdf`），且两个过滤器
  都运行在 20 文件截断**之前**——而懒加载历史早已应用了该截断。此前上限作用于未
  过滤的按 mtime 排序的列表，因此在一个满是较新截图的线程里说“分析我之前上传的
  那些 PDF”会把 PDF 推进 `omitted_summary`，让智能体没有路径可交给 `read_file`；
  现在 `total_count`、`truncated` 与 `omitted_summary` 描述的是过滤后的集合。
  省略两个参数会保持当前行为，两个过滤器以 AND 组合，空值或无效值视为不过滤，
  过滤后无匹配会返回 `No uploaded files matched the given filters.`。

#### 记忆
- **记忆：** 记忆合并（consolidation）合成碎片化的事实，并通过 LLM 为每条事实分
  配的 `expected_valid_days` / `staleFactsToExtend` 进行过期审查，剪除静默过期的
  事实。(、、)
- **记忆：** 保证注入纠正事实（并优雅降级），使用户的纠正始终能触达模型。
- **记忆：** 增量式按智能体作用域的 Markdown 事实存储，按智能体隔离事实，且更新
  单条事实时无需重写或重建整个集合的索引。

- **记忆：** 内置 FTS5/BM25 检索适配器，无需外部服务即可对已存记忆全文搜索。
- **记忆：** 新增可插拔后端：通过 HTTP 接入 OpenViking 与 mem0，以及作为用户模型
  记忆 provider 的 Honcho。(、、)
- **记忆：** 混合事实淘汰策略综合多种信号，决定容量满时应丢弃哪些事实。

#### 技能
- **skills：** 内置的图像生成技能现在可以使用兼容 OpenAI 的 Images API
  进行生成与参考图编辑，端点、模型、尺寸与输出格式均可配置。

- **技能：** 原生 SkillScan（阶段一）在加载时静态分析技能包；`describe_skill` 支
  持延迟发现，模型按需获取技能 schema，而非一开始就加载全部技能。
- **技能：** 按用户的自定义技能隔离，并配合沙箱挂载。
- **技能：** 可直接从“技能”设置页安装本地 `.skill` archive，并复用现有的按用户
  installer 和安全扫描。

- **skills：** 可以从设置页导出自定义技能，包括已禁用的那些，因此备份、在多
  个安装之间搬迁或发给协作者的，都是实际安装的版本，而非原始上传的版本。
  双语预览会列出包大小、分页的文件路径、声明的依赖要求与可操作的阻塞项，
  两个新增的仅管理员 manifest 与 download 端点会将该预览
  绑定到一个修订摘要——期间被改动的包会返回 `409`，而不是给出
  过期的 ZIP。支持文件、空目录与规范化后的可执行权限能在往返中保留，
  而链接、特殊文件、不可移植的路径、嵌套的技能根与可执行二进制会被拒绝。
  导出复制的是原始保存的文件，不是脱敏步骤：它既不扫描密钥，也不
  运行技能脚本，因此凭据与账号设置仍需单独配置。

#### 模型与集成
- **社区工具：** 新增网络检索 / 抓取引擎——GroundRoute、Crawl4AI（`web_fetch`）与
  fastCRW provider——并新增 Browserless `web_capture` 截图工具和 Brave `image_search`
  。(、、、、)
- **MCP：** MCP 工具调用支持按 server 的 `tool_call_timeout`，并提供路由提示引导
  模型选用正确的 server。
- **MCP：** 新增官方 OpenViking `/mcp` 示例，通过 OmniHarness 通用 MCP 客户端暴露其
  原生工具集。
- **社区工具：** Lark / 飞书 CLI 集成打包了运行时安装、官方 `lark-*` 技能包与交
  互式授权流程，使该集成不再依赖手动环境配置。
- **ACP：** 支持 MiniMax Code (`mcode acp`) 作为原生外部编码智能体；ACP thought
  chunk 不再拼接进工具结果。
- **社区工具：** 新增 Serply（支持 news 与 scholar 垂直搜索）和腾讯云 WSA 网络
  搜索 provider，并为 DDGS、Brave、Tavily 与 SearXNG 提供统一的原生时间范围过滤
  （日/周/月/年）。(、、)
- **社区工具：** 新增 Sofya `web_search` 与 `web_fetch` provider——搜索结果直接
  携带每个页面的内容，并按结果设上限，使默认搜索保持内联。
- **知识库：** 新增可选的只读 LightRAG 检索，作为同一 `knowledge` 组的另一个
  `knowledge_search(query)` provider——运营方通过配置哪个条目来选择 RAGFlow 或
  LightRAG。它调用 LightRAG 的结构化 `/query/data` endpoint（不做 LLM 生成），将
  排序后的 chunk 格式化为带引用编号的文本，可选的 `X-API-Key` 在所有模型可见路径
  中脱敏，服务端错误消息会映射为可操作的工具错误。

- **models：**有界并发并不限制请求速率：多个并发 run 仍可能耗尽某个 provider
  的每分钟请求配额，而分发前没有任何机制来对需求限速，因此 429 才是出错的第一
  信号。新增可选的 `models[].request_admission` 配置块，通过进程本地的队列放行
  模型调用，接受 `requests_per_minute`（必填）、可选的 `group`（默认为模型配置
  名）、`max_wait_seconds`（默认 `300`）与 `max_queue_size`（默认 `256`）；在
   60 RPM 下放行至少间隔一秒，而空闲期不会积累突发额度。同一个有界 FIFO 由同步
  调用方、独立的 asyncio 事件循环以及显式组内的每个模型实例共享，它们的策略必
  须一致——冲突的设置会在构造时失败并需要重启。取消与超时会丢弃一个等待者而不消
  耗一次放行，队列已满则会在分发前失败。该限制器通过 LangChain 的
   `BaseChatModel` 钩子挂载，因此智能体模型、invoke 与 stream 路径以及工厂创建
  的辅助模型都在覆盖范围内；工厂会把策略从 provider 参数中剥离，并把暴露给
   SDK 的 `max_retries` 设为零，使重试无法悄悄绕过钩子——现有的智能体中间件重试
  会重新进入放行队列，而非中间件调用方则会失去 SDK 重试。预算按进程计算，因此
  运维方必须把账户配额在 worker、副本与其他客户端之间划分；限制器统计的是请求
  而非 token，未配置的模型行为与之前完全一致。

#### MCP
- **MCP：** 新增持久任务运行时：长时工具任务通过持久 driver 跨 Gateway 重启继续，
  进度与完成通知显示在聊天 UI 中。(、、)
- **MCP：** 共享 MCP server 可注入按用户区分的凭据；未映射用户默认拒绝，存储的
  凭据在 Gateway API 响应中脱敏。
- **MCP：** “设置 > 工具”现在可以通过定向 Gateway endpoint 新增、编辑和删除 MCP
  server；复制粘贴 JSON 的工作流会保留高级字段和已脱敏的 secret placeholder。
- **mcp：**`extensions_config.example.json` 中新增一个可选的
   `parallel-search` server 条目（`https://search.parallel.ai/mcp`，HTTP，默认
  无认证），默认禁用；启用后会暴露 `parallel-search_web_search` 与
   `parallel-search_web_fetch`，并文档化可选的 Bearer 认证。

- **MCP：** `extensions_config.example.json` 新增可选的 `parallel-search` server
  条目（`https://search.parallel.ai/mcp`，HTTP，默认无鉴权），默认禁用；启用后会
  暴露 `parallel-search_web_search` 与 `parallel-search_web_fetch`，并文档化可选
  的 Bearer 认证。
- **渠道：** 对同一会话的密集消息进行排队，并在批次间保留话题卡片预览。
- **渠道：** 钉钉入站消息支持文件与图片附件。 渠道连接器及配套前端体验。
- **渠道：** IM 命令 `/agent list` 与 `/agent use <name>` 允许会话切换到 owner 的
  自定义智能体：选择会持久化到会话元数据（重启后恢复）并优先于过期的渠道默认值，
  IM 创建的会话在 Web UI 打开时路由到同一智能体；同时 `/agent` 在斜杠技能解析器
  、前端与 TUI 中保留，避免任何技能遮蔽该命令。
- **护栏：** 已认证的运行时上下文在 `GuardrailRequest` 中暴露，安全干预以 run 事
  件的形式持久化。
- **认证：** “保持登录”选项，配合统一的会话 cookie 策略（HTTPS 下使用持久化 `Secure`
  cookie，公网 HTTP 下使用会话 cookie）。
- **鉴权：** 内置 RBAC 鉴权 provider 与统一工厂，并在装配期（模型可见前移除工具
  ）与运行期（拒绝被禁用的调用）双重强制执行工具鉴权。

- **鉴权：** Gateway 路由权限改由已配置的 `AuthorizationProvider` 推导，不再使用
  固定表。
- **鉴权：** 模型权限会在 Gateway 路由和智能体运行时双重执行，获取沙箱时还会校验
  `sandbox:execute`。
- **鉴权：** `GET /auth/me` 现在返回调用方的生效路由权限（the RFC 阶段 4），直接
  读取认证中间件在每个已认证请求上标记的 `AuthContext`——不产生额外的 provider
  评估——使前端能隐藏调用方角色无法执行的操作。

#### 沙箱与 provisioner
- **沙箱：** 新增 E2B 与 BoxLite（micro-VM）沙箱 provider；BoxLite 自带预热池。(
  、、)
- **provisioner：** ClusterIP Service 与按技能作用域的 PVC 挂载，并支持配置沙箱
  容器端口。

- **沙箱：** 新增云沙箱 provider：Tenki 与 OpenSandbox。
- **沙箱：** K8s provisioner 模式新增可选的 lark-cli 凭据 broker sidecar，将 Lark
  应用密钥与 OAuth token 移出沙箱文件系统；沙箱只看到转发命令的 shim。默认关闭。
- **沙箱：** E2B 沙箱创建后会携带结构化的 `MountUploadResult`（`truncated`、
  `reason`、上传统计），并在同进程内的 warm-pool 回收后保留——挂载上传因资源限制
  被截断的情况可以在代码中观察，而非只出现在 Gateway 日志。

#### 扩展与插件
- **扩展：** 新增 out-of-tree Python 扩展系统，可贡献中间件、任务生命周期与系统模型
  observer、Gateway 服务和 HTTP 路由，并用 `omniharness extensions` 管理。(、、)
- **扩展：** 扩展可观察消息来源、中间件策略、智能体装配指纹、上下文压缩、护栏决策
  和工具的 MCP 来源。`omniharness-extension-api` 升至 0.2.0，0.1 扩展会在启动时被拒绝。

- **extensions：**`omniharness extensions upgrade SOURCE`（也以
   `make extension-upgrade SOURCE=...` 暴露）会替换一个受管理的本地快照，或为
  已在 `extensions` 组中的依赖重新固定版本，并沿用现有的 `plugins:` 记录，使其
  私有的 `config` 与 `required` 得以保留。迁移到更新的固定版本此前意味着先
   `remove` 再 `install`，而 `remove` 会删除整条记录——包括密钥——而已经快照过的
  本地目录若不手工编辑受管理的副本根本无法重新安装。普通的 `install` 没有变化，
  仍会拒绝已存在的本地快照；升级未安装的来源会以安装提示的方式失败关闭；失败的
  升级会恢复先前的快照，即使并发的 `pyproject.toml` / `uv.lock` 编辑阻止了依赖
  文件回滚。

#### 持久化
- **持久化：** 可通过 `postgres_schema` 选择自定义 PostgreSQL schema；ORM、LangGraph
  checkpointer 与 store 表均创建在其中，启动时自动创建。

#### 前端
- **前端：** 支持对助手回合进行分支，以及针对引用追问的侧边对话。
- **前端：** 支持重新生成最新回答。
- **前端：** 引用来源证据面板、智能体 run 的工作区变更评审，以及可视化的 `ask_clarification`
  卡片。(、、)
- **前端：** 语音输入、方向键回溯 prompt 历史、输入框内容润色，以及“（思考了 N
  秒）”思考时长标签。(、、、)
- **前端：** 用 `agents_api` 特性开关控制智能体 UI 的可见性，并在后端与 UI 中持
  久化 AI 回合时长。
- **前端：** 将斜杠技能（slash-skill）激活渲染为内联标签（chip）。
- **前端：** 支持置顶最近会话。

- **前端：** 实时显示上下文窗口使用量。
- **前端：** 澄清卡片待处理时仍可输入并发送回复。
- **Artifact：** 可在 artifact 面板中内联编辑文本 artifact。
- **Artifact：** Markdown artifact 可在新窗口 reader 中以渲染形式打开（并提供
  “查看源文件”和“下载”fallback）；一次 run 中展示的所有文件也可根据该 run 的
  投递回执打包下载为 zip。
- **前端：** 自定义智能体聊天支持 Browser Live。
- **前端：** 定时任务可复制为可编辑草稿，保留配置但不带 run 历史。
- **前端：** 支持归档与恢复会话：侧边栏 Archive 操作配 Undo toast、搜索栏上方的
  “最近会话 / 已归档”标签页，以及按会话的恢复控件；SQL 与 Memory 存储在分页前
  应用归档过滤，同时保留消息、文件、链接、置顶状态与当前 URL。
- **Artifact：** 已完成的 CSV/TSV artifact 以有界表格预览（最多 200 行 × 50 列，
  每页 50 行，吸顶表头，可选首行表头），解析在后台线程进行、复用现有 1 MiB range
  加载器——字面字符串、前导零与多行带引号单元格都得以保留，长单元格可在可复制的
  对话框中打开，源码视图一键切换。

- **projects：** 项目 MVP 第二阶段让项目真正发挥作用，而不只是给文件夹起个名
  字。项目说明此前会被存储、可以编辑，却没有任何东西读取；现在它会在每个成员
  线程的 run 中作为有界的 user 角色 `<project>` 块送达模型，且只出现在该 run
  的请求里，永远不会进入系统提示词或持久化历史；重命名会在下一次 run 生效；
  超长文本会在写入时被拒绝，而不是被截断。每个项目的文档架新增 `Documents`
  标签页（上传、带来源信息的列表、预览、下载、移入回收站、按内容哈希去重），
  智能体可按需通过 `list_project_documents` / `read_project_document` 读取
  ——这些工具只在项目 run 中注册，且仅支持文本。此外还支持双向提升：
  `Save to project` 把任意线程文件连同来源信息复制到文档架，
  `Attach to thread` 则通过常规上传管道把文档架中的文档重新摄入一次对话。只
  读的对话文件视图会聚合各成员线程的上传文件与产物，项目删除也终于有了回收站
  这一层级。

- **frontend：** 对话现在可以从输入框中引用。附件按钮旁边新增了
  `Reference a conversation` 按钮，仅当 `/api/features` 报告该能力时才渲染，
  并会打开一个选择器，其列表与侧边栏使用的最近会话列表相同——从不会提供当前
  对话，并以报告的 `max_references`（目前为 3）为上限，超过上限的行会被禁用，
  而已选中的行仍可点击以移除。被附加的对话在输入框中显示为可移除的 chip，在
  对话记录中则是指回来源的只读 chip。引用是按消息生效的：不随草稿保存，发送
  或切换线程时清除，重新生成或编辑某个回合时会不带引用运行，除非重新附加。

#### 可观测性与工具
- **可观测性：** trace-id 关联与增强日志，以及通过 Monocle 实现的智能体可观测性
  。
- **工具：** 类 Hermes 的终端工作台（`omniharness` CLI，基于 `OmniHarnessClient`），以
  及脱敏的社区支持包（support-bundle）生成器。
- **安装向导：** 安装向导现在会询问 OpenAI 兼容的 gateway 模型是否支持 thinking
  ，并新增火山引擎 Coding Plan 快速安装路径。
- **TUI：** `clear` 命令。
- **网关：** 新增 `GET /health/ready` 就绪探针，执行有界的数据库 `SELECT 1`，
  数据库不可达时返回 503（memory 后端返回 200 `not_configured`）；`/health` 仍为
  纯存活探针，生产 compose 的健康检查也改用就绪探针。

- **client：** 上下文压缩把结果存放在 `messages` 之外的
  `ThreadState.summary_text` 中，但嵌入式客户端的 `values` 事件只选择了
  `title`、`messages` 与 `artifacts`——因此 Gateway 之外的消费方（例如基准
  测试运行器）无法通过公开事件流观察到该摘要。现在每个嵌入式 `values` 事件都
  会携带 `summary_text`，缺失时为 `None`，并把更新、重复与清除作为状态快照转
  发。消息序列化、AI-delta 去重、工具产物与用量记账均未改变，也没有暴露任何
  checkpoint 内部实现。初始快照本身就可能包含恢复出来的摘要，因此仅凭取值变
  化并不能断定发生了一次压缩事件。
- **技能：** 处于激活态的限制型技能若要委派给子智能体，必须在 `allowed-tools` 中
  显式声明 `task`。只读发现基础设施（`tool_search` 与 `describe_skill`）仍可用，
  但无法为被禁用的业务工具授予 schema 可见性或执行权限。
- **记忆：** 新增 `memory.mode`（`middleware` | `tool`）；`tool` 模式会注册供模
  型直接调用的记忆工具（`memory_search`/`add`/`update`/`delete`），取代被动的逐
  回合摘要。`manager_class` 解析改为快速失败（未知后端时抛出 `ValueError`，而非
  静默回退）。
- **沙箱：** 宿主机到虚拟机的输出脱敏正则现在统一归属，消除重复的模式编译。

- **记忆：** OpenViking 后端改用官方适配器；旧 trusted-mode 的 `auth_mode`/`account`
  字段会被拒绝，改用绑定凭据的 USER API key。
- **智能体：** 子智能体委派改按净收益路由；除非并行延迟、专长能力或上下文隔离明确
  有益，否则主智能体默认直接执行。
- **持久化：** 修复静默跳过了 run-change clock schema 的数据库。`0023_run_change_seq` 被插到了
  已经发布的 `0023_user_preferences` 修订之前，因此在该修订点（或之后）盖章的数据库会把它当作
  已应用的祖先而从不执行——`run_change_clock` 表与 `runs.change_seq` 列永久缺失，第一次删除会话
  （任何 run-store change-clock 递增）就会以 `no such table: run_change_clock` 失败。新增的
  `0025_repair_run_change_seq` 修订在升级时重新应用同一份带守卫的 DDL，在形态健康的库上空操作。
  `RunChangeClockRow` 与 `UserPreferenceRow` 也已注册进 ORM 模型注册表，`create_all` 与
  autogenerate 通过显式导入（而非模块副作用）看到所有表。
- **模型：** Claude Code 凭据加载器现在能防护格式错误的 `claudeAiOauth` 容器。
  `~/.claude/.credentials.json` 可能是合法 JSON 但 `claudeAiOauth` 的值不是对象——部分导出遗留的
  `null`、原始字符串、数组或数字——此前提取器会对它调用 `.get`，从
  `ClaudeChatModel.model_post_init` 抛出 `AttributeError` 并中断模型构造，与该模块文档声明的
  "优雅降级"行为相反（同属模型加载器的 Codex 一侧早已对同样形态做了防护）。现在顶层 payload
  或 `claudeAiOauth` 值不是对象时，会以 debug 级别记录并视为"此来源没有凭据"，加载流程继续尝试
  下一个来源，所有来源都不可用时最终返回 `None`。
- **setup：** BOM 前缀配置中的自定义 sandbox 镜像现在会生效。`setup-sandbox.sh` 用 `^sandbox:`
  去匹配仍带着 UTF-8 BOM 的首行，匹配失败后静默选择并拉取默认镜像，而运行时 YAML 加载器其实
  接受同一份配置。脚本现在在进入镜像选择流程前剥离首行开头的 UTF-8 BOM，未引入新的运行时依赖。
- **模型：** Codex 的无效工具调用现在与其工具结果成对重放。Codex 模型发出 `arguments` 不是
  合法 JSON 的 `function_call` 时并不会让本轮失败：调用被记入 `invalid_tool_calls`，由
  `DanglingToolCallMiddleware` 以占位 `ToolMessage` 应答，模型看到的是可恢复的工具错误。但
  Codex Responses 序列化器只对有效的 `tool_calls` 生成输入项，占位结果作为
  `function_call_output` 到达 provider 时，同一请求里没有与之配对的 `function_call`，而
  Responses API 要求二者成对——中间件本要恢复的那个场景反而以 provider 报错收场，而不是重试。
  Chat Completions 系 provider 经 LangChain 转换器本就会这样重放无效调用，OpenAI 兼容路径的
  同类失败也已在中间件层修复；现在 Codex 请求同样把 `invalid_tool_calls` 作为 `function_call`
  输入项与有效调用并列重放。有效调用路径、解析侧与中间件均未改动。
- **middleware：** 循环检测不再中断正在分段读取文件的智能体。`read_file` 调用
  此前按 200 行的分桶建键，因此短于一个分桶的读取都会塌缩到相邻分桶上：连续
  五次 40 行的读取哈希完全相同，会触发硬停止，使 run 以强制最终答复和
  `stop_reason=loop_capped` 结束——而这正是 `read_file` 自身的截断提示
  要求模型去做的分段读取。现在的键使用精确的行区间，省略的 `end_line` 保持
  "读到末行"的开放语义，不带范围的读取与显式 `start_line=1` 仍共用同一个键。
  重复同一区间仍会在原有阈值被拦下，边界抖动的读取循环仍由按工具类型计数的
  频率层覆盖。

- **调度器：** 在 SQLite 上同样强制执行全局 `max_concurrent_runs`，此前该上限只在 Postgres 上成立。
  认领排队中的 occurrence 时，会先统计正在执行的行，再把其中一行提升为 `launching`，Postgres 用
  advisory lock 将这两步串行化。而 SQLite 的 deferred 事务直到那条提升用的 UPDATE 才占用 writer，
  因此在不同行上并发认领的调用方——手动触发与轮询重叠，或第二个 Gateway 进程共用同一个数据库
  文件——会读到同一个过期计数并全部通过预算检查，导致实际运行数超过配置的上限。
- **中间件：** 移除工具调用的守卫不再导致 Claude 或 OpenAI Responses 线程之后的每一轮都失败。
  token 预算与循环检测的硬停止、subagent 数量限制的截断以及安全终止抑制只清空了 `tool_calls`，
  却把 provider 自身的工具调用块留在消息 content 中。Anthropic 与 Responses API 会重新发送这些块，
  导致下一次请求带着没有结果的工具调用而被 provider 拒绝；写入 checkpoint 的硬停止消息还会让之后
  每条新消息都失败。现在所有守卫都通过同一个共享 helper 删除对应的 content 块，该 helper 也会保留
  clarification 所保留的 Responses 调用。
- **沙箱：** 当输出用 `:` 连接主机路径（如 `$PATH`、`$PYTHONPATH`）时，主机路径不再暴露给模型。
  匹配的路径会一直延伸到列表末尾，导致同一根目录下之后的条目都未被遮蔽；多余的遮蔽轮次每次
  恰好补回一个条目，因此短列表掩盖了这一泄露。现在遮蔽时匹配的路径在 `:` 处结束。
  挂载目录内指向所有挂载之外的符号链接，在命令输出和 `glob` 结果中改为显示其挂载路径，而不是目标的主机路径。
- **模型：** 通过 `CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR` 传递 Claude Code OAuth
  token 时，第一个之后的 Claude 模型不再丢失凭据。每个 `ClaudeChatModel` 实例都会重新加载凭据，
  但文件描述符只能读取一次，导致标题、摘要、subagent 模型以及之后的每次运行都没有凭据，并以
  `TypeError: Could not resolve authentication method` 失败。现在 token 在每个进程中只读取一次并复用。
- **运行时：** 带 `Idempotency-Key` 的 run 重试在 SQL run 存储上不再返回 500。HTTP
  准入不会传入 `user_id`，SQL 存储会把请求用户写入该行，但进程内的 run 记录仍为
  `None`。同一 key 的重试若落到另一个 Gateway worker，或在已完成的 run 被清理后回到
  同一 worker，就会比较两边的拥有者，把自己的 run 误判为其他用户的并抛错。同一不一致
  还让 HTTP run 被按拥有者过滤的历史读取漏掉，并跳过了 MCP `background_tasks` 投影，
  因此这类 run 的 `values` 事件现在会包含 `background_tasks`。`RunManager` 现在按
  SQL 存储的方式用请求用户补全缺省的拥有者，各存储记录的拥有者保持一致。
- **Skills：** 切换 skill 启用状态时不再把解析后的密钥写入 `extensions_config.json`。
  此前 Gateway 的 skill 开关与 `OmniHarnessClient.update_skill` 通过
  `ExtensionsConfig.from_file()` 读取配置（该方法会把所有 `$VAR` 值替换为环境变量的
  实际值），再把模型整体写回，于是 `"$GITHUB_TOKEN"` 引用会被持久化为明文令牌，未设置
  的变量则被永久写成 `""`。`OmniHarnessClient.update_mcp_config` 对 `mcpServers` 以外的
  所有键也存在同样问题。现在这些写入方直接修改磁盘上的原始 JSON，并按运行时的加载方式
  校验候选配置后再写入，占位符与手写结构保持不变；MCP 路由也复用同一个原始读取函数。
  已被旧版本改写过的文件仍保留明文值，请恢复 `$VAR` 引用并轮换已暴露的凭据。
- **Gateway：** `disable_clarification` 与 `github_token` 现在与 `non_interactive`
  一样，仅对内部认证的调用方生效。此前这两个键无论调用方身份都会从 `body.context`
  透传，而且不会从被逐字复制进 run config 的自由格式 `body.config` 中清除，因此任何
  会话或 PAT 调用方都能设置它们。其中 `disable_clarification` 影响更大：
  `ClarificationMiddleware` 会把包括 `risk_confirmation` 在内的所有澄清请求替换为
  "无需确认，继续执行"，`SandboxMiddleware` 也把它与 `non_interactive` 视作同一个
  非交互信号。`github_token` 则会进入 `runtime.context`，被 bash 工具导出为
  `GH_TOKEN`/`GITHUB_TOKEN`；若经由 `body.config['configurable']` 夹带，还会被写入
  checkpoint 存储。定时任务、IM 渠道与 GitHub webhook 渠道走内部请求通道，不受影响。
- **网关：** 不再把调用方提供的 `omniharness_trace_id` 持久化到 run 记录上。`body.metadata`
  会同时到达运行中的 run config（run worker 会重新盖章）和 runs API 原样回显的 run 记录，
  此前只覆盖了前者，因此客户端可以让 run 最持久的展示面与同一请求的 `X-Trace-Id` 及日志行
  互相矛盾。现在 id 只在信任边界处盖章一次，`config.context` 也以同样方式封堵，且会话自身
  的 metadata 不再被写入"创建它的那个 run"的 run 作用域 id。
- **网关：** 未处理异常的 500 响应现在也携带 `X-Trace-Id`。Starlette 的
  `ServerErrorMiddleware` 通过所有用户中间件之外的原始 send 发出这类响应，因此服务器 bug
  的 500——最需要关联 id 的那个响应——成了唯一不带 id 的响应。`TraceMiddleware` 现在会在
  重新抛出异常前自行发送一个携带该 header 的 500；服务端的异常日志不受影响，流中途的失败
  也照旧传播。这一回退响应在 `CORSMiddleware` 之外发出、保持 CORS 不可读，因此跨域拆分的
  浏览器客户端在这个响应上读不到 id——与它所替换的 `ServerErrorMiddleware` 500 一致。
- **运行时：** 会话元数据现在仅在 run 通过启动屏障后才切换为 `running`，待取消的
  run 不再短暂呈现 `running` 状态；worker 启动期间客户端可能观察到先前的会话状态
  。
- **运行时：** 通过原子化、感知租约的接管（takeover）claim 重新检查孤儿候选 run
  ，使扫描后的成功心跳仍保持 run 活跃，且仅有一个 reconciler 上报恢复。
- **技能：** `allowed-tools` 只作用于斜杠激活或实际加载的主智能体技能，避免被动
  启用的技能与评测 fixture 从每个 run 中移除 MCP、网络、文件与委派工具。(
  、、)
- **模型：** 在所有 `BaseChatOpenAI` 子类（`VllmChatModel`、`MindIEChatModel`、`PatchedChatMiMo`
  、`PatchedChatStepFun`、`PatchedChatMiniMax`）上生效 `api_base`，而不只是 `ChatOpenAI`
  / `PatchedChatOpenAI`。此前这五个子类会静默丢弃配置的 endpoint，随后以一个含义
  不明的 `unexpected keyword argument 'api_base'` 让每次请求都失败；它们也未被纳
  入未知配置 key 的告警。两者现在都基于 `issubclass(BaseChatOpenAI)` 判断。
- **智能体：** 在 LLM 请求前合并 `SystemMessage`；保证工具运行后仍有可见响应；避
  免在流结束前发起默认的 LLM 标题调用；为省略号预留空间以使本地标题遵守 `max_chars`
  ；并将工具输出尾部前移，使回退截断遵守 `max_chars`。(、、
  、、)
- **智能体：** 动态上下文的日期扫描跳过无日期的提醒；从不含 `config.yaml` 的智能
  体目录加载 `SOUL.md`；`update_agent` 的旧版智能体守卫要求存在 `config.yaml`；
  并拒绝空的 `SOUL.md` 更新。(、、、)
- **中间件：** 为循环检测的工具频次计数器加窗口，避免长 run 误触；阻止标题中间件
  流式输出 token；修复“同内容列表耗尽时位置回退误取无关 todo”的问题；在 `_apply`
  、`before_agent`、`_clear_run_state` 与 `_drain_pending_warnings` 之间持有 token
  预算锁；丢弃孤立的 `ToolMessage` 以免严格型 provider 返回 400；净化非法 tool-call
  参数；并在 dangling 修复中从空的 tool-call 名称与畸形 tool-call id 恢复。(
  、、、、、、、)
- **子智能体：** 继承 `LoopDetectionMiddleware` 与摘要中间件，使工具循环能被打断
  、步骤能被捕获；将回合预算上限以 `MAX_TURNS_REACHED` 暴露并附带部分结果；在累
  加式 `stop_reason` + `token_budget` 上统一护栏上限；压缩前注入持久上下文；保留
  父 checkpoint 命名空间；在 general-purpose 系统 prompt 中禁用 `task` 工具；flush
  失败时重新缓冲子智能体事件以避免丢失步骤；并修复子智能体 `run_id` 为 `None` 时
  丢失 `loop_capped` 停止原因的问题。(、、、、
  、、、、)
- **记忆：** 加固对 null / 空值边界情况的处理——跳过仅含空白的事实；在更新、检索
  与剩余三处原始读取中规整 null 的 `confidence` / `source.confidence`；将显式 `null`
  的 `backend_config` 值视为缺省；修复事实无 id 或事实列表为空时的 `KeyError` /
  `UnboundLocalError`；停止防抖更新队列的忙等（busy-spin）；并在优雅关闭时刷写记
  忆队列以防丢失。(、、、、、、
  、、)
- **运行：** 关闭 run 原子性中的多 worker 归属缺口；在租约续期于截止期前无法确认
  时令本地执行快速失败，并在 peer 接管后对迟到的完成写入加围栏；多 worker 下将 cancel
  降级为租约接管；让 `create_thread` 在插入竞态时仍幂等；从运行时上下文读取 `stop_reason`
  ；并将 run 时长持久化到 checkpoint 以供历史读取。(、、、
  、、、)
- **运行时：** 序列化 SQLite event-store 写入，避免按会话的序列号冲突；在 journal
  中跳过隐藏的人类消息；并去掉 `_merge_stream_text` 中静默丢弃 delta 的行为。(
  、、)
- **网关：** 按真实 `event_type` 关联会话消息反馈；把 artifact 服务、gateway 上
  传与 Discord 渠道中的阻塞文件 IO 移出事件循环；限制上传文件的上下文清单；并实
  时追踪畸形的 Redis 重连 id。(、、、、、)
- **上传：** 在写入前先占位转换后的 Markdown 配套文件名，使同词干（stem）的两个
  可转换上传（或一个可转换上传加一个同词干 `.md` 上传）不再在同一请求内静默互相
  覆盖。`uploads.auto_convert_documents` 开启时，配套 `.md` 会得到唯一名称（如 `a_1.md`
  ）；`POST /threads/{id}/uploads` 与 `OmniHarnessClient.upload_files` 都会在 `markdown_file`
  中返回实际文件名。
- **配置：** 将为 null 的对象型配置节规整为默认值；在 store 与 sync checkpointer
  中遵循统一数据库配置；并让旧版 DB 回填在已存在的表上补建缺失的 `Index` 对象。(
  、、、)
- **模型：** 将 `stream_chunk_timeout` 默认值应用到所有 `BaseChatOpenAI` 子类；
  并为 `ChatOpenAI` 把 `api_base` 规范化为 `base_url`，遇到未知配置 key 时给出告
  警。
- **MCP：** 按 server 隔离工具发现失败；同步 session-pool 单例的生命周期；按配置
  内容 + 路径（而非仅更新的 mtime）失效工具缓存；在加载时校验 MCP 工具名，使延迟
  prompt 保持惰性；并按来源 server 路由工具，而非按名称前缀。(、、、、)
- **技能：** 斜杠技能每个 run 仅激活一次，而非每次模型调用都激活；补齐技能安装安
  全扫描的覆盖缺口；在评审 CI 中识别被完全删除的技能包，并在 SkillScan 中把剩余
  的 `requests` / `httpx` 方法识别为网络出口；在无参 skills prompt 段落复用已解
  析的 app 配置；并支持不重启 Gateway 即可重新加载已挂载技能。(、
  、、、、)
- **沙箱：** 为反向路径翻译与输出脱敏正则加上段边界；在 `read_file` / `str_replace`
  中处理单边行范围与空文件；对齐 AIO bash 工作目录；在 Windows 的反向 resolve 包
  含性检查中使用 `os.sep`；在 bash 命令中规范化 Windows 反斜杠路径；阻止 `glob`
  / `grep` / `ls` 暴露被禁用技能的文件；并在沙箱审计中允许合法的 heredoc 命令。(
  、、、、、、、、)
- **沙箱：** 同步沙箱 provider 单例的生命周期（含并发回归测试），并让 provisioner
  中的 k8s 调用不阻塞事件循环。
- **沙箱：** 将沙箱 artifact 挂载与渠道用户对齐；修复非 root / NFS 主机上的本地
  开发（`make dev`）；停止时回收 macOS 上的 nginx 进程；并修复 Docker 中生产环境
  Postgres 的 UV-extras 检测。(、、、)
- **渠道：** 在解析渠道 provider 配置前先校验 provider；对 GitHub webhook 重投递
  去重，并丢弃冗余的 GitHub review-comment webhook 扇出；把斜杠技能白名单检查限
  定在 run 的 owner 作用域；将飞书文件消息批量到一个会话，并以 bot @mention 前缀
  分发飞书群命令；在 `/connect` 绑定码前接受前导 @mention，且不把裸 `connect` 当
  作绑定命令；阻止飞书创建会话话题并限流卡片更新；让 UI 运行时渠道配置优先于 `config.yaml`
  ；修复 `bot_login` / `mention_login` 仅含空白时 `require_mention` 的门控；防护
  企业微信中为 null 的引用字段；并将入站去重按聊天作用域的工作区建立 key，使 Telegram
  、飞书、微信与钉钉在默认（未绑定）配置下不再因重投递重复执行智能体，遇到瞬时失
  败时释放去重 key 以便重投递仍可恢复。(、、、、
  、、、、、、、、)
- **前端：** 摘要过程中保留消息与持久上下文；流式期间保留 artifact 并稳定 artifact
  路径；解析相对 artifact 图片路径；在 header 下拉中保留已展示的 artifact；保持
  孤立的工具消息可见；工具步骤期间展示助手文本；客户端导航时重置新会话；防止并发
  提交导致流被取消；修复过期 run 的重连与取消处理；修复聊天公式渲染、单波浪线 markdown
  、双重 reasoning 渲染、UTF-16 markdown 二进制分类与 Streamdown 中的 `<memory>`
  标签；让最近会话行整体可点击；上传前校验附件上限并修复消息复制中上传文件元数据
  ；修复移动端工作区与可访问性阻塞、卡片工具消息 bug 以及侧边聊天工具栏 / 面板按
  钮行为；拦截未解析的建议模板占位符；刷新通知权限；仅对已完成回合显示分支操作；
  在自定义智能体聊天中启用重新生成；并为被中断的首回合 run 生成兜底标题。(
  、、、、、、、、、
  、、、、、、、、、
  、、、、、、、、、)
- **TUI：** `/quit` 退出前先中断活动 run。
- **追踪：** 把 Langfuse trace 元数据附加到目标评估器。
- **ThreadData：** 修复 `runtime.context` 为 `None` 时的 `AttributeError`。
- **熔断器：** 修复半开探测不可重试后熔断器卡死的问题。
- **社区工具：** `image_search` 现在返回全分辨率图片 URL。
- **技能：** SkillScan 不再把惰性求值的 PEP 695 类型别名误判为网络出口。

- **追踪：** 从运行时上下文解析 Langfuse trace 的用户。
- **子智能体：** 子智能体上限与 `MIN_SUBAGENT_LIMIT` 保持一致地限幅。
- **MCP：** 按 server 的 OAuth 预热改为失败即软降级，并持久化轮换后的 refresh token
  。
- **认证：** 邮箱账号改为大小写不敏感解析。
- **调度器：** 修复一个调度竞态，该竞态可能为同一个定时任务启动两个 run。
- **渠道：** 在转换为 mrkdwn 前先转义 Slack 保留字符。
- **渠道：** 丢弃不携带会话身份的入站钉钉消息。
- **记忆：** 合并后的事实从其来源继承 `expected_valid_days`。
- **Postgres：** 用 `pool_recycle` 与 `command_timeout` 加固异步引擎，消除陈旧连
  接导致的 504。
- **社区工具：** 在 `web_fetch`（Browserless）中暴露目标页的错误状态。
- **沙箱：** `str_replace` 在任意文件上遇到空 `old_str` 时改为无操作。
- **沙箱：** 限制 E2B 输出同步的资源占用。
- **沙箱：** 本地 AIO 流量绕过代理。
- **流式：** 保持大文件生成过程的响应性。
- **流式：** 对回放历史中的缺口发出信号。
- **运行时：** 模型调用后移除临时的图片上下文。
- **运行时：** 拒绝不支持的 run 选项与流模式。
- **运行时：** 序列化 checkpoint 写入与活动 run、线性化 delta 模式的 checkpoint
  恢复，并接受 SDK 默认的 `stream_resumable=false`，以避免恢复竞态。(、
  、)
- **checkpoint：** 解包对空 channel 的 `Overwrite` 首次写入。
- **网关：** 当 header 已设置时，优先使用 `X-Trace-Id` 而非 `metadata.omniharness_trace_id`
  。
- **网关：** 分支历史补种的 run id 按继承的回合作用域划分。
- **前端：** 工作区变更评审中，把“符号链接替换文件”与“删除”区分开。
- **前端：** 对 artifact URL 的路径段进行编码。
- **前端：** 在分支会话中保留重新生成状态。
- **前端：** 剥离并解析 `<current_uploads>` 上传上下文标签。
- **前端：** 刷新后保持已完成子任务卡片的稳定。
- **前端：** 恢复 artifact 与侧边面板的可调整大小。
- **内容安全：** 回填空的内容过滤响应，避免污染会话。
- **Artifact：** 显式加载完整文件时限定在来源会话内，使其他会话中同路径 artifact
  仍保持 1 MiB 预览。
- **沙箱：** `SandboxAuditMiddleware` 改为按命令替换所处位置判断风险：普通输出捕获
  不再误拦，而命令位置、解释器代码参数、`eval`/`source`、process substitution 与
  here-string 中执行下载内容仍会阻止；heredoc 正文继续按数据处理。
- **MCP：** 设置页的启停只校验目标 server；允许禁用已不合规目标但拒绝重新启用，
  支持规范中的 `transport` 别名、展示后端校验详情，并以原子方式更新共享配置。
- **MCP：** 用按 server 的 `session_init_timeout`（默认 60 秒，`null` 可关闭）限制工具
  发现与持久 stdio session 初始化，避免挂起 server 阻塞智能体装配或 Gateway 事件循环。
- **前端：** 回合仍在流式输出时隐藏旧的后续建议。
- **前端：** 修复流式渲染抖动：不重复播放逐字动画、稳定步骤文本和消息顺序，并保持
  reasoning 位于答案上方。(、、、)
- **前端：** 聊天路由中的 thread id 现在会编码，特殊字符不再破坏导航。
- **前端：** 本地化会话导出失败消息。
- **前端：** 每个 run 只渲染一张工作区变更卡片。
- **网关：** 拒绝 API 请求中的非正读取上限。
- **网关：** 统一各 API 路由的 thread id 校验。
- **网关：** 向跨域客户端暴露 run 元数据响应 header，使分离部署的前端能及时获知新 run id。
- **网关：** 从稳定 checkpoint 执行“编辑并重跑”，确保编辑后的 prompt 真正运行，
  并在重跑后保留手动标题。
- **运行时：** 可从任意存活 Gateway worker 取消 run，停止按钮不再依赖请求路由。
- **运行时：** 重新生成响应时保留当前标题，并支持最近一次尚未写入 checkpoint 的中断响应。
- **智能体：** 将 404 等 `web_fetch` 错误页识别为错误证据，使重试和停滞保护能够响应。
- **子智能体：** 委派执行使用隔离 callback 与惰性技能激活，修复跨事件循环错误及被动
  技能移除 `write_file` 等基础工具的问题。
- **沙箱：** 安全协调 E2B 沙箱：选择首个健康候选、按用户与会话采纳规范实例、延后
  处理 peer 的活动副本，并在宽限期后回收孤儿。
- **沙箱：** `grep` 支持搜索单个文件。
- **技能：** 斜杠调用可从托管 integrations 根目录激活集成技能。
- **MCP：** 忽略过大的类路径文本。
- **记忆：** 在创建临界区拒绝重复事实，按条目边界截断 mem0 注入上下文，并阻止
  “仅检查”等任务级指令进入长期记忆。(、、)
- **调度器：** 启动成功后的记账若失败，仍保留 run slot 与 run id，防止后续重复启动。
- **配置：** 为异步 ORM engine 规范化 `postgres://` 短 scheme。
- **Browserless：** 接受 `timeout` 配置键并加固类型转换。
- **运行时：** JSONL 批量事件按 run 分组写入，避免跨多个 run 的批次全落入首个文件。
- **运行时：** 恢复独立 LangGraph Studio 兼容：图入口、文件式 app、系统助手发现与
  `langgraph dev` 工作流重新可用。
- **网关：** 只在 `/messages/page` 中把 `turn_duration` 标到 run 的最后一条 AI 消息。
- **网关：** MCP task worker 停止时以 HTTP 503 拒绝取消请求。
- **中间件：** 修复动态上下文目标、列表字符串净化、重复无效工具占位符，以及摘要误
  压缩当前用户请求等四个上下文问题。(、、、)
- **中间件：** 恢复向模型说明 `write_todos` 工具的系统 prompt 注入。
- **工具：** 使用运行时用户解析待展示文件，避免有效 artifact 被误判在 outputs 外。
- **子智能体：** 每个后台执行使用服务端 execution ID，复用 provider tool-call ID 的
  并发 run 不再覆盖、轮询或取消彼此状态。
- **MCP：** 收到 task snapshot 时拒绝非有限 `poll_after_seconds`。
- **runtime：** 缓慢或卡死的 stdio MCP server 不再拖住整个 Gateway。智能体装配
  此前在事件循环上同步装配 MCP 工具，因此等待一次进行中的 MCP
  初始化会阻塞所有其他请求的 SSE 投递、run 取消与定时器，
  而不只是阻塞那个正在等待自己工具的调用方。
  现在每个异步入口点都会把工具装配派发到工作线程：`task_tool` 中的子智能
  体生成路径、用于持久批处理的 `SubagentBatchService._execute_item`、
  `run_agent` 的 agent 工厂（它覆盖了 lead-agent 装配中两处
  `get_available_tools` 调用点），以及 checkpoint state-accessor 的构建——
  其冷缓存读取现在在工作线程中承担 MCP 初始化的等待，而不再停住事件循环。这四
  处卸载共用同一个有界专用池（`utils/assembly_io.py` 中的
  `run_assembly()`，8 个 worker，可用 `OMNI_HARNESS_ASSEMBLY_WORKERS`
  覆盖），而非事件循环的默认执行器，因此一个为等待完整 MCP 超时而停住的
  worker 无法把其他所有 `to_thread`
  调用方排到自己身后；contextvars
  会跨这次跳转复制，扩展的 build-context 快照因此仍能传播，
  而当等待中的装配数超过 worker 数时会以限流的警告记录下来。由于装配
  现在可能被长时间挂起，持久批处理会在启动前立即重新检查其条目的持久状态，
  因此在装配期间被取消的批处理不会再发起模型调用。

- **agents：** `LoopDetectionMiddleware` 不再把一个轮次的预算消耗在另一个轮次的
  合法工作上。它此前只用 `thread_id` 界定相同调用哈希与按工具频率窗口
  的作用域，因此一个跨轮次复用的已编译智能体——`OmniHarnessClient`
  会保留图并为每个轮次分配新的 `run_id`——
  会把先前轮次的普通调用计入后一个轮次的限额，在默认的相同调用阈值下，
  第三个独立轮次就产生一次虚假的循环警告，第五个轮次则被剥掉一次合法的工具
  调用。状态现在按 `(thread_id, run_id)` 界定作用域，同一个 run 内多次进入图
  时证据仍会累积（包括隐藏的 goal 延续），并发兄弟 run 则各自拥有独立的警
  告队列。LRU 淘汰会丢弃整个 run 作用域，`reset(thread_id)` 仍会清除该线程
  拥有的每个作用域，阈值以及警告/硬停止行为均未改变。

- **middleware：** 人工输入卡片的回复现在会被识别为用户的当前请求。
  卡片答案以隐藏的 `HumanMessage` 形式到达，其中携带有效的
  `human_input_response`，而轮次检测辅助函数使用的是
  `is_real_user_message`，它会无差别地拒绝每条隐藏消息，没有任何豁免——
  因此由卡片回复启动的 run 会把较早的可见请求当作"当前"请求，而答案本身
  却被视为框架注入。在摘要中，当前请求的挽救逻辑因此锁在了那条过期的消息
  上：压缩之后模型看到的是原封不动的原始请求，
  而用户的地区与年份约束只存在于摘要里。在 `McpRoutingMiddleware`
  中，只出现在卡片答案里的路由关键词匹配不到任何东西，
  于是被推迟的 MCP 工具永远不会被自动提升，模型只能手动调用
  `tool_search`——同样的答案若以可见消息发送就能完成提升，
  可见行为只取决于答案的传输方式。现在两处都改用
  `is_genuine_user_message`，它跳过隐藏消息，除非其携带有效的
  `human_input_response`；没有该字段的隐藏消息仍会被跳过。

- **goal：** 一个已达到 token 上限的 run 所满足的目标，
  其后不再跟着一次毫无意义的延续。既然延续现在共享该 run 的 token 预算，
  硬停止后排入队列的延续只会做一次模型调用，随后其工具调用便被剥离，
  因此无法取得任何进展——然而 worker 仍然会把它排入队列，
  每次都付出一次评估器调用和一次模型调用的代价，
  直到延续上限或无进展上限终止该目标为止。`run_agent` 现在会把 run 的
  `stop_reason` 传入目标延续的准备流程，当它是 `token_capped` 时，目标会以
  `stand_down_reason: "token_capped"` 退场，而不是再排入一次延续。
  评估器仍会先运行，因此已达到上限的 run 确实满足了的目标仍会被清除，其他
  `stop_reason` 的行为与之前相同。

- **agents：** token 预算对没有 `run_id` 的 run 重新生效——包括 LangGraph
  Server、`langgraph dev` 以及直接调用 `create_omniharness_agent` 的调用方。
  两处缺陷都源于那个 runtime 局部的回退键。子智能体的硬停止被存在 id
  字符串下，却用 `consume_stop_reason(None)` 读回，因为 `SubagentExecutor`
  会传播父级的 `run_id` 而父级没有，于是被 token 上限截断的子智能体向父级
  报告的是干净的 `Task Succeeded`，而不是上限截断失败。此外，LangGraph
  会给每个节点各自的 `Runtime` 包装器，因此 `id(runtime)` 在 `after_model`、
  下一次 `wrap_model_call` 与 `before_agent` 之间各不相同：
  排队的预算警告从未被投递，`after_model` 错过了 `before_agent`
  的基线而把线程里的每条 `AIMessage` 都计入，
  同一线程上的第二次调用还被计入了第一次调用的令牌。现在，context
  中没有非空字符串 `run_id` 的调用会改用 LangGraph 按 run 作用域的
  `Runtime.control` 对象作为键，也就是循环检测使用的同一个锚点；
  而停止原因会严格按给定的 context `run_id`
  存储，包括 `None`。

- **agents：** `create_omniharness_agent` 的三项功能现在名副其实。工厂图此前是在
  没有
  `DurableContextMiddleware` 的情况下构建的，
  而正是它写入 `delegations` 账本——因此 `SubagentLimitMiddleware`
  始终把此前的委派数计为零，只有 per-response 上限生效——也正是唯一会把
  `summary_text` 放回模型请求的东西，
  因此第一次压缩之后模型只看到保留的尾部，摘要就此丢失。另外，
  `RuntimeFeatures(token_budget=True)` 构建的 `TokenBudgetConfig()`
  其 `enabled` 默认为 `false`，于是每个钩子都提前返回，既没有警告，
  也没有硬停止，更没有 `token_capped`。现在
  `_assemble_from_features` 总会按 lead-agent 链的同一位置添加
  `DurableContextMiddleware`，工厂的模型请求会在图含有摘要、委派或
  已加载技能文件时携带隐藏的 durable-context 块，而
  `token_budget=True` 会构建 `TokenBudgetConfig(enabled=True)`。

- **sandbox：** 一旦并发子智能体数量超过 AIO 镜像的 shell 会话上限，并发子智能
  体就会停止工作。每个并发子智能体都会获得自己的持久化 scoped shell，但 AIO
  镜像把 `MAX_SHELL_SESSIONS` 限制为 10，因此第十一个 shell 会在 OmniHarness
  仍持有其 scoped id 的情况下淘汰掉最旧的空闲会话——该子智能体的下一条命令随即以
  `404 Session not found` 失败，而在不提高容量的情况下重建会话只会淘汰另一个
  子智能体并丢失其 shell 状态。新的本地容器现在会把
  `subagent_runtime.max_running + 1`（多出的那个槽位给 lead shell 留出空间）
  作为 `MAX_SHELL_SESSIONS`，provisioner 模式会把同一个值转发给 sandbox Pod，
  而显式设置的、低于所需容量的 `sandbox.environment.MAX_SHELL_SESSIONS`
  现在会在 provider 启动时报错并列出两个数值。如果 scoped 会话仍然丢失
  （因超时或外部清理），OmniHarness 会重建它一次，且仅针对结构化的
  `404 Session not found` 响应。

- **subagents：** 子智能体在自己的上下文被压缩之后仍保留自己的指令。执行器以
  `system_prompt=None` 构建 agent，并把拼装好的提示作为第一条消息放进
  state，因此其中承载着角色提示、`<report_contract>` 引用规则、验收标准
  说明、技能索引，以及被推迟的 MCP 工具和路由提示——而压缩是按索引裁剪的，
  索引 0 永远落在被摘要掉的部分里。第一次压缩之后的每一次模型调用都是在
  完全没有系统提示的情况下进行的，而摘要也替代不了它，因为它是以隐藏数据
  注入的，权限契约明确告诉模型不要遵从它。现在动态上下文保留会一并挽救
  `SystemMessage`，以及带标签的提醒和最新的用户消息，并保持它们的顺序，
  使提示仍排在最前、且不会被送进摘要器；当提示加上当前请求就是剩下的全部
  内容时，直接跳过压缩，而不是把提示摘要掉。lead agent 不受影响——它的提示
  是请求的 system message，而不是 state 里的一条消息。

- **worker：** 被委派的子智能体出错不再导致父 run 失败。当子智能体的模型
  调用在重试后仍以错误结束时，执行器报告 `task_failed`，lead agent 仍然
  作答，但 worker 还在根级 `task_running` 自定义事件里看到了
  `omniharness_error_fallback` 标记——每一个都携带一条带 `additional_kwargs`
  的子智能体消息——并据此把父 run 标记为 `error`，错误文本取自子智能体。
  目标延续随之停止，而一次编辑并重跑把线程回滚，丢弃了编辑后的问题和新的
  回答。自定义帧不再参与父级的错误回退检测，而 lead 自身的错误回退仍通过
  `values`、`messages` 和 `updates` 帧送达；现在 lead 完成时父 run 以
  `success` 结束。

- **sandbox：** 反向解析 Windows 宿主机路径的正斜杠拼写。正向解析以 `/`
  拼写已解析的路径，因为反斜杠会破坏 `\U` 这类 bash 转义序列，但把输出中的
  宿主机路径映射回其 `/mnt/...` 形式的反向扫描器仍把匹配锚定在原生的反
  斜杠基路径上——因此每个在命令输出或智能体写入的文件中回来的正向解析路径
  都无法匹配，把原始宿主机路径、真实用户名和完整目录树泄露给了模型，而不是
  智能体本应引用的容器路径。现在扫描器的匹配与分隔符无关，与沙箱工具早已
  采用的同一份契约一致；在两种拼写重合的 POSIX 宿主机上不受影响。

- **sandbox：** 远程 `list_dir` 不再把失败报告为空目录。在缺失路径上执行
  `find ... 2>/dev/null` 只产生空的 stdout，而客户端错误被当作 `[]` 吞掉，
  于是 `ls` 告诉智能体该目录是 `(empty)`——一个已死的沙箱、一个已关闭的
  客户端和一个不存在的路径看上去都像一棵可写的空树，让智能体覆盖已有文件
  或跳过恢复。AIO、E2B、BoxLite、OpenSandbox 和 Tenki 现在会在命令或客户端
  失败时抛出 `OSError`，在什么都没列出时抛出 `FileNotFoundError`，与本地
  沙箱对非目录路径的既有行为一致；真正空的目录仍报告 `(empty)`，而
  `find -H` 让带符号链接的根仍可列出。

- **sandbox：** 远程 `grep` 与 `glob` 不再把失败报告为“没有匹配”。这些搜索
  丢弃了 stderr，并从 `head` 取管道状态，因此缺失的搜索根、缺失的
  `grep`/`find` 二进制或不可读的目录树会什么都不打印并以 0 退出——而工具会
  告诉智能体 “No matches found”，而本地沙箱在这种情形下报告的是
  `Error: Directory not found`。现在一个共享包装器会记录搜索命令自身的状态：
  根缺失时抛出 `FileNotFoundError`，任何其他失败——包括在已经打印了部分结果
  之后的 `grep` 2 或 `find` 1，因为调用方无法区分部分结果与完整结果——都抛出
  `OSError`，告诉智能体有些路径无法读取。真正的无匹配仍返回 `[]`。E2B、
  OpenSandbox、BoxLite 和 Tenki 在客户端已关闭时也会抛出，而不是返回空。. Continue with start_line=744]`
  带范围的读取报告的是文件行号，而不是 provider 的切片相对行号。单个超长
  行仍然在字符上限处截断，因为丢掉它会浪费掉大部分预算，此时标记指向
  `bash`，而不是一次无法返回该内容的 `read_file` 调用。

- **sandbox：** 强制 PowerShell 使用 UTF-8 控制台，使 CJK 工具输出在 Windows
  上不再乱码。命令运行器通过 UTF-8 管道读取器捕获 stdout，但 Windows
  PowerShell 5.1 除非显式切换，否则以遗留的 OEM 代码页写出控制台输出——
  在 zh-CN Windows 上是 GBK——因此每个 CJK 字符到达时都是乱码，而又因为读取
  器是替换无法解码的字节而不是抛错，损坏是静默的。现在每个 PowerShell
  `-Command` 载荷都会在用户命令运行前把 `InputEncoding`、`OutputEncoding`
  和 `$OutputEncoding` 设为 UTF-8。

- **sandbox：** Docker-outside-of-Docker 沙箱的端口绑定在 Docker Desktop 上
  默认绑定到回环地址。`OMNI_HARNESS_SANDBOX_HOST` 在 DooD 模式下默认为
  `host.docker.internal`，它在容器内解析为 Docker Desktop VM 网关，而把沙箱
  端口发布到该地址会让宿主机套接字层以 `WSAEADDRNOTAVAIL` 拒绝绑定——因此
  即使启动成功了，第一个沙箱 shell 动作仍以 `ports are not available` 失败。
  当 Docker server 是 Docker Desktop 且未配置
  `OMNI_HARNESS_SANDBOX_BIND_HOST` 覆盖时，绑定主机现在是 `127.0.0.1`，
  Docker Desktop 会转发它；显式覆盖仍然优先，原生 Linux DooD 不受影响。

- **frontend：** 让人工输入卡片与请求它的回合待在一起。在多轮对话中，一张
  既有的 `needYourHelp` 卡片可能漂到下一条用户消息下方，于是时间顺序变得
  误导，一个已回答的请求可能读起来像新一轮的一部分。一条提交前的基线消息
  可能被编进新持久化的用户消息之后，一张仅通过 REST 历史确认的卡片可能
  永远进不了 checkpoint 基线，而已经为当前 run 持久化的步骤可能在一次中断
  之后被抬进上一轮。现在基线消息会恢复在待处理的人类消息之前，经 REST
  确认的卡片算作已确立的历史，而当前 run 自身的步骤留在启动它们的消息
  之下。

- **frontend：** 在增量流重连之后恢复用户的输入。在较晚一个回合期间刷新，
  可能让重连流在当前人类输入进入持久历史 feed 之前先回放 AI 与工具 chunk，
  于是用户的消息短暂消失，其推理步骤被归到上一轮之下。现在活动 run 的输入
  会在加入增量流之前先从 `kwargs.input` 恢复并合并入最新的持久线程状态，按
  id 去重；如果元数据或状态读取不可用，则原样沿用先前的重连路径。

- **frontend：** 即使一个智能体的工具组显式为空，也显示它的技能徽章。徽章
  容器的空值合并链停在工具组计数 `0` 上，因此一个声明为 `tool_groups: []`
  且 `skills: ["data-analysis"]` 的智能体在 Agents gallery 中丢掉了徽章——
  尽管显式为空的工具组列表是有效的，并受 Agent API 与 `update_agent` 工具
  支持。现在容器在两个列表中任意一个至少有一项时即显示。

- **frontend：** 删除侧边栏会话前先确认。在某个最近会话的菜单中选择 Delete
  会立即移除该对话及其文件，没有任何确认步骤，尽管删除是不可逆的。现在一个
  对话框会点明该对话并警告删除不可逆，聚焦 Cancel，并在 Cancel、Escape 或
  关闭时保持会话完好；删除待处理期间操作被禁用、驳回被阻止，而删除失败会让
  对话框保持打开并带上底层错误，以便用键盘重试。该对话框挂在虚拟化的侧边栏
  行之外，因此一次列表刷新无法在一次部分删除之后移除重试 UI。

- **frontend：** 让 MCP 配置对话框留在视口内。在 Capability Center 中打开
  一份很长的 MCP server 定义会让 JSON textarea 长过窗口，于是居中的对话框
  裁掉了标题、关闭控件和 Save/Cancel 按钮，在较小的窗口上变得难以编辑或
  关闭。现在对话框受视口约束、在桌面上有更多横向空间，长 JSON 在编辑器内部
  滚动，而标题、Close、Save 和 Cancel 留在滚动区域之外，即使在极小的视口下、
  或遇到很长的服务器名称或校验消息时也是如此。

- **frontend：** 中文本地化文档链接。本地化文档中的 MDX 链接与 Nextra 卡片
  此前在改写时并不知道活动的文档语言，于是跟着快速上手链接走的中文读者被
  送到了英文页面。现在本地化文档布局通过 context 提供该语言，链接改写会
  尊重它。

- **events：** 读取含有 U+0085、U+2028 或 U+2029 的 JSONL 事件记录。三个
  读取器都会把这些 Unicode 分隔符当作记录边界来切分，因此携带其中之一的
  记录在读取时会被跳过——这会在重新打开之后复用事件序列号，并把幂等插入
  变成重复。现在线程读取、run 读取与序列恢复都按物理换行切分；既有有效
  文件无需重写。

- **events：** 阻止 JSONL 线程变更在一次删除中分裂到两代锁。
  `delete_by_thread()` 在仍持有每线程锁的同时把它从注册表中移除，因此一个
  已排在旧锁上的变更可能与一个稍后为同一线程解析出新建锁的变更并发运行
  ——在紧跟删除边界处出现重叠的序列号分配与文件变更。现在注册表是一个
  `WeakValueDictionary`，且不再弹出该条目，于是持有者与排队的等待者让同一代
  保持存活直到它们排空，之后该条目自行消失。

- **gateway：** 以数据属主、而非授权身份读取一个线程的 run。列表、keyset
  分页和单 run 读取端点按调用方的授权身份过滤 run 行，而 `start_run` 给它们
  盖的是数据身份戳——两者只在本来就是安全的属主取值上重合，因此受信任的
  内部调用方即使在自己有权操作的线程上也总是看到一个空 run 列表和 404，
  而这个症状很容易被误读为 run 丢失。现在内部调用方会跳过每用户存储过滤器，
  而这些端点的线程可见性已经做了授权；浏览器与 API 会话则保持各自确切的每
  用户过滤器；两个消息读取端点有同样的混淆，也以同样方式修正。

- **conversation：** 让会话读取器的页面留在内联范围内，并说明何时丢掉了
  文本。一个页面此前是靠切掉放不下的最后一条消息来填满其 20,000 字符上限的，
  而被切掉的后缀永远无法翻页取回——六条各 3,500 字符的消息中最旧的一条回来
  时约 2,500 字符，且 `has_more: false`。更糟的是，超出默认 12,000 字符工具
  输出预算的页面会被 `ToolOutputBudgetMiddleware` 外置，于是模型只看到一份
  摘要加上一份源文本的文件副本，而这是在目标线程里。现在页面按实际适用于
  `read_conversation` 的预算来确定大小（每工具覆盖，否则
  `externalize_min_chars`，以及 `fallback_max_chars`），仍以 20,000 文本字符
  为上限，而放不下的一条消息会完整地开启下一页——于是一项运维设置始终当家，
  且 `tool_output.tool_overrides.read_conversation` 只调整这一个工具。现在
  被截断的结果会带上一条提示，要求智能体承认这一省略、并在声称完整覆盖之前
  索取缺失的材料。

- **client：** 发出后又被后续某个节点改写的 AI 消息，其新增文本现在也能流式送
  出。`LoopDetectionMiddleware`、`TokenBudgetMiddleware`、
  `SafetyFinishReasonMiddleware`、`SubagentLimitMiddleware` 与
  `TerminalResponseMiddleware` 都会在各自的节点里用同一个 id 改写最后一条 AI
  消息，但流只会把首次见到的 id 记下来，之后一律跳过，因此改写从未送达
  `messages-tuple` 消费方：`chat()` 与 headless `--print` 返回的是改写之前的文
  本，而不是终态错误或强制停止提示；TUI 从未显示停止提示或安全提示；模型节点
  之后追加的 `token_usage_attribution` 也始终没到。values 路径现在会为每个 id
  记住最后一次见到的消息对象，并在快照中持有另一个对象时重新检查它，只把新增的
  文本作为又一次 delta 发出，并把新的 `additional_kwargs` 走既有的仅元数据后续
  事件；未变化的消息仍会被跳过，不再重新抽取文本。不会扩展已发送文本的替换则不
  会重新发出。

- **mcp：** 并行的同步 MCP 调用不再互相取消对方的连接。当内嵌客户端向同一个
  stdio server 派发两次同步调用时，每个包装器都跑在自己的事件循环上，而池会把
  兄弟循环上的存活会话与进行中的创建视为过期——把它们取消或关闭，并以
  `CancelledError` 中止某个工具步骤，而不是返回两个结果。已建立的会话与进行中
  的创建现在按 `(server_name, scope_key, owning_loop)` 归键，因此同一循环内的
  调用方仍共享创建与状态，而不同的循环各自独立，每个属主也只回收自己的记录，包
  括在正常的 `asyncio.run()` 关闭之后。同步调用仍使用彼此独立的子进程会话，也
  不获得任何共享的服务端状态。

- **web-fetch：** 抽取出的 Markdown 里的相对目标现在会按其来源页面解析。Jina、
  Browserless 与 InfoQuest 原样返回 HTML 中书写的链接，因此位于
  `https://example.com/docs/current` 的页面会产出 `[Next](../next)`，让智能体拿
  不到任何可以继续跟进的 URL。三个 provider 现在都会把请求的 URL 传给共享抽取
  器，由它把锚点与图片目标相对该 URL、或相对首个可用的文档 `<base>` 解析；只改
  写目标属性的取值，而不是序列化另一棵解析树，因此畸形的标记、注释、脚本与属性
  格式都原封不动地保留，并仍以原样到达 Readability.js。fetch 校验、4096 字符的
  输出上限与线程外抽取均未改变，Python 回退路径也保持纯文本行为。

- **community：** Tavily 抽取现在从 `web_fetch` 条目而非搜索配置读取凭据。当
  `web_search` 用 Serper、`web_fetch` 用 Tavily 时，fetch 用 Serper 的 key 构造
  客户端，把独立的 Tavily fetch key 完全忽略了。现在每个工具都从自己的条目读取
  `api_key`，并在未提供时回退到 SDK 的 `TAVILY_API_KEY`，与既有的 Exa 辅助函数保
  持一致。只在 `web_search` 下放置共享 Tavily key 的配置，必须同时在
  `web_fetch` 下也设置它，或让两者都依赖 `TAVILY_API_KEY`。

- **browser：** 浏览器会话的拆除不再随调用方的取消而中断。
  `BrowserSessionManager.close_session()` 会在 await 其关闭之前先把会话从注册表
  中移除，而该关闭又直接 await 私有的 Playwright 循环，因此此刻的取消会穿过
  `asyncio.wrap_future()` 传播到清理逻辑本身——留下浏览器进程与 context 成为孤
  儿，会话却已不在注册表中，也没有属主再来重试。`close_all_sessions()` 在更大规
  模上有同样的属主问题：它先清空整个注册表，因此关闭第一个会话时的取消会让之后
  每个会话都彻底没有安排任何拆除。现在拆除会在任何可取消的 await 之前提交给私有
  循环，并在 `asyncio.shield()` 之后 await，而 close-all 会在其首个 await 之前先
  安排好每个会话，并对组等待加 shield。调用方仍会收到 `CancelledError`；只有已
  经启动的清理的属主身份与它隔离了。

- **setup：** 同一个 pre-sync extras 检测器现在按 `utf-8-sig` 读取
  `config.yaml`。PyYAML 能接受前导的 UTF-8 BOM，但检测器按纯 `utf-8` 读取该文
  件，把 BOM 留在了第一行上，因此其锚定的章节模式无法认出合法配置的开头章节，
  并漏掉了它声明的 extras——`postgres`、`browser` 与 `ollama` 的检测在其章节位
  于最前时都以同样方式失败，而同一份文件的纯 UTF-8 副本却可以正常工作。

- **channels：** WeCom 的两条对外路径都发送无上限的文本，而 bot 协议把内容上限
  压到 20480 UTF-8 字节，这个门槛一份深度研究报告轻易就能越过。超过上限时，
  `_send_with_retry` 重试三次后放弃：流式路径让回复卡在中途，从未发送过
  `finish=true`；推送路径则把回复整个丢弃。流式回复现在在 UTF-8 字符边界上截
  断，其后带一个可见的截断标记——一个流承载整条回复，因此不会在中途断开——而
  没有可回复帧的主动推送（例如定时任务通知）则按换行边界拆成顺序的 markdown 消
  息，让完整内容仍能送达。两条路径现在都以 UTF-8 字节而非字符来度量载荷。

- **channels：** 现在单条无法解码的 WeChat 消息不会再拖累同批其余消
  息。`_poll_loop` 在收到整批消息后立刻持久化 `get_updates_buf` 游标，随后逐
  条迭代 `data["msgs"]` 且没有按消息隔离错误，于是只要有一条消息的处理抛出异
  常，现实中的触发因素是损坏或无法解密的附件，例如被截断的加密图片 payload，
  循环就会中断，而游标此时已经越过整批消息。失败消息之后的每条消息都会被永久
  丢弃，下一次轮询也不会重新拉取它们。现在 `_handle_update` 在按消息包裹的
  `try`/`except` 中运行，因此同批消息仍能送达 bus，失败会连同其消息 id 一起
  记入日志，而游标仍会在整批消息全部尝试过之后前进。

- **channels：** Discord 线程映射在线程创建之后于事件循环之外持久化，因此进
  程若在创建与其后台写入之间被杀掉，仍可能丢失最新的映射，并让某个 Discord
  线程在重启后无法访问。`stop()` 现在会把内存中的映射刷写到磁盘，并做了包
  装，使关闭路径永不被阻塞，这是在硬杀窗口之上的一张尽力而为的兜底网，而不是
  新的写入路径。

- **channels：** 在 Telegram 频道配置中启用 `rich_messages` 会让每条最终对外
  消息都渲染成一行损坏的单行文本：像 `/help` 这样的命令菜单与普通的错误回复
  都被经 `sendRichMessage` 以 `rich_message.markdown` 发送，而后者会合并单个
  换行，并剥掉菜单所依赖的 `<name>` / `<skill-name>` / `<task>` 尖括号
  token。现在只有 `rich_messages` 已启用 *且* 文本确实包含某种富文本构造，即
  围栏代码块、表格行或分隔行、任务列表、`[text](url)` 链接、粗体、斜
  体、`<details>` 块或 `$$` 数学式时，消息才会以富文本形式发送。该检测器刻意
  保守，要求表格必须让该行以 `|` 开头，因此 `/help` 中像
  `/goal [condition|clear]` 这样的一行永远不会触发它。

- **models：** 请求准入限流器在两次独立的加锁中分别决定立即准入与入队，因此
  一个阻塞型调用方可能观察到下一个许可尚未到期、在入队之前被挂起，随后在许可
  到期而等待队列仍为空时被更新的调用方抢先：新来者拿走了许可，较早的调用方只
  能再等一个间隔，或在 `max_wait_seconds` 较短的情况下超时，而较晚的那个请求
  却成功了。立即准入与 FIFO 入队现在是一次加锁保护的单一决策。非阻塞调用仍会
  快速失败且永不入队，队列化限速、取消、超时、队列容量与无突发行为均未改
  变。

- **uploads：** 单个 200,000 字符的段落会产出 199,999 字符的上传预览，尽管有
  五行的限制；过长的合法标题也会绕过 50 条的上限，而该上限实际上是上下文大小
  的约束。大纲标题现在统一截断到 200 字符，回退预览文本则截断到 2,000 字符并
  跨所有行，省略标记也计入这些预算。物理行号、短文本、既有的标题与预览数量，
  以及原始文件字节都得到保留；这约束的只是返回的摘要文本，而不是文件扫描内
  存，也不是跨上传的总预算。` 里的 `[]`
  默认值从未生效，一个宽泛的 `except` 又把由此产生的 `TypeError` 渲染成三条
  `'NoneType' object is not iterable` 检查结果。新用户会在 `make doctor` 本
  应减少困惑的那一刻看到一副安装损坏的样子，而他们其实只是还没有配置任何模
  型。现在当没有配置任何模型时 LLM 检查会跳过，只留下可操作的
  `models configured` 失败及其 `make setup` 提示；一旦配置了模型，一切都不会
  改变。

- **docker：** 在 Windows Git Bash 上，`make docker-start` 与 `make up` 会无
  条件中止，并报出 `Docker socket not found at /var/run/docker.sock —
  AioSandboxProvider (DooD) will not work.` MSYS2/Git Bash 在该路径下并没有
  物理的 Unix socket，Docker Desktop 使用的是命名管道，尽管守护进程原生支持把
  `/var/run/docker.sock` 挂载进 Linux 容器，因此这项检查永远不可能通过。在
  `MINGW*`、`MSYS*` 与 `CYGWIN*` 下，预检现在改为验证 `docker info` 的连通
  性，而不再要求存在 socket 文件；POSIX 主机在缺少 socket 时仍会快速失
  败。

- **MCP：** 从工作区变更排除内部 stdio 临时目录 `.mcp/tmp`。
- **沙箱：** 接受文档中的 E2B reconciliation 配置字段。
- **沙箱：** 按文件、挂载及整个上传过程限制 E2B mount 上传的大小、文件数和时间。
- **沙箱：** 保留 E2B 同步文件名尾部空白并容忍越界远端 mtime。
- **沙箱：** 结构化技能读取经沙箱 provider 路径映射解析，与 `ls`/shell 使用同一启用状态投影。
- **记忆：** Honcho 与 Mem0 在配置解析时拒绝非正或非有限的 timeout/字符上限。
- **记忆：** 自定义智能体 bootstrap 事实限定到所选智能体 bucket。
- **Artifact：** Windows 支持原子保存；读取响应提供 SHA-256 ETag，使普通 HTTP LAN
  等无 `crypto.subtle` 环境也能预览和编辑。
- **前端：** 长 run 前后保持会话顺序稳定，用户消息不再重复或落到自身步骤之后，
  mid-run 页面重载后回合步骤也不再出现在触发该 run 的用户消息之前。(、、)
- **前端：** HTML artifact 注入 base href 时不再把 `<header>` 误判为 `<head>`。
- **前端：** 聊天页按置顶状态排序。
- **前端：** 模型加载失败时显示工作区错误 banner 与重试操作。
- **前端：** 后续回合流式输出时仍保留已完成助手消息的复制等操作。
- **前端：** 复制 Lark 授权链接时复用 clipboard fallback。
- **渠道：** 用固定 worker pool 与有界队列限制入站流量，关闭时等待真实跨线程任务。
- **渠道：** 飞书、Telegram 与企业微信发送附件时把文件 IO 移到 worker 线程。
- **飞书：** 接收文件保持事件循环非阻塞，避免重名覆盖、越界写入，并让单个附件失败不阻塞其余消息。
- **钉钉：** 命令分类前剥离前导 `@bot`，群聊中的 `/new` 等命令可被识别。
- **企业微信：** 序列化 WebSocket 启停并等待 SDK 接收任务真正结束。
- **Lark：** 沙箱内 CLI lock 目录保持可写，含凭据的 config 根目录仍为只读。
- **调度器：** 读取时转换序列化的任务时间戳。
- **调度器：** busy 的定时 occurrence 改为进入持久队列而非跳过，由
  `scheduler.queue_timeout_seconds` 限制等待并可跨 Gateway 重启。
- **开发：** backend `make dev` 的 Uvicorn watcher 排除运行时状态，智能体写文件不再重启 Gateway。
- **Docker：** 加固本地与容器启动：`make up` 等待健康检查，允许缺失 `.env`，生产
  环境可写 extensions 配置，运行数据不进入构建上下文，日志命令正确解析 checkout，
  默认回环 origin 可完成 dev setup hydration。(、、、、、)
- **网关：** 为持久化消息标记服务端权威的 feed 位置，避免历史超过一页且触发上下文
  压缩后，较早的用户消息消失或跳到步骤流中间。
- **消息：** 移除旧版 `<uploaded_files>` 标签处理：后端将 #4174 之前的写法视为
  普通内容，仅剥离 `<current_uploads>`；前端继续剥离旧标签，确保历史会话仍能干净
  渲染。
- **沙箱：** 将 `bash`、`ls`、`glob`、`grep`、`read_file`、`write_file`、
  `str_replace` 和 `task` 面向模型的 `description` 参数统一改为可选（默认空），
  provider 省略该参数时不再在执行前被拒绝。
- **沙箱：** 将 Windows MSYS 路径转换排除限定到安全的虚拟路径前缀，不再全局
  禁用转换，使依赖正常路径转换的 host-native CLI launcher 恢复工作。
- **技能：** 解析可移植的 `allowed-tools` scalar 时感知括号，使 `Bash(tvly *)`
  这类条目保持完整；未匹配括号会被拒绝而非静默拆分，参数限定条目保持字面含义，
  不会扩大访问范围。
- **config：** `use_previous_response_id` 在 `config.yaml` 的模型条目里是可
  用的；它并非 `ModelConfig` 字段，只经由模型工厂的 `extra="allow"` 透传抵达
  `ChatOpenAI`；但它从未被记录，读起来又像是 `use_responses_api` 的同义词。
  事实并非如此：`use_responses_api` 选择的是端点，而
  `use_previous_response_id` 则把 Responses API 从每轮重放完整历史切换为在服
  务端状态上串接。`config.example.yaml` 中的 OpenAI Responses API 示例新增了
  一行被注释掉的 `use_previous_response_id: false`，并注明它会原样转发给
  `ChatOpenAI`、串接起来的上下文仍按 input token 计费、以及客户端的历史改写
  只在历史被重放时才生效。仅新增注释，没有 schema 变更，没有新的 `ModelConfig`
  字段，也没有 `config_version` 版本号提升。
- **MCP：** 普通 stdio 工具在 transport 断开后可重新连接：仅当失败的 pooled
  session 仍在注册时将其淘汰，原始错误照常返回且不自动重放，后续重试会启动新的
  子进程。
- **MCP：** 在配置边界拒绝无法作为 HTTP header value 传输的凭据（尾部换行或空白、
  非 ASCII），避免 transport 异常回显完整值并将 secret 泄漏到模型上下文、
  checkpoint 和 trace。
- **子智能体：** 在提交失败路径停止僵尸 PENDING registry 条目，并直接根据 waiter
  长度计算容量快照中的 queued 数量，避免遍历被其他线程并发修改的 deque。
- **Discord：** 强引用 ack-reaction task，并在关闭时将其 drain，避免 GC 静默丢弃
  reaction 或在重启周期之间固定住 channel。
- **流式传输：** subscriber 使用过期 cursor 重连到空或已 drain 的 stream 时，
  `MemoryStreamBridge._make_gap` 不再触发 `IndexError`。
- **前端：** 格式化结构化上传错误详情（FastAPI validation issue、对象、数组），
  不再显示 `[object Object]`。
- **前端：** 将已选模型名称限制在 selector button 宽度内，过长名称会在 composer
  和 sidecar 中显示省略号，而不再溢出。
- **开发：** 所有平台的前端开发服务器默认使用 Webpack
  （`OMNI_HARNESS_DEV_BUNDLER=turbo` 可重新启用 Turbopack），避免 Turbopack 在
  macOS 上泄漏 PostCSS worker、在 Windows 上发生 runtime panic。
- **脚本：** 使用显式 interpreter（`bash scripts/...`）运行仓库 shell script，
  避免 zip/tarball 下载、`core.fileMode=false` 或非 POSIX 文件系统导致 executable
  bit 丢失后，`make docker-start` 等命令以 `Permission denied` 失败。
- **记忆：** 配置为终止回合的记忆读取现在会抛出与后端无关的 `MemoryReadError`，
  且 prompt 装配阶段不会再吞掉它：严格模式的 OpenViking（`read: raise`）、Mem0
  与 Honcho 读取都会传播；OpenViking 作用域解析失败遵循配置的读取策略；5 秒注入
  deadline 同样遵循该策略（fail-open 时无上下文继续，严格模式以超时为原因抛出）。

- **scripts：** 在原生 Windows 上，`shutil.which("pnpm")` 遵循
  `PATH`/`PATHEXT` 的解析规则，可能选中一个通用的 `pnpm` 匹配，即 `.exe` 或
  `.bat`，或位于更早路径上的包装脚本，而不是 npm 安装的 `pnpm.cmd` 包装脚
  本。共享的主机运行器现在会先检查 `pnpm.cmd` 与 `corepack.cmd`，再检查那些
  通用名称，与仓库既有文档中记录的 Windows 命令选择顺序一致；POSIX 上的解析
  顺序未变。

- **tests：** 在一位 Windows 贡献者的主机上，后端测试套件跨七个文件失败了 68
  个 shell 脚本测试，而它们没有一个是由于被测代码本身有问题。CreateProcess
  会先搜索 `System32` 再搜索 `PATH`，因此 WSL 的 `bash.exe` 启动器赢下了每一次
  `["bash", ...]` 的派发，却又无法针对 Windows 检出路径运行仓库脚本：在非英语
  Windows 上，它那条本地化的 UTF-16LE 警告会击穿 harness 的管道解码，把真正
  的失败埋在 `TypeError` 背后；`sh` 在 MSYS2 之外并不存在；而
  `dev-entrypoint.sh` 的 `command -v python3` 探测选中的是 Microsoft Store
  的别名存根，它们在执行时会以 49 退出。各套件现在通过一个共享辅助函数来解析
  shell，它镜像了仓库的 Git Bash 包装脚本发现逻辑，并显式拒绝 WSL 启动器与
  Store 存根；在不存在 Git Bash 的地方则干净地跳过。POSIX 与 CI 的行为未
  变。

- **tests：** 技能 request-scoped-secrets 套件中的五个测试在 Windows 主机上
  失败，而两个负向检查则以空洞的方式通过，因为探针里嵌入了 POSIX 语
  法：`LocalSandbox._get_shell()` 在那里解析为 PowerShell，其中 `$VAR` 是一
  个未定义的 PowerShell 变量，会展开为空，因此正向检查永远看不到注入的值，而
  `"secret" not in out` 断言实际上是在与空输出比较。探针现在会按生产实际解析
  出的 shell 的语法来渲染，PowerShell 下为 `$env:NAME`，cmd.exe 下为
  `%NAME%`，POSIX shell 下为 `$NAME`，因此负向检查在 Windows 上真正验证了擦
  除效果，而按调用划分作用域的用例也证明了注入的值确实到达了第一个子进
  程。POSIX 上的输出在形式上未变。

- **tests：** checkpoint 保留需要一份可执行的声明，说明一次删除绝不可以破坏
  什么；一个只保留最新 N 个的提案就曾在评审显示它会静默破坏分支与时间旅行的
  父链语义之后被撤回。新套件把六种保留场景固定在 memory、SQLite 与 Postgres
  三套 checkpointer 上：完整 schema 与 delta schema 各自按步骤的增长基线；删
  除分支祖先会以 `CheckpointLineageError` 大声失败，而不是静默破坏分支或重新
  生成；删除一个显式的恢复目标会移除恢复入口；挂起的写入是被保留的状态，而非
  垃圾；末尾仅含时长的叶子与叶子的同级分支（真正的分叉路径）可以被安全删除。
  一份配套草案记录了受保护的集合、可证明安全的删除形态，以及带孤儿记账的联合
  表机制，供未来任何 `max_checkpoints_per_thread` 或 TTL 工作对照校
  验。
- **智能体：** 当上传（或其他）上下文包装被注入消息文本时，会话标题改用用户的原始
  消息内容生成，标题不再引用服务端注入的 `<current_uploads>` 上下文；仅含附件的
  消息保持 `New Conversation` 兜底。
- **智能体：** 仅当搜索模式无法解析主应用配置时，自定义智能体存储才回退到文件存储
  ——非法配置与缺失配置路径会直接暴露，而非静默切换存储后端——异步智能体路由中的
  store IO 也移出事件循环。
- **沙箱：** 五个远程沙箱 provider（E2B、OpenSandbox、AIO、Tenki、BoxLite）的
  `list_dir` 与 `glob` 原样返回文件名，不再剥离空白，名称以空格开头或结尾的文件
  不会列在不存在的路径下。
- **沙箱：** Bash 工具引导智能体用证据（`uname -s`、`sw_vers`、`uname -a`）检测
  执行环境，而非依赖模型假设；被拒绝的 host 路径会指引它改用纯命令探测或允许的
  虚拟路径，而不是重复被拦截的命令。
- **沙箱：** 文件追加不再在预读失败时破坏已有内容：E2B 追加只把“文件不存在”类
  错误视为空文件，其他错误直接抛出，不再用追加的尾部覆盖整个文件；AIO 追加改用
  服务端原生 append 模式，完全不需要预读。
- **技能：** 技能 Markdown 显式以 UTF-8 读取，默认代码页非 UTF-8 的 Windows 主机
  上，本地化技能不再以 `UnicodeDecodeError` 校验失败。
- **MCP：** 同步包装的 MCP 工具保持 LangGraph `ToolRuntime` 注入（无注解的同步
  包装器现在对 `functools.wraps` 透明），按用户的作用域解析与持久任务提交不再以
  `runtime=None` 运行——此前这会让完成通知 run 落到默认 lead 智能体而非该会话的
  自定义智能体。
- **前端：** 移动端侧边栏触发按钮在普通与自定义智能体欢迎页保持可点击；此前换行的
  （较长的本地化）欢迎文案在相同 `z-index` 覆盖层中可能盖住 header 的可点区域。
- **浏览器：** 后台 live-frame 调度任务保持强引用，GC 不再因回收任务而丢失其
  `finally` 中的 pending guard 清理，Browser Live 视图不再静默停止刷新。
- **运行时：** completion hook 或任务停止扇出内抛出的取消会先让终态收尾完成——
  扩展 observer 得以运行、流的 END 标记得以发布——然后再重新抛出中断；收尾尾部
  仍可被中断。
- **运行时：** 内嵌 `OmniHarnessClient` 的图缓存在任何授权模式下都按生效用户建立键，
  并在运行时上下文中落实同一用户，顺序复用于不同用户时不再提供用其他用户的 prompt
  与工作区状态装配的图。
- **运行时：** 被取消的工作区变更快照捕获会排空已在运行的扫描并清理该 run 的文本
  缓存，不再泄漏 `omniharness-workspace-changes-*` 目录；仅元数据的捕获则立即传播
  取消，不再等待扫描完成。
- **持久化：** Gateway 启动时容忍数据库已被迁移到经明确评审的更新版本
  （`0019_thread_incarnations`），使部署更新后仍可回滚到本镜像；其他未知版本、
  空版本表与多行版本表仍然快速失败。
- **上传：** 上传文档的大纲排除围栏代码块，代码注释与围栏内的粗体示例不再挤占
  50 条标题预算中的真实章节。
- **开发：** `_pick_python()` 通过 `/usr/bin/env` 校验解释器候选，与前端实际的
  启动方式保持一致；在 Microsoft Store Python 桩能通过 Bash 探测却无法通过
  `env` 的 Windows 上，`make dev` 不再无法启动前端。 扫描。
- **子智能体：** 通过 seen-id 集合对流式 AI 消息去重（O(n²) -> O(n)）。
- **沙箱：** `LocalSandbox` 的路径改写正则与本地路径脱敏模式改为按实例缓存，不再
  每次搜索命中都重新编译。
- **消息：** 按组为工具调用结果建立索引。
- **前端：** 不再在每个流式 chunk 上重新推导消息内容。
- **浏览器：** Browser Live 进度帧改用 JPEG 编码，减小传输负载。
- **前端：** 在流式 chunk 之间缓存已稳定消息的 copy-data 推导结果，不再让每个
  chunk 都为每条已稳定消息重新计算 toolbar/copy 文本。
- **前端：** 聊天流改为请求 `messages-tuple` + `updates` + `custom`，不再请求完整
  的 `values` 状态快照——重传的历史 `values` 消息约占 SSE 负载的 75%——在本地把
  reducer 事件折叠进渲染状态，完整快照仅保留用于回放缺口恢复。
- **提示词注入：** 新增输入净化中间件防御提示词注入，输入护栏中伪造的框架标签会
  被拦截，系统上下文以 `SystemMessage` 注入以隔离角色。(、、)
- **提示词注入：** 对渲染进模型 prompt 的不可信内容进行 HTML 转义——记忆事实与摘
  要、`SOUL.md`、子智能体描述、技能元数据，以及记忆更新 prompt 中的会话块——并中
  和 `web_capture` 工具结果中的提示词注入标签。(、、、
  、、、、、)
- **prompt-injection：**对 MindIE 工具响应框架进行转义。该 provider 的
   `_fix_messages` 在把工具调用名称与参数渲染进
   `<tool_call>` / `<function=...>` 标签前会对其进行转义，但把 `ToolMessage`
  包进 `<tool_response>` 的姊妹路径却原样传递文本——而该输出到达时大体未经净化，
  因为工具结果净化器只覆盖其允许列表中的远程内容工具（`web_fetch`、
  `web_search`、`image_search`、`web_capture`），并有意不处理本地
   `bash` / `read_file` 输出以及名称不同的 MCP 工具。因此 `read_file` 结果中一
  个字面的 `<tool_response>` 会提前闭合框架，其后的一切都以仿佛位于工具响应之
  外的方式呈现给 MindIE 模型，于是埋在不可信文件中的负载可以伪造
   `<system-reminder>`。内容现在用 `quote=False` 做 HTML 转义，与工具调用路径
  一致；模型仍会将实体解码回来，因此只有框架受到保护，合法结果的理解方式与之前
  完全一致。
- **机密：** 从技能环境中清除继承来的密钥环境变量（`MYSQL_PWD`、`REDISCLI_AUTH`
  、缩写形式的 `*_PASS` 与 Postgres 的 `PGPASSFILE`）；请求作用域的密钥对斜杠激
  活与自主调用的技能都会绑定。(、、、)
- **web_fetch：** 针对自托管 provider 的 SSRF 防护。
- **鉴权：** 全局技能管理接口现在要求管理员权限；旧版 skills 挂载按用户可见性门
  控；artifact 遵循受信任的 `owner-user-id` header；受信任的鉴权主体透传到运行时
  。(、、、)
- **认证：** 在 access-token 生命周期内持久化 `csrf_token` cookie。
- **MCP：** 拒绝 run metadata 中的旧版 MCP 凭据。
- **认证：** 加固登录后 `next` 路径校验。
- **前端：** 分离 origin 部署中，模型、工作区变更和 range artifact 请求会发送 session cookie。
- **技能：** 投影技能文件改为复制而非 hardlink，沙箱写入不能再修改规范来源；所有
  平台（含 Windows）遇到漂移的投影命名空间都会 fail closed。
- **脚本：** support bundle 中任意位置的 secret-shaped key（如 `db_pass`、
  `signing_key`）都会脱敏。
- **沙箱：** 加固本地 Docker sandbox container：sandbox host 非 loopback 时，
  发布端口默认绑定 Docker bridge gateway 而非 `0.0.0.0`
  （`OMNI_HARNESS_SANDBOX_BIND_HOST=0.0.0.0` 可恢复广泛绑定）；使用 Docker 默认
  seccomp profile 替代无条件 `seccomp=unconfined`
  （`OMNI_HARNESS_SANDBOX_SECCOMP_UNCONFINED=1` 可重新启用）；container 还会丢弃
  所有 capability、启用 `no-new-privileges` 并使用有界资源。
- **鉴权：** 复用持久化 sandbox 前重新检查授权策略，使被撤销的
  `sandbox:execute` grant 在下一次 sandbox-backed 回合立即生效，而不会随缓存的
  sandbox 继续存活。
- **run：** GET stream join 上的取消/回滚 action 现在返回
  `405 Method Not Allowed`——取消后继续 stream 应使用 POST——关闭 safe method 上
  被 CSRF middleware 有意豁免的状态变更；不带 action 的 GET join 保持不变。
- **沙箱：** 沙箱子进程环境会清除 `SSH_AUTH_SOCK`——继承宿主机 ssh-agent socket
  会让沙箱内代码用智能体持有的所有密钥签名与认证——除非技能通过 required-secrets
  显式声明。

### 文档

- **文档：** 说明生产 Docker 下 `LocalSandboxProvider` 如何解析
  `sandbox.mounts[].host_path`，并给出 Gateway bind-mount 与配置示例。
- **文档：** 记录 GitHub 入站去重 TTL 语义及不会被去重的重投递，并收紧测试。
- **文档：** 新增 Honcho 记忆后端专门指南，并在 README 加入长期记忆入口。
- **文档：** 将子 Agent 文档重构为中英文各十一章的用户手册（`harness/subagents/`）：
  概念、快速上手、目录、委派用法、结果与验收、限制与容量、沙箱与隔离、可观测性、
  按症状排查、开发者集成，以及附带 2026 年 6 月至 9 月变更记录的参考附录。原单页
  成为该章节的索引页，指向该页面的已有链接保持有效；指向旧页面小节锚点的深链接
  会落到索引页。

### 内部改进

- **测试：** 前端单元测试迁移到 rstest，并在 DOM 环境运行 hook 级测试。
- **测试：** live client 测试要求显式 opt-in。
- **测试：** 工具输出测试用自构造失败条件替代魔法不可写绝对路径。
- **测试：** 使用 Monocle Test Tools 新增 trace 行为测试，校验路由、工具调用和 token/时长成本。
- **测试：** 为感知租约的孤儿恢复增加 SQL 与并发 reconciler 覆盖。
- **测试：** 锁定 Gateway offline banner 的 POST logout 行为。
- **重构：** 抽取并测试前端 placeholder 检测工具。
- **重构：** 合并 E2B client 生命周期 helper，并在 warm-pool 淘汰时复用 kill helper。
- **重构：** 命名 E2B capacity ledger 的 meta-field 数量，使 admission offset 明确。
- **CI：** 发布 lark-cli-init 与 lark-broker 镜像。
- **基准：** 新增隔离的 checkpoint channel-mode 基准，对比 `full` 与 `delta` 的延迟、存储和回放。
- **deps：** 升级 `cryptography` 49.0.0 -> 50.0.0、`postcss` 8.4.31 -> 8.5.25、
  `h2` 4.3.0 -> 4.4.1、`langgraph-checkpoint-sqlite` 和
  `langgraph-checkpoint-postgres` 3.1.0 -> 3.1.1、`nanoid` 5.1.6 -> 5.1.16、
  `h3` 1.15.6 -> 1.15.9，以及 `next` 16.2.11 -> 16.3.3。其中 `next` 的升级修复
  了两条未经身份验证的远程代码执行公告，一条位于 Image Optimization API 的
  AVIF 路径，一条影响部署在 Windows 上的服务器；
  `h3` 则阻止经过双重编码的 `.` 段越出静态路由目录。

- **依赖：** 升级 `cryptography` 49.0.0 -> 50.0.0、`postcss` 8.4.31 -> 8.5.25、
  `h2` 4.3.0 -> 4.4.1、两个 `langgraph-checkpoint-*` 3.1.0 -> 3.1.1，以及
  `nanoid` 5.1.6 -> 5.1.16。(、、、、、)
- **基准：** 在 `backend/scripts/benchmark/omnimem_eviction/` 下新增可复现的混合
  memory eviction 评测，为 #4789 策略提供按构造实现 blind 的确定性 grader。
- **测试：** 将 `tests/blocking_io/` 从 `make test` 中排除；专用的
  `make test-blocking-io` suite（及其 CI workflow）仍是该目录的 owner。
- **CI：** 后端单元测试 workflow 拆分为四个并行分片——各自独占 runner 与隔离的
  Postgres/Redis——使用 `pytest-split` 与提交的时长基线，基线缺失时直接失败；
  `make test` 仍是完整的离线套件入口。
- **测试：** Windows 上跳过 POSIX mode-bit 技能权限断言（`chmod` 契约在该平台不可
  观测），使 Windows 贡献者可以获得绿色的后端套件基线。
- **测试：** 针对空技能目录固定 composer 技能建议的行为（the RFC Phase 4）：`skills`
  策略不允许任何技能的调用方——或没有任何技能的全新安装——会从 `GET /api/skills` 得到
  `[]`，此时 composer 必须降级为仅含内置命令的下拉框，而不是损坏或彻底消失。新增测试
  驱动 matcher 并真实挂载 `InputBox`：输入 `/` 时恰好列出内置命令，输入无匹配的查询时
  不渲染列表框。没有生产代码改动；已审计全部四处 `useSkills()` 消费方，均能优雅降级。


## [2.0.0] — 2026-06-15

OmniHarness 2.0 是围绕"超级智能体"框架的彻底重写，核心包含子智能体、持久化记忆、
沙箱执行以及可扩展的技能（Skill）/工具系统。本版本与 1.x 系列**没有共享代码**，
原有的 Deep Research 框架仍在
[`main-1.x` 分支](https://github.com/jokerking-oss/omni-harness/tree/main-1.x)上维护。

本次发布关闭了
2.0.0 里程碑，

### ⚠ 不兼容变更（Breaking Changes）

- **harness：** 从 `RunStore` 重新加载历史 run，并持久化"已中断（interrupted）"
  状态。run 的取消 / 多任务调度语义现在要求拥有该 run 的 worker 上具备可用的
  RunStore；跨 worker 的取消请求将返回 `409`，不再静默"伪成功"。
- **循环检测：** 支持配置开关，并可按工具维度覆盖触发频率。
- **循环检测：** 警告注入延后执行，避免与工具调用生命周期错位。
- **子智能体：** 通过终态任务事件，把子智能体的 token 用量流式上报到 header。
- **建议：** AI 追问（follow-up）建议改为可选。
- **社区工具：** 新增 Brave Search 网络检索工具。
- **IM：** 新增"用户自有 IM 渠道连接"——用户可以在运营方配置的 bot 之上，绑定
  自己的 Slack / Telegram / Discord / 飞书 / 钉钉 / 微信 / 企业微信 账号。
- **模型：** 新增 MiniMax provider，用于图像 / 视频 / 播客类技能，并新增"音乐
  生成"技能。
- **社区工具：** 为 `image_search` 新增 Serper Google 图片 provider。

#### 可观测性
- **追踪：** LangGraph 追踪名设置为 `lead_agent`（自定义智能体则使用其
  `agent_name`），让 Langfuse / LangSmith 中的 trace 更清晰。
- **默认值：** 默认开启 token 用量统计。
- **追踪：** 把子智能体的 span 归属到父线程的 Langfuse trace 上。
- **技能：** 新增面向维护者的 issue 与 PR 工作流技能。

### 性能优化

- **harness：** 把 thread 元数据过滤下推到 SQL，不再在 Python 侧后过滤。
- **运行时：** 为 `MemoryRunEventStore` 中的消息建立索引，避免 O(n) 扫描。
- **沙箱：** 加快 glob/grep 遍历中的 `should_ignore_name` 判断。
- **上传：** 在 Windows 上支持基于符号链接保护的安全上传。
- **MCP：** 加固 MCP 配置接口对异常输入的处理。
- **网关：** 限制 skill artifact 预览的解压上限，避免被 zip-bomb 类构造滥用。
- **沙箱：** 默认不再 bind-mount 宿主机的 CLI 认证目录。
- **运行时：** 持久化 run 的消息摘要。
- **运行时：** 加锁保护同步单例的初始化与 reset 路径。
- **运行：** gateway 重启后从持久化存储中恢复历史 run。
- **网关：** 对已经处于 interrupted 状态的 run，cancel 接口幂等返回。
- **事件：** 序列化结构化的 DB event 内容。
- **持久化：** 复用 token 用量按模型分组的 SQL 表达式。
- **nginx：** 把 CORS 策略下放到 gateway 的 allowlist，避免双重应用。
- **网关：** 在无状态（stateless）run 接口上强制校验 thread 归属。
- **序列化：** 从流式 values 事件中剥离 base64 图片数据。
- **网关：** token 用量归因到实际使用的模型。
- **子智能体：** 工具与中间件按 model 覆盖（model override）来构造。
- **子智能体：** 子智能体与父 run 的 checkpointer 隔离。
- **智能体：** 解决 `TodoMiddleware` 中 `todos` 通道的类型冲突。
- **智能体：** 新智能体的 bootstrap 流程保持在用户作用域内。
- **中间件：** 同步原始 tool-call 元数据。
- **中间件：** 防止 todo 完成提醒消息泄漏到 IM 渠道。
- **智能体：** `resolve_agent_dir` 要求存在 `config.yaml`，从而跳过仅含记忆的
  目录。
- **中间件：** 把 `UploadsMiddleware` 中的上传扫描移出事件循环。
- **中间件：** 针对非挂载型沙箱，把超限的工具输出外置到沙箱中。
- **子智能体：** general-purpose 的 `max_turns` 提升到 150，默认超时提升到 30
  分钟。
- **记忆：** 队列化的 memory 更新按智能体维度隔离。
- **追踪：** 把 `session_id` 与 `user_id` 透传到 Langfuse trace。

#### 工具、沙箱与 MCP
- **MCP：** 修复 MCP 配置中列表型变量的环境变量解析。
- **沙箱：** 在 `RemoteSandboxBackend` 中补上 `list_running`。
- **沙箱：** 沙箱就绪轮询不再阻塞事件循环。
- **沙箱：** Provisioner 的 PVC 数据按用户隔离。
- **工具：** 引入 `Runtime` 类型别名，消除 Pydantic 序列化告警。
- **harness：** 为同步客户端封装仅异步可用的 config 工具。
- **工具检索：** 通过移除 ContextVar，可靠地隐藏延迟加载的 MCP schema。
- **web_fetch：** 在受限网络环境下为 Jina reader 支持代理。
- **沙箱：** 修复 AIO 沙箱缓存被陈旧复用的问题。
- **沙箱：** 不再把字符串字面量路径片段误判为不安全的绝对路径。
- **MCP：** 让 stdio MCP 产出的文件可通过虚拟沙箱路径解析。
- **MCP：** 新增工具缓存重置接口。

#### 技能与渠道
- **技能：** 强制校验 `allowed-tools` 元数据。
- **技能：** 修复自定义 skill 安装时的权限问题。
- **技能：** SKILL.md 出现 YAML 错误时，展示出错行号与引号提示。
- **渠道：** 提取回复时忽略隐藏的控制消息。
- **渠道：** 暴露企业微信（WeCom）WebSocket 连接失败的信息。
- **渠道：** 用户自有 IM 消息要求绑定身份。
- **渠道：** 以运行时的 provider 状态为权威来源。
- **渠道：** 让渠道连接流程可确定（deterministic）。
- **渠道：** 增加运行态的防护约束（operational guardrails）。

#### 认证
- **认证：** 用缓存响应替换 setup-status 接口的 429 限流。
- **认证：** 对齐"认证禁用（auth-disabled）"模式与 mock 历史加载行为。
- **聊天：** 修复新会话第一条用户消息被吞掉的问题。
- **前端：** 异步 chat submit 完成后再清空输入框。
- **前端：** 对恢复出的会话消息去重。
- **前端：** 流式中的 assistant 消息不再展示复制按钮。
- **前端：** 新建会话的 thread 消息相互隔离。
- **前端：** 限制深层嵌套列表的缩进，避免渲染崩溃。
- **token 用量：** token 用量按 message id 去重聚合。
- **前端：** 移除用 Backspace 删除 prompt 附件的快捷键。
- **建议：** 解析追问问题前先剥离内联的 `<think>` 推理内容。
- **前端：** 工作区会话列表在超过 50 个 thread 后分页加载。
- **前端：** SSR 鉴权探测无法连通 gateway 时仍保持工作区可交互。
- **前端：** 删除后重置当前激活的会话。
- **前端：** 多段（multi-part）AI 消息渲染完整内容。
- **harness：** 运行时路径以项目根目录为基准解析。
- **Docker：** 把 Gateway 默认改为单 worker，避免多 worker 模式下出现异常。
- **脚本：** `make dev` 重启时保留 `uv` extras。
- **脚本：** 停止时清理本地 nginx。
- **配置：** 让 reload boundary 在代码层面可发现。
- **replay-e2e：** 重放 fixture 按调用方与会话作为 key。
- **配置：** 把 `config.yaml` 中为 null 的列表字段归一为空列表。
- **脚本：** 在 uvicorn 的 reload-exclude 生效前先创建 backend/sandbox 目录。
- **Makefile：** 修复 per-commit hooks 的安装。

### 变更

- **provider（重构）：** 各 provider 间共享 assistant payload 的回放匹配逻辑。
- **todo（重构）：** 移除未使用的完成提醒计数器。
- 清理文档中残留的"独立 LangGraph 服务器"相关内容。
- 补充自定义 AIO 沙箱镜像的文档。
- **运行时：** 增加 lifecycle 端到端测试覆盖。
- **blocking-io：** 检测器以"显式失败（fail-loud）"方式解析仓库根目录，并提供
  共享 CLI 入口。
- **CI：** 统一 PR / issue 打标签逻辑，修复 reviewing 任务的崩溃与标签抖动。

[2.0.0]: https://github.com/jokerking-oss/omni-harness/releases/tag/v2.0.0

