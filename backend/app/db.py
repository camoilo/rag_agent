"""业务数据库（SQLite）：连接管理与建表。

表结构：
- sessions   会话
- documents  上传文档的元数据与向量化状态
- messages   聊天消息（assistant 消息含引用 JSON）
- usage_log  全局 token 用量与耗时
"""

from contextlib import asynccontextmanager
from datetime import datetime
import aiosqlite

from app.config import APP_DB, DATA_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL DEFAULT '新会话',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    document_name TEXT NOT NULL,
    status      TEXT NOT NULL,          -- processing / ready / empty / failed
    error       TEXT,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role       TEXT NOT NULL,           -- user / assistant
    content    TEXT NOT NULL,
    citations  TEXT,                    -- 引用来源 JSON（仅 assistant 消息）
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);

CREATE TABLE IF NOT EXISTS usage_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    elapsed_ms        INTEGER NOT NULL DEFAULT 0,
    model             TEXT,
    created_at        TEXT NOT NULL
);
"""


def now() -> str:
    """统一的时间戳格式（本地时间，ISO 秒级）。"""
    return datetime.now().isoformat(timespec="seconds")


@asynccontextmanager
async def connect():
    """按操作获取连接，用完即关。"""
    db = await aiosqlite.connect(APP_DB)
    db.row_factory = aiosqlite.Row
    try:
        # 并发写入时排队等待而非直接报 database is locked
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("PRAGMA synchronous=NORMAL")  # WAL 下的推荐级别
        yield db
    finally:
        await db.close()


async def init_db():
    """启动时创建数据目录与全部表。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with connect() as db:
        await db.execute("PRAGMA journal_mode=WAL")  # 持久化到库文件，提升读写并发
        await db.executescript(SCHEMA)
        await db.commit()


async def fail_interrupted_documents() -> list[str]:
    """启动对账：遗留 processing 文档置为失败，并返回其 id 供清理残留向量。"""
    async with connect() as db:
        rows = await (
            await db.execute("SELECT id FROM documents WHERE status = 'processing'")
        ).fetchall()
        await db.execute(
            "UPDATE documents SET status = 'failed', error = ? WHERE status = 'processing'",
            ("服务重启导致解析中断，请重新解析或重新上传",),
        )
        await db.commit()
    return [row["id"] for row in rows]


async def failed_document_ids() -> list[str]:
    """全部失败文档 id：失败文档不应保留向量，启动时需清理其残留分块。"""
    async with connect() as db:
        rows = await (
            await db.execute("SELECT id FROM documents WHERE status = 'failed'")
        ).fetchall()
    return [row["id"] for row in rows]


async def session_exists(session_id: str) -> bool:
    """判断会话是否存在。"""
    async with connect() as db:
        row = await (
            await db.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,))
        ).fetchone()
        return row is not None
