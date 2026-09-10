"""业务数据库（SQLite）：连接管理与建表。

表结构：
- sessions   会话
- documents  上传文档的元数据与向量化状态
- messages   聊天消息（assistant 消息含引用 JSON）
- usage_log  每轮对话的 token 用量与耗时
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
    session_id        TEXT,
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
        yield db
    finally:
        await db.close()


async def init_db():
    """启动时创建数据目录与全部表。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with connect() as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def session_exists(session_id: str) -> bool:
    """判断会话是否存在。"""
    async with connect() as db:
        row = await (
            await db.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,))
        ).fetchone()
        return row is not None
