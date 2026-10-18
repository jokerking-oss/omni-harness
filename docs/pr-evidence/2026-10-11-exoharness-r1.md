# Exoharness 借鉴第一阶段实现验证

日期：2026 年 10 月 11 日。需求范围见 [正式 PRD](../plans/2026-10-11-exoharness-adoption-prd.md)。

本记录保留第一阶段交付时的范围与结果；后续五项能力已继续完成，最终状态见 [完整交付验证记录](2026-10-11-exoharness-complete.md)。

## 实现结果

新增 `tool_search(names=[...], server_name=...)`，在既有延迟加载系统中提供精确批次的完整校验和真实来源限定。旧 `query` 及 `select:` 保持兼容。

精确批次只有全部成功才生成 schema 与新增 promotion。技能禁止项在调用内层工具前拒绝，避免原始 schema 先进入 `on_tool_end` 和运行日志。目录 hash 绑定无凭据来源身份与名称碰撞状态；真实组装链路保留去重前的碰撞证据，且不污染共享工具实例。

没有复制 Exoharness 的代码或资产。本轮只采用设计思路并按本仓库架构实现，保持现有许可证。

## 测试和静态检查

- 新增 63 个参数化测试案例，覆盖精确选择、来源限定、真实组装、权限前置检查和同步/异步图回调。
- 最终相关离线回归：**241 passed**。
- 后端完整 Ruff lint：**通过**。
- 后端完整 Ruff format 检查：**1508 files already formatted**。
- `git diff --check`：**通过**。
- 独立审查发现的日志 callback、来源 hash 和构建碰撞三个问题均已修正并通过二轮复核。

在 `backend/` 用现有 `.venv/Scripts/python.exe` 执行以下 PowerShell 命令可复现相关回归：

```powershell
$testFiles = @(
    'tests/test_strict_tool_search.py',
    'tests/test_strict_tool_search_policy.py',
    'tests/test_strict_tool_search_assembly.py',
    'tests/test_tool_deduplication.py',
    'tests/test_deferred_catalog.py',
    'tests/test_deferred_setup.py',
    'tests/test_tool_search.py',
    'tests/test_deferred_filter_middleware.py',
    'tests/test_deferred_promotion_integration.py',
    'tests/test_deferred_tool_crosscontext.py',
    'tests/test_subagent_deferred_promotion_integration.py',
    'tests/test_skill_tool_policy_middleware.py',
    'tests/test_skill_policy_deferred_discovery.py',
    'tests/test_tool_promotion_audit_middleware.py',
    'tests/test_thread_state_promoted.py',
    'tests/test_harness_boundary.py',
    'tests/test_mcp_routing_auto_promote.py',
    'tests/test_mcp_routing_config.py',
    'tests/test_mcp_routing_metadata.py',
    'tests/test_mcp_routing_prompt.py',
    'tests/test_authorization_runtime.py'
)
& ./.venv/Scripts/python.exe -m pytest $testFiles -q --tb=short
& ./.venv/Scripts/ruff.exe check . --output-format concise
& ./.venv/Scripts/ruff.exe format --check .
```

## 全仓检查限制

修改前启动的完整离线套件已出现失败，之后在约 17% 处长时间没有进展，已停止该测试进程。为明确首个阻塞，重新执行同一套件并增加 `-x` 与诊断超时：

```powershell
& ./.venv/Scripts/python.exe -m pytest -m 'not live' --ignore=tests/blocking_io tests/ -q --tb=short -x -o faulthandler_timeout=60
& ./.venv/Scripts/python.exe -m pytest tests/blocking_io -q --tb=short
```

普通离线套件结果为 **1 failed, 1732 passed, 30 skipped, 3 deselected**，随后因 `-x` 停止。首个失败是未改动的 `test_bench_sandbox_provider.py::test_boxlite_shim_workaround_retries_after_fixing_permissions`：Windows 文件 `st_mode & 0o111` 不满足 POSIX 可执行位断言。没有宣称剩余完整套件通过。

最终 blocking-I/O 套件为 **6 failed, 136 passed, 1 skipped**，失败位于未改动模块：

| 测试 | 失败表现 |
| --- | --- |
| `test_channel_runtime_config_store.py` 三项权限用例 | Windows 实际权限位 `438` 与期望 `384` 不同 |
| `test_dynamic_context_middleware.py::test_abefore_agent_policy_resolution_failure_does_not_replace_timeout` 两个参数案例 | 后台 worker 的 `finished.wait(1)` 断言失败；此前一次执行其中一个案例通过，存在时序变化 |
| `test_integrations_router.py::test_lark_auth_complete_route_does_not_block_event_loop` | 环境没有安装 `lark-cli`，返回 404 |

这些失败不在本轮代码路径内。本轮没有调整无关测试、跳过规则或环境依赖来使全仓门禁变绿；完整门禁仍需在适用环境继续验证。

## 后续范围

服务摘要与授权后分页、历史 schema 投影压缩、模型请求证据、资料结构块检索和跨执行交付聚合仍为 PRD 的后续候选，本轮没有将它们标为已交付。
