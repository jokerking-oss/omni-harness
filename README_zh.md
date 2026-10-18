# OmniHarness 2.0

[English](./README.md) | 中文

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](./backend/pyproject.toml)
[![Node.js](https://img.shields.io/badge/Node.js-22%2B-339933?logo=node.js&logoColor=white)](./Makefile)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

OmniHarness 是一个开源的 **super agent harness**。它把 **sub-agents**、**memory** 和 **sandbox** 组织在一起，再配合可扩展的 **skills**，让 agent 能完成从几分钟到几小时不等的任务。

它不是需要自己拼装的 framework，而是开箱即用、同时足够可扩展的运行时：默认就带上 agent 真正会用到的能力——文件系统、记忆、技能、沙箱执行环境，以及为多步骤任务做规划和拉起子智能体的能力。

## 核心能力

- **Sub-Agents**：把复杂任务拆成多个子智能体并行执行，再由主流程汇总。每个子智能体有独立上下文、工具和终止条件。
- **Sandbox**：每个任务运行在隔离的 Docker 容器里，拥有完整文件系统（skills / workspace / uploads / outputs），可执行命令、读写文件、跑长任务。
- **Skills**：结构化的能力模块，按需渐进加载——只加载当前这一步需要的，避免一次性塞满上下文。可扩展、可替换、可组合。
- **长期记忆**：跨会话积累偏好与工作习惯，越用越贴合你的写作风格与常用流程。
- **Agentic Browser**：可选的浏览器控制能力，让 agent 真正操作页面——导航、点击、输入、提交表单。
- **定时任务**：在 workspace 里按 once / cron / interval 调度，支持复用会话或每次新建会话。
- **项目**：把相关会话组织在同一名称下，共享项目指令与文档架。
- **IM 渠道**：从 Telegram、Slack、飞书、企业微信、钉钉、微信等渠道接收任务，无需公网 IP。
- **终端工作台（TUI）**：在终端里直接使用，与 Web UI 共享同一份会话存储。

## 快速开始

### 环境要求

- Docker Desktop / Docker Engine，以及 **Docker Compose v2.24+**
- Python 3.12+、Node.js 22+
- 或直接使用 Docker（推荐）

### 安装

```bash
git clone https://github.com/jokerking-oss/omni-harness.git
cd omni-harness
```

运行安装向导（推荐），它会引导你选择模型服务商、搜索工具与 sandbox 模式，生成 `config.yaml` 并写入 `.env`：

```bash
make setup
```

随时可用 `make doctor` 检查配置与系统环境。

### 运行

**Docker（推荐）**

```bash
make docker-init    # 首次运行或镜像更新时拉取 sandbox 镜像
make docker-start   # 启动服务
```

**本地开发**

```bash
make check     # 校验 Node.js 22+、pnpm、uv、nginx
make install   # 安装后端与前端依赖
make dev       # 启动服务
```

访问地址：**http://localhost:2026**

## 配置模型

OmniHarness 不绑定模型服务商，任何 OpenAI 兼容 API 都可以接入。安装向导会生成最小化的 `config.yaml`，常见的模型配置方式：

```yaml
models:
  - name: gpt-4o
    display_name: GPT-4o
    use: langchain_openai:ChatOpenAI
    model: gpt-4o
    api_key: $OPENAI_API_KEY
```

API key 建议写入 `.env`：

```bash
OPENAI_API_KEY=your-api-key
```

## 文档

- [贡献指南](CONTRIBUTING.md)
- [配置说明](backend/docs/CONFIGURATION.md)
- [后端架构](backend/README.md)

## 安全使用

OmniHarness 具备**执行系统命令、读写文件**等高权限能力，默认设计为部署在**本地可信环境**（仅本机回环访问）。

如果把 agent 暴露到不可信网络（公网、多人局域网）且没有严格防护，可能导致：未授权的非法调用（被扫描到后批量执行高危操作）、以及由此带来的合规与法律风险。

跨设备、跨网络部署时，至少要做到：

- **IP 白名单**：用防火墙或 iptables 限制只允许可信来源访问
- **前置身份验证**：用 nginx 等反向代理加一层强认证
- **网络隔离**：把 agent 与可信设备放进同一专用网段
- **首次初始化**：全新实例请立即通过 `/setup` 创建管理员账号

管理员权限等同于代码执行权限，请谨慎授权。

## 许可证

本项目采用 [MIT License](./LICENSE) 开源发布。
