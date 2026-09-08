"""会话管理路由：列表 / 新建 / 重命名 / 删除 / 历史消息。"""

import json
import uuid
from typing import Annotated
from fastapi import APIRouter, HTTPException, Path

from app.db import connect, now
from app.schemas import Citation, MessageOut, SessionOut, SessionRenameRequest


router = APIRouter(prefix="/api/sessions", tags=["sessions"])

_SESSION_COLUMNS = "id, title, created_at"


async def _ensure_session(db, session_id: str) -> None:
    """会话不存在时抛 404。"""
    row = await (
        await db.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,))
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="会话不存在")


@router.get("")
async def list_sessions() -> list[SessionOut]:
    """全部会话，新创建的在前。"""
    async with connect() as db:
        rows = await (
            await db.execute(f"SELECT {_SESSION_COLUMNS} FROM sessions ORDER BY created_at DESC, rowid DESC")
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
    return session


@router.get("/{session_id}/messages")
async def get_messages(session_id: Annotated[str, Path()]) -> list[MessageOut]:
    """会话的历史消息，按时间正序。"""
    async with connect() as db:
        await _ensure_session(db, session_id)
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
    return SessionOut.model_validate(dict(row))


@router.delete("/{session_id}", status_code=204)    # 204无返回内容
async def delete_session(session_id: Annotated[str, Path()]) -> None:
    """删除会话及其全部消息。"""
    async with connect() as db:
        await _ensure_session(db, session_id)
        await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await db.commit()
