"""FastAPI 入口：应用实例、中间件、健康检查与全局统计。"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.agent import close_agent, init_agent
from app.core.document_processing import allowed_suffixes, upload_limits
from app.db import connect, fail_interrupted_documents, init_db
from app.routers import chat, documents, sessions


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期：启动时初始化业务库与记忆库，停止时关闭记忆连接。"""
    await init_db()
    await fail_interrupted_documents()
    await init_agent()
    try:
        yield
    finally:
        await close_agent()


app = FastAPI(
    title="RAG 知识库助手",
    version="0.1.0",
    lifespan=lifespan,
)

# 仅允许配置内的来源跨域：生产经 nginx 同源反代，开发走 vite 代理，均无需 " * "
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in get_settings().cors_origins.split(",") if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(documents.router)
app.include_router(chat.router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    """健康检查。"""
    return {"status": "ok"}


@app.get("/api/config")
async def upload_config() -> dict:
    """前端上传约束：当前解析模式、允许格式、大小与页数上限。"""
    max_bytes, max_pages = upload_limits()
    return {
        "mineru_mode": get_settings().mineru_mode,
        "allowed_suffixes": sorted(allowed_suffixes()),
        "max_upload_bytes": max_bytes,
        "max_pages": max_pages,
    }


@app.get("/api/stats")
async def stats() -> dict[str, int]:
    """全局统计：会话 / 文档 / 消息数量与累计 token 用量。"""
    async with connect() as db:

        async def scalar(sql: str) -> int:
            row = await (await db.execute(sql)).fetchone()
            return row[0]

        return {
            "sessions": await scalar("SELECT COUNT(*) FROM sessions"),
            "documents": await scalar("SELECT COUNT(*) FROM documents"),
            "ready_documents": await scalar("SELECT COUNT(*) FROM documents WHERE status = 'ready'"),
            "messages": await scalar("SELECT COUNT(*) FROM messages"),
            "prompt_tokens": await scalar("SELECT COALESCE(SUM(prompt_tokens), 0) FROM usage_log"),
            "completion_tokens": await scalar("SELECT COALESCE(SUM(completion_tokens), 0) FROM usage_log"),
        }
