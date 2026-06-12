# Data Agent — NL2SQL 智能数据查询系统

基于 **RAG（检索增强生成）+ LangGraph 工作流**的智能数据查询系统。用户以自然语言提问，系统通过多路检索召回元数据（表、字段、指标、枚举值），由 LLM 生成并校验 SQL，在数据仓库执行后返回美化的 Markdown 报告。

## 架构概览

```
┌──────────────────── 前端 (Vue 3) ────────────────────┐
│  用户输入 → SSE 流式解析 → Markdown 渲染 → 表格/进度  │
└──────────────────────┬───────────────────────────────┘
                       │ POST /api/query (SSE)
                       ▼
┌───────────────── FastAPI ─────────────────┐
│  lifespan (全局客户端生命周期)              │
│  middleware (request_id 注入)              │
│  QueryRouter → QueryService → LangGraph   │
└───────────────────────────────────────────┘
       │
       ▼
┌────────────── LangGraph 状态图 (14 节点) ──────────────┐
│                                                        │
│  extract_keywords ──┬→ recall_column ──┐               │
│                     ├→ recall_metric  ──┼→ merge       │
│                     └→ recall_value  ──┘               │
│                                                        │
│  filter_table ──┬→ add_extra_context                    │
│  filter_metric ─┘         │                            │
│                       generate_sql                     │
│                            │                           │
│                       validate_sql                     │
│                         ╱    ╲                         │
│               correct_sql    execute_sql               │
│                   │              │                     │
│         (最多重试3次)     result_formatter              │
│                                │                       │
│                               END (SSE 流式输出)        │
└────────────────────────────────────────────────────────┘
       │                         ▲
       ▼                         │
┌────────── 多数据源检索层 ──────────┐
│                                    │
│  Qdrant     Elasticsearch  MySQL  │
│  (向量检索)  (全文检索)    (元数据) │
│                                    │
└────────────────────────────────────┘
```

## 核心特性

- **多路检索融合**：同时从 Qdrant（向量语义检索）、Elasticsearch（IK 分词全文检索）、MySQL（精确查询）三个数据源召回相关元数据，然后在 `merge_retrieved_info` 节点完成去重、补全和归并
- **LLM 智能筛选**：在多路检索的粗排结果上，通过 LLM 节点（`filter_table` / `filter_metric`）进一步精筛，只保留与用户问题真正相关的表和指标
- **SQL 生成与自修正**：根据筛选后的上下文生成 SQL，通过 MySQL `EXPLAIN` 校验语法，失败时自动修正（最多重试 3 次）
- **流式输出**：通过 Server-Sent Events (SSE) 实时推送每个节点的执行状态，前端可逐阶段展示进度
- **可构建知识库**：提供 CLI 脚本 `build_meta_knowledge`，从 YAML 配置一键建立元数据索引（向量 + 全文 + 关系库）

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Vue 3 + Vite 7 | Composition API，SSE 流式消费，marked 渲染 Markdown |
| HTTP 框架 | FastAPI | 异步 Web 服务，SSE 流式响应 |
| AI 工作流 | LangGraph + LangChain | 14 节点状态图，条件路由，异步流式执行 |
| LLM | DeepSeek Chat | SQL 生成、修正、结果格式化 |
| Embedding | BAAI/bge-large-zh-v1.5 | 1024 维中文语义向量，通过 HuggingFace TEI 服务 |
| 向量数据库 | Qdrant v1.16 | 字段、指标的语义向量检索 (COSINE 距离) |
| 全文检索 | Elasticsearch 8.19 + IK 分词器 | 字段枚举值的中文分词全文匹配 |
| 关系数据库 | MySQL 8.0 (SQLAlchemy asyncmy) | meta 库（元数据）+ dw 库（数据仓库） |
| 日志 | Loguru | 支持 request_id 追踪、文件轮转 |
| 配置 | OmegaConf | YAML + Python dataclass 结构化配置 |
| 容器化 | Docker Compose | 一键启动所有中间件 (MySQL/ES/Qdrant/TEI) |

## 项目结构

```
data-agent/
├── main.py                           # FastAPI 应用入口
├── pyproject.toml                    # 项目依赖 (Python 3.12+)
├── CLAUDE.md                         # 项目开发规范
│
├── conf/
│   ├── app_config.py                 # 配置 dataclass 定义 (AppConfig)
│   └── app_config.yaml               # 运行时配置 (数据库/LLM/Qdrant/ES/Embedding)
│
├── prompts/                          # 9 个 LLM Prompt 模板
│   ├── generate_sql.prompt           # SQL 生成
│   ├── correct_sql.prompt            # SQL 错误修正
│   ├── filter_table_info.prompt      # 表和字段筛选
│   ├── filter_metric_info.prompt     # 指标筛选
│   ├── extend_keywords_for_*.prompt  # 三类关键词扩展
│   ├── plan_sql.prompt               # SQL 规划（备用）
│   └── prompt_templates.prompt       # 结果 Markdown 渲染
│
├── app/
│   ├── agent/                        # LangGraph 智能体核心
│   │   ├── graph.py                  # 状态图编译与拓扑定义
│   │   ├── state.py                  # DataAgentState (TypedDict 状态)
│   │   ├── context.py                # DataAgentContext (运行时上下文)
│   │   ├── llm.py                    # LLM 客户端 (DeepSeek Chat)
│   │   └── nodes/                    # 14 个工作流节点
│   │       ├── extract_keywords.py   # ① jieba 分词 + TF-IDF 关键词提取
│   │       ├── recall_column.py      # ② Qdrant 向量召回字段
│   │       ├── recall_metric.py      # ③ Qdrant 向量召回指标
│   │       ├── recall_value.py       # ④ ES 全文召回字段枚举值
│   │       ├── merge_retrieved_info.py # ⑤ 三路召回结果合并/去重/补全
│   │       ├── filter_table.py       # ⑥ LLM 筛选必需的表和字段
│   │       ├── filter_metric.py      # ⑦ LLM 筛选必需的指标
│   │       ├── add_extra_context.py  # ⑧ 注入时间/数据库环境信息
│   │       ├── generate_sql.py       # ⑨ LLM 生成 SQL
│   │       ├── validate_sql.py       # ⑩ MySQL EXPLAIN 语法校验
│   │       ├── correct_sql.py        # ⑪ LLM 根据错误修正 SQL
│   │       ├── execute_sql.py        # ⑫ 执行 SQL 查询
│   │       └── result_formatter.py   # ⑬ LLM 将结果渲染为 Markdown
│   │
│   ├── api/                          # FastAPI 服务层
│   │   ├── routers/query_router.py   # POST /api/query 和 GET /api/stream
│   │   ├── schemas/query_schema.py   # Pydantic 请求/响应模型
│   │   └── dependencies.py           # FastAPI 依赖注入 (仓库/客户端)
│   │
│   ├── services/                     # 业务服务层
│   │   ├── query_service.py          # 查询编排 (LangGraph 执行 + SSE 输出)
│   │   └── meta_konwledge_service.py # 知识库构建 (向量化 + 索引)
│   │
│   ├── clients/                      # 外部系统客户端管理器（单例）
│   │   ├── mysql_client_manager.py   # MySQL (SQLAlchemy async, pool_size=10)
│   │   ├── es_clinet_manager.py      # Elasticsearch (AsyncElasticsearch)
│   │   ├── qdrant_client_manager.py  # Qdrant (AsyncQdrantClient)
│   │   └── embedding_client_manager.py # HuggingFace TEI Embedding
│   │
│   ├── repossitories/                # 数据仓库层 (Repository Pattern)
│   │   ├── mysql/
│   │   │   ├── meta_mysql_repository.py  # 表/字段/指标 CRUD + 关联查询
│   │   │   └── dw_mysql_repository.py    # SHOW COLUMNS / 枚举值 / 版本 / EXECUTE
│   │   ├── qdrant/
│   │   │   ├── column_qdrant_repository.py # 字段向量索引 (data-agent-column)
│   │   │   └── metric_qdrant_repository.py # 指标向量索引 (data-agent-metrics)
│   │   └── es/
│   │       └── ValueEsRepository.py      # 字段值全文索引 (data-agent-values)
│   │
│   ├── models/                       # 数据模型定义
│   │   ├── mysql/                    # SQLAlchemy ORM (table_info/column_info/metric_info)
│   │   ├── qdrant/                   # Qdrant TypedDict 载荷格式
│   │   └── es/                       # ES TypedDict 文档格式
│   │
│   ├── core/                         # 基础设施
│   │   ├── lifespan.py               # FastAPI 生命周期 (启动/关闭客户端)
│   │   ├── context.py                # request_id ContextVar
│   │   └── log.py                    # Loguru 日志配置
│   │
│   ├── prompt/
│   │   └── prompt_loader.py          # .prompt 文件加载器
│   │
│   ├── scripts/
│   │   └── build_meta_knowledge.py   # CLI: 从 YAML 配置构建元数据知识库
│   │
│   └── conf/
│       ├── meta_config.py            # 元数据配置 dataclass
│       └── meta_config.yaml          # 表/字段/指标定义 (知识库构建输入)
│
├── data-agent-frontend/              # Vue 3 前端 (聊天界面)
│   ├── package.json                  # 项目依赖 (Vue 3, Vite 7, marked)
│   ├── vite.config.js                # Vite 构建配置 + API 代理 (→ :8000)
│   ├── index.html                    # HTML 入口
│   ├── README.md                     # 前端说明
│   ├── dist/                         # 生产构建产物
│   └── src/
│       ├── main.js                   # Vue 应用入口
│       ├── App.vue                   # 单文件应用 (聊天界面全部逻辑)
│       ├── style.css                 # 全局样式
│       ├── assets/                   # 静态资源
│       └── components/               # Vue 组件
│
├── docker/
│   ├── docker-compose.yaml           # 中间件编排 (MySQL/ES/Kibana/Qdrant/TEI)
│   ├── elasticsearch/Dockerfile      # ES 8.19 + IK 分词器
│   └── mysql/
│       ├── meta.sql                  # meta 库 DDL + 权限
│       └── dw.sql                    # dw 库 DDL + 示例数据
│
└── logs/                             # 日志输出目录
```

## 工作流程详解

一次完整的用户查询经过以下 13 个节点：

### 1. extract_keywords — 关键词提取
- 使用 jieba 分词对用户问题做 TF-IDF 关键词提取
- 过滤词性：保留名词 (n/ns/nr/nt)、动词 (v)、英文 (eng) 等 14 种词性
- 原始 query 同时作为兜底关键词加入

### 2. recall_column / recall_metric / recall_value — 三路并行检索
- **向量路 (recall_column / recall_metric)**：LLM 扩展关键词 → Embedding 向量化 → Qdrant 相似度搜索 (threshold=0.6, COSINE 距离) → dict 去重
- **全文路 (recall_value)**：LLM 扩展关键词 → ES `match` 查询 (ik_max_word 分词) → dict 去重

### 3. merge_retrieved_info — 三路合并（核心节点）
分 6 个阶段完成数据融合：
1. 字段按 `(column_name, table_id)` 去重
2. 指标的 `relevant_columns` 回补到字段的 `related_metrics`
3. ES 召回的枚举值按 `column_id` 分配到对应字段的 `examples`
4. 字段按 `table_id` 归并到表下
5. 从 MySQL 查询每张表的主键/外键字段并注入
6. 转换为 `TableInfoState` 和 `MetricInfoState` 格式输出

### 4. filter_table / filter_metric — LLM 精筛
- LLM 根据用户问题，从候选表中筛选真正需要的表和字段
- LLM 从候选指标中筛选相关的指标
- 大幅减少无关上下文，提升后续 SQL 生成准确率

### 5. add_extra_context — 注入环境信息
- 当前日期、星期、季度
- MySQL 版本号和 SQL 方言 (通过 `SELECT version()` 获取)

### 6. generate_sql — SQL 生成
- 将所有上下文（表结构、字段、指标、时间、数据库信息）YAML 序列化
- LLM 根据 prompt 模板生成 SQL

### 7. validate_sql — SQL 校验
- 通过 MySQL `EXPLAIN` 语句校验 SQL 语法
- 成功 → 进入 execute_sql
- 失败 + 重试次数 < 3 → 进入 correct_sql
- 失败 + 重试次数 ≥ 3 → 兜底执行（尝试执行看结果）

### 8. correct_sql — SQL 修正
- 携带错误历史、SQL 历史、原始上下文
- LLM 根据错误信息修正 SQL，返回 validate_sql 重新校验（循环）

### 9. execute_sql — 执行查询
- 在 dw 库执行最终 SQL
- 返回结果集 (mappings + fetchall)

### 10. result_formatter — 结果渲染
- LLM 将原始查询结果转换为 Markdown 格式报告
- 包含表格展示、中文表头翻译、核心数据高亮

## 快速开始

### 1. 环境要求

- Python 3.12+
- Docker & Docker Compose
- 8GB+ 内存（运行全部中间件）

### 2. 启动中间件

```bash
cd docker
docker-compose up -d
```

这会启动 MySQL (3306)、Elasticsearch (9200)、Kibana (5601)、Qdrant (6333)、TEI Embedding (9081) 五个服务。

### 3. 安装依赖

```bash
pip install -e .
```

或使用 Poetry：

```bash
poetry install
```

### 4. 配置

编辑 `conf/app_config.yaml`，填入实际的连接信息和 API Key：

```yaml
# conf/app_config.yaml
db_meta:
  host: localhost
  port: 3306
  user: root
  password: "your_password"
  database: meta

db_dw:
  host: localhost
  port: 3306
  user: root
  password: "your_password"
  database: dw

qdrant:
  host: 127.0.0.1
  port: 6333

elasticsearch:
  host: localhost
  port: 9200

embedding:
  api_base: http://localhost:9081

llm:
  model: deepseek-chat
  api_key: "your_deepseek_api_key"
```

### 5. 构建元数据知识库

在启动查询服务之前，需要先将业务元数据（表、字段、指标定义）索引到各数据源：

```bash
python -m app.scripts.build_meta_knowledge -c app/conf/meta_config.yaml
```

这个脚本会：
1. 将表/字段/指标定义写入 MySQL `meta` 库
2. 从 dw 库读取实际字段类型和枚举值
3. 将字段和指标向量化后写入 Qdrant
4. 将标记 `sync=true` 的字段枚举值写入 Elasticsearch

### 6. 启动后端服务

```bash
python main.py
```

服务默认启动在 `http://localhost:8000`。

### 7. 启动前端开发服务器

```bash
cd data-agent-frontend
npm install
npm run dev
```

前端默认启动在 `http://localhost:5173`。Vite 开发服务器已配置代理，所有 `/api/*` 请求会自动转发到后端 `http://localhost:8000`。

> **生产部署**：执行 `npm run build` 生成 `dist/` 目录，将静态文件部署到任意 Web 服务器（Nginx、Caddy 等），同时配置反向代理将 `/api/*` 指向 FastAPI。

## 前端界面

前端是一个基于 **Vue 3 Composition API** 的单页面聊天应用，所有逻辑集中在 `App.vue` 单文件中。

### 消息类型展示

| 消息类型 | 数据字段 | 渲染方式 | 说明 |
|----------|---------|---------|------|
| `text` | `content` | 纯文本气泡 | 简单文字消息 |
| `steps` | `steps` | 彩色圆点列表 | 执行步骤进度（黄色=进行中，绿色=完成，红色=错误） |
| `markdown` | `content` | marked 渲染 + `v-html` | LLM 流式生成的 Markdown 内容，多次 SSE 事件累积拼接 |
| `table` | `columns` + `rows` | HTML `<table>` | 结构化数据表格，英文表头自动转中文 |
| `error` | `content` | 红色文字 | 错误信息展示 |

### SSE 事件处理流程

```
POST /api/query ─→ ReadableStream ─→ 逐行解析
                                        │
                          ┌─ data: {"state": "..."}  → steps 消息
                          ├─ data: {"content": "..."} → markdown 消息 (流式累积)
                          ├─ data: {"result": [...]}  → table 消息
                          ├─ data: {"error": "..."}   → error 消息
                          └─ data: [DONE]             → 流结束标记 (忽略)
```

### Vite 代理配置

```js
// vite.config.js
server: {
  proxy: {
    "/api": {
      target: "http://localhost:8000",   // 后端 FastAPI 地址
      changeOrigin: true,
      configure: (proxy) => {
        proxy.on("proxyReq", (proxyReq) => {
          proxyReq.setHeader("Cache-Control", "no-cache");  // SSE 禁用缓存
          proxyReq.setHeader("Connection", "keep-alive");   // 长连接
        });
      },
    },
  },
}
```

## 前后端通信协议 (SSE)

前端通过单次 HTTP POST 发起查询，后端以 Server-Sent Events 流式返回每个节点的执行状态和最终结果。

### SSE 事件格式

```text
┌─ HTTP POST /api/query
│   Content-Type: application/json
│   Body: {"query": "用户问题"}
│
◄─ HTTP 200 OK
    Content-Type: text/event-stream
    Cache-Control: no-cache
    Connection: keep-alive

    data: {"state": "开始提取关键词"}
    
    data: {"state": "关键词提取完成"}
    
    data: {"state": "生成sql"}
    
    data: {"content": "根据您的查询，2025年华北地区的"}
    
    data: {"content": "成交总额如下："}
    
    data: {"result": [{"地区": "华北", "成交总额": 1234567.89}]}
    
    data: [DONE]
```

### SSE 数据字段说明

| 字段 | 类型 | 说明 | 前端行为 |
|------|------|------|---------|
| `state` | `string` | 当前步骤的描述文字 | 追加到 steps 列表 |
| `content` | `string` | LLM 流式生成的 Markdown 片段 | 累积拼接后实时渲染 |
| `result` | `array 或 string` | 最终结构化查询结果 | 数组→表格，字符串→Markdown |
| `error` | `string` | 错误信息 | 显示红色错误气泡 |
| `[DONE]` | 特殊标记 | SSE 流结束 | 关闭流，停止 loading |

## API 接口

### POST /api/query — 自然语言查询

**请求**：
```json
{
  "query": "查询2025年华北地区的成交总额"
}
```

**响应**：`text/event-stream` (SSE 流)

```text
data: {"state": "开始提取关键词"}
data: {"state": "关键词提取完成"}
data: {"state": "开始搜索字段"}
...
data: {"state": "开始渲染结果"}
data: {"result": "## 查询结果\n\n2025年华北地区的成交总额为 **1,234,567.89 元**\n\n| 地区 | 成交总额 |\n|------|----------|\n| 华北 | 1,234,567.89 元 |"}
```

每个 SSE 事件包含一个 JSON 对象，包含 `state`（进度描述）或 `result`（最终 Markdown 结果）字段。

### GET /api/stream — 测试 SSE 连接

返回模拟的 SSE 流，每 1 秒推送一个阶段状态，用于测试 SSE 连接是否正常。

## 数据模型

### meta 库 — 元数据管理

```
table_info              column_info               metric_info
┌──────────────┐       ┌──────────────┐         ┌──────────────┐
│ id           │◄──────│ table_id (FK)│         │ id           │
│ name         │       │ id           │         │ name         │
│ role(fact/dim)│      │ name         │         │ description  │
│ description  │       │ type         │         │ relevant_columns(JSON)
└──────────────┘       │ role         │         │ alias (JSON) │
        ▲              │ examples(JSON)│        └──────┬───────┘
        │              │ description  │               │
        │              │ alias (JSON) │               │
        │              └──────┬───────┘               │
        │                     │                       │
        │              column_metric                  │
        │              ┌──────────────┐               │
        │              │ column_id(FK)│───────────────┘
        │              │ metric_id(FK)│
        │              └──────────────┘
        │
  事实表 (fact) / 维度表 (dim)
```

### dw 库 — 数据仓库

存放实际的业务数据：维度表（`dim_region`、`dim_customer`、`dim_product`、`dim_date`）和事实表（`fact_order` 等）。

### Qdrant 向量索引

| Collection | 维度 | 距离 | 用途 |
|------------|------|------|------|
| `data-agent-column` | 1024 | COSINE | 字段语义检索 (name/description/alias 分别向量化) |
| `data-agent-metrics` | 1024 | COSINE | 指标语义检索 (name/description/alias 分别向量化) |

### Elasticsearch 全文索引

| Index | 分词器 | 用途 |
|-------|--------|------|
| `data-agent-values` | ik_max_word | 字段枚举值全文检索 |

## 配置说明

### 应用配置 (`conf/app_config.py`)

基于 OmegaConf 的类型安全配置系统。定义 `AppConfig` dataclass 作为 schema，运行时从 `conf/app_config.yaml` 加载值并 merge。

核心配置项：

- `db_meta` / `db_dw`：MySQL 连接信息（host/port/user/password/database）
- `qdrant`：向量数据库地址和 embedding 维度
- `elasticsearch`：ES 连接地址和索引名
- `embedding`：HuggingFace TEI 服务地址和模型名
- `llm`：LLM 模型名和 API Key

### 元数据配置 (`app/conf/meta_config.yaml`)

知识库构建的输入文件，定义业务表和指标：

```yaml
tables:
  - name: fact_order
    role: fact
    description: 订单事实表
    columns:
      - name: order_amount
        role: measure
        description: 订单金额
        sync: true        # 是否将枚举值同步到 ES
      - name: region_id
        role: key
        description: 地区ID，关联dim_region表
  - name: dim_region
    role: dim
    description: 地区维度表
    columns:
      - name: region_name
        role: dimension
        description: 地区名称，如华北、华东
        sync: true

metrics:
  - name: GMV
    description: 成交总额
    relevant_columns:
      - fact_order.order_amount
    alias:
      - 销售额
      - 交易总额
```

## Prompt 模板管理

所有 LLM 调用的 prompt 模板集中在 `prompts/` 目录，以 `.prompt` 为后缀。通过 `load_prompt("template_name")` 加载。

| 模板文件 | 调用节点 | 输入变量 | 输出格式 |
|----------|---------|---------|---------|
| `extend_keywords_for_column_recall.prompt` | recall_column | query | JSON 字符串数组 |
| `extend_keywords_for_metric_recall.prompt` | recall_metric | query | JSON 字符串数组 |
| `extend_keywords_for_value_recall.prompt` | recall_value | query | JSON 字符串数组 |
| `filter_table_info.prompt` | filter_table | query, table_info | JSON 对象 |
| `filter_metric_info.prompt` | filter_metric | query, metric_info | JSON 字符串数组 |
| `generate_sql.prompt` | generate_sql | query, table_info, metric_info, date_info, db_info | 纯文本 SQL |
| `correct_sql.prompt` | correct_sql | query, table_info, metric_info, date_info, db_info, error_sql, error | 纯文本 SQL |
| `prompt_templates.prompt` | result_formatter | query, sql_message | Markdown |

## 开发指南

### 代码规范

参考项目根目录的 `CLAUDE.md`：

- 交流语言使用简体中文
- 专业术语保留英文（如 Transformer、SQLAlchemy、Qdrant）
- Python 代码注释使用中文
- LLM Prompt 模板使用中文描述

### 添加新节点

1. 在 `app/agent/nodes/` 下创建新文件，实现异步函数
2. 函数签名：`async def node_name(state: DataAgentState, runtime: Runtime[DataAgentContext])`
3. 如需流式输出进度，使用 `writer = runtime.stream_writer` 并调用 `writer({"state": "描述"})`
4. 如需写入状态，直接 `return {"field": value}`
5. 在 `app/agent/graph.py` 中注册节点并添加边

### 添加新 Prompt 模板

1. 在 `prompts/` 目录下创建 `.prompt` 文件
2. 使用 `{variable_name}` 标记变量占位符（字面量 `{}` 需转义为 `{{}}`）
3. 通过 `load_prompt("文件名不含后缀")` 在节点中加载

### 日志追踪

日志系统基于 Loguru，自动为每个请求注入 `request_id`：

```python
from app.core.log import logger
logger.info("这是一条带 request_id 的日志")
```

输出格式：`2026-06-12 18:44:28.873 | INFO | request_id - uuid | 文件:函数:行号 - 消息`

## License

MIT