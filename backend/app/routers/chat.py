"""聊天 SSE 路由：流式问答、引用回传与消息入库。

事件序列（text/event-stream，每帧 `data: {json}\n\n`）：
- token  正文增量，可能多次
- done   正常结束，携带引用列表 / 耗时 / token 用量
- error  异常信息
"""

import json
import re
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessageChunk, HumanMessage

from app.config import get_settings
from app.core.agent import CitationCollector, citations_var, get_agent
from app.db import connect, now, session_exists
from app.schemas import ChatRequest, Citation

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    """流式问答。会话不存在时在建立流之前返回 404。"""
    if not await session_exists(request.session_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    # 若是首条消息，同时将其设为会话标题
    await _save_user_message(request.session_id, request.question)

    return StreamingResponse(
        _stream(request.session_id, request.question),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # nginx禁用缓冲
    )


async def _stream(session_id: str, question: str) -> AsyncIterator[str]:
    """执行 agent 并以 SSE 输出，然后落库。"""
    started = time.perf_counter()
    collected = CitationCollector()
    token = citations_var.set(collected)  # 本轮请求的引用收集器
    parts: list[str] = []
    usage: dict = {}
    try:
        async for chunk, _metadata in get_agent().astream(
            input={"messages": [HumanMessage(content=question)]},
            config={"configurable": {"thread_id": session_id}},
            stream_mode="messages",
        ):
            # 只处理 AI 消息块：转发正文增量（排除工具调用的决策块与 ToolMessage），
            # 并取末尾块上的流式用量
            if isinstance(chunk, AIMessageChunk):
                if isinstance(chunk.content, str) and chunk.content:
                    parts.append(chunk.content)
                    yield _event({"type": "token", "content": chunk.content})
                if chunk.usage_metadata:
                    usage = dict(chunk.usage_metadata)

        answer = "".join(parts)
        yield _event({
            "type": "done",
            "citations": [c.model_dump() for c in _cited_citations(answer, collected.items)],
            "elapsed_ms": _elapsed_ms(started),
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
        })
    except Exception as exc:
        yield _event({"type": "error", "detail": f"{type(exc).__name__}: {exc}"})
    finally:
        citations_var.reset(token)
        answer = "".join(parts)
        await _save_assistant(
            session_id,
            answer=answer,
            citations=_cited_citations(answer, collected.items),
            elapsed_ms=_elapsed_ms(started),
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
        )


_CITATION_MARK = re.compile(r"\[([0-9]+)\]")


def _cited_citations(answer: str, citations: list[Citation]) -> list[Citation]:
    """只保留答案中实际引用到的来源；答案未标注 [n] 时回退为全部来源。"""
    cited = [c for c in citations if c.index in {int(n) for n in _CITATION_MARK.findall(answer)}]
    return cited or citations


def _event(payload: dict) -> str:
    """构造一帧 SSE 事件。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


async def _save_user_message(session_id: str, question: str) -> None:
    """落库用户消息；首条消息同时更新会话标题。"""
    async with connect() as db:
        user_count = (
            await (
                await db.execute(
                    "SELECT COUNT(*) FROM messages WHERE session_id = ? AND role = 'user'",
                    (session_id,),
                )
            ).fetchone()
        )[0]
        await db.execute(
            "INSERT INTO messages (session_id, role, content, created_at)"
            " SELECT ?, 'user', ?, ?"
            " WHERE EXISTS (SELECT 1 FROM sessions WHERE id = ?)",
            (session_id, question, now(), session_id),
        )
        if user_count == 0:
            await db.execute(
                "UPDATE sessions SET title = ? WHERE id = ?", (question[:30], session_id)
            )
        await db.commit()


async def _save_assistant(
    session_id: str,
    answer: str,
    citations: list[Citation],
    elapsed_ms: int,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    """落库 assistant 消息（含引用）与 token 用量；内容为空时跳过对应行。"""
    settings = get_settings()
    async with connect() as db:
        if answer:
            await db.execute(
                "INSERT INTO messages (session_id, role, content, citations, created_at)"
                " SELECT ?, 'assistant', ?, ?, ?"
                " WHERE EXISTS (SELECT 1 FROM sessions WHERE id = ?)",
                (
                    session_id,
                    answer,
                    json.dumps([c.model_dump() for c in citations], ensure_ascii=False),
                    now(),
                    session_id,
                ),
            )
        if prompt_tokens or completion_tokens:
            await db.execute(
                "INSERT INTO usage_log (prompt_tokens, completion_tokens, elapsed_ms, model, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (prompt_tokens, completion_tokens, elapsed_ms, settings.chat_model, now()),
            )
        await db.commit()
