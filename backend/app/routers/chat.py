"""聊天 SSE 路由：流式问答、引用回传与消息入库。

事件序列（text/event-stream，每帧 `data: {json}\n\n`）：
- token  正文增量，可能多次
- done   正常结束，携带引用列表 / 耗时 / token 用量
- error  异常信息
"""

import json
import logging
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
logger = logging.getLogger(__name__)


@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    """流式问答。会话不存在时在建立流之前返回 404。"""
    if not await session_exists(request.session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    logger.info("收到问答请求 session=%s question_len=%d", request.session_id, len(request.question))

    return StreamingResponse(
        _stream(request.session_id, request.question),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # nginx禁用缓冲
    )


async def _stream(session_id: str, question: str) -> AsyncIterator[str]:
    """执行 agent 并以 SSE 输出，然后落库；取消或异常时不写入半截回答。"""
    started = time.perf_counter()
    collected = CitationCollector()
    token = citations_var.set(collected)  # 本轮请求的引用收集器
    parts: list[str] = []
    prompt_tokens = 0
    completion_tokens = 0
    completed = False
    answer = ""
    citations: list[Citation] = []
    try:
        async for chunk, _metadata in get_agent().astream(
            input={"messages": [HumanMessage(content=question)]},
            config={"configurable": {"thread_id": session_id}},
            stream_mode="messages",
        ):
            # 只处理 AI 消息块：转发正文增量，累加各次模型调用的流式用量（检索决策与最终生成是两次独立的调用）
            if isinstance(chunk, AIMessageChunk):
                if isinstance(chunk.content, str) and chunk.content:
                    parts.append(chunk.content)
                    yield _event({"type": "token", "content": chunk.content})
                if chunk.usage_metadata:
                    prompt_tokens += chunk.usage_metadata.get("input_tokens", 0)
                    completion_tokens += chunk.usage_metadata.get("output_tokens", 0)

        completed = True  # 生成已完成：即使推送末帧时客户端断开，也应正常落库。
        answer = "".join(parts)
        citations = _cited_citations(answer, collected.items)
        yield _event({
            "type": "done",
            "citations": [c.model_dump() for c in citations],
            "elapsed_ms": _elapsed_ms(started),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        })
    except Exception as exc:
        logger.exception("问答失败 session=%s", session_id)
        yield _event({"type": "error", "detail": f"{type(exc).__name__}: {exc}"})
    finally:
        citations_var.reset(token)
        # 仅完整生成后一次性提交整轮问答：停止、断线或异常时不产生"有问无答"的半轮记录
        if completed:
            try:
                await _save_turn(
                    session_id,
                    question=question,
                    answer=answer,
                    citations=citations,
                    elapsed_ms=_elapsed_ms(started),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )
            except Exception:
                logger.exception("问答落库失败 session=%s", session_id)
        else:
            logger.info(
                "问答未完成 session=%s elapsed=%dms partial_len=%d（客户端中断或异常）",
                session_id,
                _elapsed_ms(started),
                len("".join(parts)),
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


async def _save_turn(
    session_id: str,
    question: str,
    answer: str,
    citations: list[Citation],
    elapsed_ms: int,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    """
    一次性提交一轮问答：用户消息、assistant 消息与 token 用量在同一事务中写入。
    回答为空时只记录用量，不写消息，避免留下有问无答的记录。
    """
    settings = get_settings()
    async with connect() as db:
        if answer:
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
            if user_count == 0:
                await db.execute(
                    "UPDATE sessions SET title = ? WHERE id = ?", (question[:30], session_id)
                )
        if prompt_tokens or completion_tokens:
            await db.execute(
                "INSERT INTO usage_log (prompt_tokens, completion_tokens, elapsed_ms, model, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (prompt_tokens, completion_tokens, elapsed_ms, settings.chat_model, now()),
            )
        await db.commit()
    logger.info(
        "问答落库完成 session=%s answer_len=%d citations=%d prompt_tokens=%d completion_tokens=%d elapsed=%dms",
        session_id,
        len(answer),
        len(citations),
        prompt_tokens,
        completion_tokens,
        elapsed_ms,
    )
