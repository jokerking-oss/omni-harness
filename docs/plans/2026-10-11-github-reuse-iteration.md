# Workbarley GitHub 复用与成果工作台迭代

日期：2026 年 10 月 11 日。

本轮采用用户确定的前后端完整闭环方向，把已有交付页扩展为可搜索、可筛选的成果工作台。优先使用项目已经接入的开源组件和后端依赖；下一轮扩展文档解析和语义检索时，再按实际需求加入独立模块。

## 开源来源和接入位置

下表是针对当前 Next.js 16、React 19、Tailwind 4 和 Python FastAPI 技术栈的选型。许可证以链接中的官方文件为准。项目适配程度和优先顺序属于本项目的实施判断。

| 来源 | 许可证 | 当前状态 | 本项目用途 |
| --- | --- | --- | --- |
| [shadcn/ui](https://github.com/shadcn-ui/ui) | [MIT](https://github.com/shadcn-ui/ui/blob/main/LICENSE.md) | 已接入，本轮复用 | 组合现有 Button、Input、Select、Badge 和 Dialog，完成搜索工具栏、文件卡片和预览入口。保留现有生成组件，通过业务组件组装页面。 |
| [Vercel AI Elements](https://github.com/vercel/ai-elements) | [Apache 2.0](https://github.com/vercel/ai-elements/blob/main/LICENSE) | 已接入，后续聊天 UI 来源 | 消息、推理、工具和代码展示组件，继续通过现有 registry 更新，接入本项目的 LangGraph 数据流。 |
| [React Flow](https://github.com/xyflow/xyflow) | [MIT](https://github.com/xyflow/xyflow/blob/main/LICENSE) | 已有 `@xyflow/react` 依赖，后续图形 UI 来源 | 当需要任务依赖图或执行流程图时复用节点、连线和交互画布。 |
| [TanStack Query](https://github.com/TanStack/query) | [MIT](https://github.com/TanStack/query/blob/main/LICENSE) | 已接入，本轮复用 | 用带筛选条件和用户身份的查询键管理分页缓存，把取消信号传到请求，避免不同搜索结果混在一起。参考官方 [Infinite Queries](https://github.com/TanStack/query/blob/main/docs/framework/react/guides/infinite-queries.md)。 |
| [FastAPI](https://github.com/fastapi/fastapi) 和 [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) | [MIT](https://github.com/fastapi/fastapi/blob/master/LICENSE)、[MIT](https://github.com/sqlalchemy/sqlalchemy/blob/main/LICENSE) | 已接入，本轮复用 | 在已有成果接口增加查询参数验证，保留异步数据库读取、用户过滤和时间加执行 ID 的游标分页。参考 [SQLAlchemy SELECT 查询](https://github.com/sqlalchemy/sqlalchemy/blob/main/doc/build/orm/queryguide/select.rst)。 |
| [MarkItDown](https://github.com/microsoft/markitdown) | [MIT](https://github.com/microsoft/markitdown/blob/main/LICENSE) | 后端已有 | 继续通过现有 `omniharness/utils/file_conversion.py` 处理文档转换，沿用项目资料的派生文本路径。 |
| [Docling](https://github.com/docling-project/docling) | [MIT](https://github.com/docling-project/docling/blob/main/LICENSE) | 后续候选 | 有扫描 PDF、多栏布局和复杂表格需求时，增加可选转换器，再接入现有项目资料流程。首次使用需准备模型文件，本地推理需评估 CPU、内存和后台执行；模型权重许可单独核对。见 [模型与离线配置](https://docling-project.github.io/docling/usage/advanced_options/)。 |
| [Qdrant Python client](https://github.com/qdrant/qdrant-client) | [Apache 2.0](https://github.com/qdrant/qdrant-client/blob/master/LICENSE) | 后续候选 | 跨成果和项目资料的语义检索适配器。开发可用本地模式，扩大部署时使用异步客户端和独立服务；索引过滤由服务端绑定用户和项目，另行选择 embedding 模型。见 [多租户文档](https://qdrant.tech/documentation/manage-data/multitenancy/)。 |
| [FastMCP](https://github.com/PrefectHQ/fastmcp) | [Apache 2.0](https://github.com/PrefectHQ/fastmcp/blob/main/LICENSE) | 后续候选 | 当自有业务 API 需要独立工具服务时使用，由现有 MCP 适配器消费。保持现有持久任务运行时；HTTP 部署配置鉴权和会话管理，见 [部署文档](https://gofastmcp.com/deployment/http)。 |

本轮属于已有开源依赖的组合复用和业务适配，没有新增第三方源码副本、素材包或依赖。上表后续候选尚未安装或接入。后续复制源文件时，记录实际版本或提交、原始路径、许可证和修改范围，并保留上游版权声明。

## 第一轮交互与接口

用户在 `/workspace/deliveries` 输入文件名或来源会话标题，提交搜索后可按文档、表格、演示文稿、图片、代码和其他文件筛选。页面从后端获取匹配文件，显示来源和执行状态，通过现有文件路由预览、下载，或返回原会话。搜索和类型可以组合使用，清空筛选回到未筛选列表。

`GET /api/deliveries/page` 保留原有分页参数，增加 `q` 和 `file_type`。`q` 最长 200 个字符，去除首尾空白后按 Unicode casefold 做字面子串匹配。搜索范围是文件名和来源会话标题；文件类型按最后一个扩展名分类，扩展名大小写不影响结果。返回的文件列表只保留同时满足搜索和类型条件的路径。

接口先限定当前用户的执行和现存会话，再读取唯一的正式 `run.delivery` 凭据，校验输出路径后筛选。模型回答中的链接、目录扫描和其他用户的数据不作为结果来源。

筛选历史时每次最多扫描 50 个候选执行，额外读取一条判断后续是否还有候选。没有匹配的扫描窗口仍返回前进的游标，页面允许继续加载更早的执行；只有搜索到达范围末尾时才显示无结果。纯内存模式保留近期会话范围限制，页面说明不能代表完整历史。卡片计数只表示已加载结果。

## 验收范围

后端覆盖文件名和会话标题搜索、中文和 Unicode 大小写、全部类型、组合筛选、参数边界、跨用户隔离、非法凭据、SQL 和内存分页，以及无匹配扫描窗口的游标推进。前端覆盖请求编码和取消、筛选重置分页、文件卡片、预览下载和来源链接、加载失败重试，以及窄屏显示。

检查结果和已知环境失败见 [本轮验收记录](../pr-evidence/2026-10-11-github-reuse-iteration.md)。
