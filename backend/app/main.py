"""FastAPI 入口：应用实例、中间件、健康检查与全局统计。"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.agent import close_agent, init_agent
from app.db import connect, init_db
from app.routers import chat, documents, sessions


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期：启动时初始化业务库与记忆库，停止时关闭记忆连接。"""
    await init_db()
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
