"""会话管理路由：列表 / 新建 / 重命名 / 删除 / 历史消息。"""

import json
import logging
import uuid
from typing import Annotated
from fastapi import APIRouter, HTTPException, Path

from app.core.agent import get_memory_saver
from app.db import connect, now, session_exists
from app.schemas import Citation, MessageOut, SessionOut, SessionRenameRequest


router = APIRouter(prefix="/api/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)

_SESSION_COLUMNS = "id, title, created_at"


@router.get("")
async def list_sessions() -> list[SessionOut]:
    """全部会话，按最近活动时间倒序：新建或刚完成问答的会话排在前面。"""
    async with connect() as db:
        rows = await (
            await db.execute(
                f"SELECT {_SESSION_COLUMNS} FROM sessions s"
                " ORDER BY COALESCE("
                "   (SELECT MAX(m.created_at) FROM messages m WHERE m.session_id = s.id),"
                "   s.created_at"
                " ) DESC, s.rowid DESC"
            )
        ).fetchall()
    return [SessionOut.model_validate(dict(row)) for row in rows]


@router.post("", status_code=201)
async def create_session() -> SessionOut:
    """新建会话，标题默认"新会话"。"""
    session = SessionOut(id=uuid.uuid4().hex, title="新会话", created_at=now())
    async with connect() as db:
        await db.execute(
            f"INSERT INTO sessions ({_SESSION_COLUMNS}) VALUES (?, ?, ?)",
            (session.id, session.title, session.created_at),
        )
        await db.commit()
    logger.info("新建会话 id=%s", session.id)
    return session


@router.get("/{session_id}/messages")
async def get_messages(session_id: Annotated[str, Path()]) -> list[MessageOut]:
    """会话的历史消息，按时间正序。"""
    if not await session_exists(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    async with connect() as db:
        rows = await (
            await db.execute(
                "SELECT id, role, content, citations, created_at FROM messages"
                " WHERE session_id = ? ORDER BY id",
                (session_id,),
            )
        ).fetchall()
    return [
        MessageOut(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            citations=[Citation.model_validate(c) for c in json.loads(row["citations"])]
            if row["citations"]
            else [],
            created_at=row["created_at"],
        )
        for row in rows
    ]


@router.patch("/{session_id}")
async def rename_session(session_id: Annotated[str, Path()], request: SessionRenameRequest) -> SessionOut:
    """重命名会话。"""
    async with connect() as db:
        cursor = await db.execute("UPDATE sessions SET title = ? WHERE id = ?", (request.title, session_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="会话不存在")
        await db.commit()
        row = await (
            await db.execute(
                f"SELECT {_SESSION_COLUMNS} FROM sessions WHERE id = ?", (session_id,)
            )
        ).fetchone()
    logger.info("重命名会话 id=%s title=%s", session_id, request.title)
    return SessionOut.model_validate(dict(row))


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: Annotated[str, Path()]):
    """删除会话：业务库会话 + 记忆库对应线程。"""
    async with connect() as db:
        await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor = await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="会话不存在")  # 未commit，messages的删除会回滚
        await db.commit()
    try:
        await get_memory_saver().adelete_thread(session_id)
    except Exception:
        logger.exception("删除会话 id=%s 成功，但清理记忆失败", session_id)
    else:
        logger.info("删除会话 id=%s（业务记录与记忆已清理）", session_id)
