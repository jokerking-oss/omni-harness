# Exoharness 借鉴完整交付验证

日期：2026 年 10 月 11 日。需求见 [PRD v2.1](../plans/2026-10-11-exoharness-adoption-prd.md)。本记录覆盖第一阶段严格加载及第 9 节五项后续能力，使用本项目原生实现，没有引入上游代码或资产。

## 实现映射

| 需求 | 主要实现 | 验收覆盖 |
| --- | --- | --- |
| 严格工具加载 | `tools/builtins/tool_search.py`、`tools/tools.py`、`skill_tool_policy_middleware.py` | `test_strict_tool_search*.py`、去重、来源与技能策略回归；禁止批次不进入内层工具和 callback |
| 分层发现 | `tools/builtins/tool_discovery.py`、`tool_search.py`、策略中间件及主 Agent/错误恢复组装 | `test_tool_discovery.py`、真实同步/异步图、授权后统计、过期游标、无来源工具、无 schema/promotion/业务执行 |
| 历史 schema 投影 | `agents/middlewares/catalog_projection.py`、`deferred_tool_filter_middleware.py` | `test_catalog_projection.py`；失败、未知、过期和已撤销工具不投影；原状态不变；清除请求副本中的供应商响应链 ID |
| 请求证据 | `models/request_evidence.py`、factory/Codex payload hook、RunJournal/事件契约及 `RequestEvidencePanel` | `test_model_request_evidence.py`、模型 factory、journal/事件契约、API/DOM 单测；同步/异步流式及非流式、错误、并发、隐私与大小上限 |
| 项目资料结构 | `projects/document_structure.py`、`projects/tools.py` | `test_project_document_structure.py` 和既有资料工具测试；原始/文本 SHA、稳定块 ID、表格分页、字面搜索、Unicode/CRLF、转码与权限失效 |
| 交付工作区 | Gateway `routers/deliveries.py`、`/workspace/deliveries`、导航和双语文案 | `test_deliveries_router.py`、前端 API 单测、`deliveries.spec.ts`；SQL/内存分页、正式凭据、owner 隔离、预览/来源、空状态和失败重试 |

以上 backend harness 路径均位于 `backend/packages/harness/omniharness/`。页面复用现有 ArtifactViewer 和文件权限路由；请求证据复用现有运行事件 API；没有新增数据库迁移、平行 trace 库或资料库。

## 最终检查

- 相关后端最终回归：**815 passed, 1 skipped**，41.03 秒。真实模型测试没有在本次执行；跳过项保留原有规则。
- 前端完整单元测试：**1632 passed，204 files**，无失败或跳过。
- 新增交付页浏览器测试：**2 passed**。使用本机 Chrome 和 Webpack dev server（3021）；覆盖文件预览、加载更多、定制 Agent 来源链接、空状态及 503 后重试。
- TypeScript `tsc --noEmit`：通过。
- 完整 ESLint：通过；Ruff lint：通过；Ruff format：**1520 files already formatted**；`git diff --check`：通过。
- 资料工具文件卸载及运行日志 callback 的定向检查：**7 passed**。资料用例沿用仓库已有的真实引擎与 `run_file_io` call-through spy，包含新增结构目录、块读取和搜索的 worker 调度断言；callback 用例使用 strict blocking-I/O gate。

Playwright 默认 Chromium 未安装，下载也因连接中断失败。改用已安装的 Chrome 完成同一套浏览器验收；没有把下载失败当作测试通过。冷启动编译导致首次页面断言超时，编译完成后两项用例重跑通过。临时验收服务已停止。

## 请求投影基准

`backend/scripts/benchmark/tool_catalog_projection.py` 提供确定性离线场景和显式真实模型入口。同一组 4 条消息在投影前后分别为 **9253 / 1056 UTF-8 JSON 字节**；原始历史和调用/结果配对保留。该场景使用合成 schema，不能推导生产节省比例。

在 `backend/` 执行：

```powershell
& ./.venv/Scripts/python.exe scripts/benchmark/tool_catalog_projection.py offline
# 以下命令会调用两次已配置的真实模型，本次未执行：
& ./.venv/Scripts/python.exe scripts/benchmark/tool_catalog_projection.py run-live --model 'your-configured-model'
```

真实入口对原始/投影请求绑定同一个工具，验收模型是否产生唯一且参数正确的 `lookup(city="Paris")` 调用并报告 usage。它不执行业务工具，也不作为端到端业务成功率或供应商缓存命中的证据。

## 复现命令

在 `backend/` 使用已有虚拟环境：

```powershell
$testFiles = @(rg --files tests | Where-Object {
    $_ -match 'test_(strict_tool_search|tool_discovery|catalog_projection|model_request_evidence|deliveries_router|project_document_structure|bench_tool_catalog_projection|deferred_|tool_search|skill_policy_deferred|skill_tool_policy|tool_error_handling|tool_deduplication|mcp_routing_prompt|subagent_deferred|subagent_executor|model_factory|codex_provider|model_request_admission|run_journal|run_event_stream_contract|project_document_tools|harness_boundary|lead_agent_model_resolution)' -and $_ -notmatch 'blocking_io'
})
& ./.venv/Scripts/python.exe -m pytest $testFiles -q
& ./.venv/Scripts/python.exe -m pytest tests/blocking_io/test_project_documents.py tests/blocking_io/test_run_journal_callbacks.py -q
& ./.venv/Scripts/ruff.exe check . --output-format concise
& ./.venv/Scripts/ruff.exe format --check .
```

在 `frontend/` 执行安装好的本地工具（等价于项目脚本的检查项；避免 Windows pnpm 包装器触发交互式重新安装）：

```powershell
& ./node_modules/.bin/rstest.cmd run
& ./node_modules/.bin/eslint.cmd . --max-warnings=0
& ./node_modules/.bin/tsc.cmd --noEmit
& ./node_modules/.bin/playwright.cmd test tests/e2e/deliveries.spec.ts
```

标准 Playwright 命令需要项目配置指定的 Chromium；本机验收以临时配置将 `launchOptions.executablePath` 指向现有 Chrome，并将 `baseURL` 指向测试 dev server。临时配置和报告在忽略目录，不属于产品代码。

## 明确的边界与剩余验证

- 请求证据仅包含安全内容面的哈希、JSON 字节及有限部件索引。最多展示 18 个部件和 8 个工具摘要；差异针对该前缀计算，完整数量、字节和总哈希仍覆盖全部内容面。请求头、凭据和原始正文不进入证据。最终 provider payload 与模型输入有明确标记；字节减少和哈希相同都不等于 Token 节省或缓存命中。
- 资料结构读取校验最多 100 MiB 原始文件，处理最多 8 MiB 服务文本、100,000 行及 10,000 块。表格/块内容最多 20,000 字符、字面搜索最多 50 项；超限指引调用原有字符窗口读取。所有文件和解析操作从事件循环卸载。
- SQL 事件存储支持历史 keyset 分页。memory/jsonl 事件存储每页扫描最多 50 个候选执行；纯内存数据库仅考虑最多 50 个近期/置顶会话及每会话 50 个执行。页面说明此范围；正式凭据指向当前文件版本，文件可能已更新或不可用。
- 初始完整后端离线/strict blocking-I/O 门禁的已知失败详见 [R1 检查记录](2026-10-11-exoharness-r1.md)。2026-10-11 的后续复核已将真实 LLM 用例改为显式 `OMNI_HARNESS_RUN_LIVE_TESTS=1` opt-in；相关回归 **851 passed、1 skipped**，strict blocking-I/O **141 passed、3 skipped**。Windows 全量普通套件两次在未修改的 Hypothesis 随机差分测试健康检查处停止，此前 **3721 passed、61 skipped、17 deselected**；诊断排除首个测试后运行至 **3722 passed**，随后第二个随机批处理性质用例也触发相同检查。两项失败 seed 的单测重放均通过，因此仍没有宣称全仓普通门禁通过。
- 真实模型前后对照尚未运行；没有据此发布性能或 Token 节省承诺。
