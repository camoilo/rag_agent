# RAG 知识库助手

前后端分离的检索增强问答（RAG）应用：上传文档构建知识库，MinerU 在线解析文档，切分写入Chroma向量库，基于 LangChain 的 Agent 进行流式问答，回答附带引用来源。

## 功能

- **知识库管理**：上传 PDF / Office 文档 / 图片 / `.txt` / `.md`（大小上限随解析模式：precision ≤200MB、flash ≤10MB），由 MinerU 在线解析为 Markdown 后切分、向量化入库；失败可重新解析；支持删除（联动清理向量与文件）
- **混合检索**：向量检索（Chroma）+ BM25（jieba 分词 + rank_bm25），RRF 融合排序，中文召回效果优于单一向量检索
- **流式问答**：SSE 逐 token 输出，回答中 `[n]` 标注引用来源，附来源文件与原文片段
- **会话记忆**：LangGraph checkpointer 持久化每个会话的对话上下文，删除会话时联动清空
- **用量统计**：会话数、文档数、消息数、token 用量一览

## 技术栈

| 层       | 技术                                                              |
|----------|-------------------------------------------------------------------|
| 后端框架 | Python 3.13 · FastAPI · uvicorn                                   |
| Agent    | LangChain（`create_agent`）· LangGraph（`AsyncSqliteSaver` 记忆） |
| 模型     | OpenAI 协议兼容接口（默认阿里云百炼 qwen 系列）                   |
| 文档解析 | MinerU 在线 API（`langchain-mineru` 的 `MinerULoader`）           |
| 向量库   | Chroma（`langchain-chroma`）                                      |
| 检索     | 向量 + jieba + rank_bm25（RRF 融合）                              |
| 业务存储 | SQLite（aiosqlite 原生 SQL）                                      |
| 前端     | Vue 3 · Vite · Element Plus · Pinia · axios                       |
| 渲染     | marked + DOMPurify                                                |
| 部署     | Docker Compose（前端 nginx + 后端 uvicorn）                       |

## 项目结构

```
rag_agent/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口与生命周期
│   │   ├── config.py            # 环境变量与存储路径
│   │   ├── db.py                # 业务库连接与操作
│   │   ├── schemas.py           # Pydantic 请求/响应模型
│   │   ├── routers/
│   │   │   ├── sessions.py      # 会话 CRUD
│   │   │   ├── documents.py     # 上传/列表/删除
│   │   │   └── chat.py          # SSE 流式问答
│   │   └── core/
│   │       ├── document_processing.py  # MinerU 解析、切分、向量化入库
│   │       ├── vector_store.py        # Chroma 封装
│   │       ├── retriever.py           # 混合检索
│   │       └── agent.py               # LLM、工具与 Agent 构建
│   ├── data/                    # 运行时数据（git 忽略）
│   │   ├── app.db               # 业务库（sessions/documents/messages/usage_log）
│   │   ├── agent_memory/        # LangGraph 记忆库（与会话绑定）
│   │   ├── chroma/              # 向量库
│   │   └── uploads/             # 上传原件
│   ├── Dockerfile
│   ├── .env.example
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/                 # http.js（REST）· sse.js（流式）
│   │   ├── stores/              # chat.js · documents.js（Pinia）
│   │   ├── components/         # chat/ · knowledge/ 组件
│   │   ├── views/               # ChatView · KnowledgeView
│   │   └── router/
│   ├── nginx.conf               # 容器版站点配置（反代 + SSE）
│   └── Dockerfile
├── docker-compose.yml
├── README.md
└── LICENSE
```

## 快速开始

### 方式一：本地开发

**后端**（Python 3.13+，依赖管理用 [uv](https://docs.astral.sh/uv/)）：

```bash
cd backend
cp .env.example .env        # 填入 OPENAI_API_KEY 与 MINERU_TOKEN
uv sync
uv run uvicorn app.main:app --reload --port 8000   # 单 worker，勿加 --workers
```

**前端**（Node 20+）：

```bash
cd frontend
npm ci
npm run dev                # http://localhost:5173，/api 代理到 8000
```

### 方式二：Docker 部署

```bash
# 准备 backend/.env
docker compose up -d --build
# 访问 http://localhost/（默认仅监听本机）
```

- 前端容器（nginx:80）反代后端容器，SSE 已配置无缓冲转发
- 后端必须单 worker：启动时会把上一进程遗留的 `processing` 文档标记为失败，多 worker 会误杀其他进程正在解析的任务，请勿给 uvicorn 加 `--workers`
- 默认端口仅绑定 `127.0.0.1`；确需局域网访问时把 `docker-compose.yml` 改为 `"80:80"`，并在 nginx / 反代层加访问控制（应用本身无鉴权）
- 数据持久化于 `rag-data` 卷（业务库 / 记忆库 / 向量库 / 上传文件）
- `docker compose down` 停止（数据保留），`docker compose down -v` 连同数据一起删除

## 配置

### 环境变量（`backend/.env`）

| 变量             | 必填 | 说明                                                                                          |
|------------------|------|-----------------------------------------------------------------------------------------------|
| `OPENAI_API_KEY` | 是   | OpenAI 协议兼容平台的 API Key                                                                 |
| `MINERU_TOKEN`   | 是   | MinerU 解析 token（[MinerU token申请](https://mineru.net/apiManage/token)）；flash 模式可留空 |

### 应用配置（`backend/app/config.py`）

| 变量                 | 默认值                                        | 说明                                            |
|----------------------|-----------------------------------------------|-------------------------------------------------|
| `CORS_ORIGINS`       | `http://localhost:5173,http://127.0.0.1:5173` | 允许的跨域来源，逗号分隔；生产由 nginx 同源反代 |
| `OPENAI_BASE_URL`    | 阿里云百炼 compatible-mode 接口               | 对话模型接口                                    |
| `CHAT_MODEL`         | `qwen3.8-flash`                               | 对话模型名                                      |
| `EMBEDDING_BASE_URL` | 同 `OPENAI_BASE_URL`                          | 向量模型接口                                    |
| `EMBEDDING_MODEL`    | `qwen3.7-text-embedding-flash`                | 向量模型名                                      |
| `EMBED_BATCH_SIZE`   | `20`                                          | 单次嵌入请求的文本行数                          |
| `LLM_TIMEOUT`        | `60`                                          | 对话模型网络超时（秒）                          |
| `EMBEDDING_TIMEOUT`  | `30`                                          | 向量化请求网络超时（秒）                        |
| `MAX_RETRIES`        | `2`                                           | 网络错误或超时的重试次数                        |
| `MINERU_MODE`        | `precision`                                   | 解析模式；flash 免 token 但限 ≤10MB / ≤20 页    |
| `MINERU_LANGUAGE`    | `ch`                                          | 文档语言                                        |
| `MINERU_OCR`         | `false`                                       | 扫描件开启 OCR；仅 precision 生效               |
| `MINERU_FORMULA`     | `true`                                        | 公式识别；仅 precision 生效                     |
| `MINERU_TABLE`       | `true`                                        | 表格识别；仅 precision 生效                     |
| `MINERU_TIMEOUT`     | `600`                                         | 单文件解析等待上限（秒）                        |
| `CHUNK_SIZE`         | `800`                                         | 切分块大小                                      |
| `CHUNK_OVERLAP`      | `100`                                         | 切分重叠长度                                    |
| `TOP_K`              | `4`                                           | 最终返回的引用块数                              |
| `USE_HYBRID`         | `true`                                        | 混合检索；`false` 为纯向量                      |
| `CANDIDATE_K`        | `20`                                          | 混合检索每路召回候选数                          |

除了直接更改这些配置，也可用同名大写环境变量临时覆盖。

## API 概览

| 方法   | 路径                          | 说明                                            |
|--------|-------------------------------|-------------------------------------------------|
| GET    | `/api/health`                 | 依赖可用性检查（业务库 / 向量库，异常返回 503） |
| GET    | `/api/stats`                  | 用量统计                                        |
| GET    | `/api/config`                 | 上传约束（当前模式 / 后缀 / 大小与页数上限）    |
| POST   | `/api/sessions`               | 新建会话                                        |
| GET    | `/api/sessions`               | 会话列表                                        |
| PATCH  | `/api/sessions/{id}`          | 重命名                                          |
| DELETE | `/api/sessions/{id}`          | 删除（联动清空记忆）                            |
| GET    | `/api/sessions/{id}/messages` | 历史消息                                        |
| POST   | `/api/documents`              | 上传文档（multipart）                           |
| GET    | `/api/documents`              | 文档列表                                        |
| POST   | `/api/documents/{id}/retry`   | 重新解析失败文档（需原文件）                    |
| DELETE | `/api/documents/{id}`         | 删除（联动清理向量与文件）                      |
| POST   | `/api/chat`                   | SSE 流式问答                                    |

交互式文档：后端启动后访问 `http://localhost:8000/docs`。

## 设计要点

- **记忆与业务隔离**：会话记忆存独立 SQLite（`agent_memory.db`），与业务库（`app.db`）分离，避免锁竞争，会话间记忆互不可见。
- **模型自主检索**：知识检索封装为 `knowledge_search` 工具，由模型决定是否调用；系统提示词要求先检索再回答、引用标注 `[n]`、无结果时如实说明。
- **删除即清理**：删会话 → 同步清空该会话记忆；删文档 → 直接清理业务记录、向量块与上传原件。
- **解析交给 MinerU**：文档经 MinerU 在线 API 解析为 Markdown（表格、公式一并保留）后入库，文件会上传至 mineru.net。

## License

[MIT](LICENSE)
