"""Agent：LLM、knowledge_search 工具与带会话记忆的 agent 实例。"""

from contextvars import ContextVar
from functools import lru_cache
from typing import Annotated
import aiosqlite
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph.state import CompiledStateGraph

from app.config import MEMORY_DIR, MEMORY_DB, get_settings
from app.core.retriever import retrieve
from app.schemas import Citation

# 当前请求的引用收集器：chat 路由每轮 set 一个新列表，
# 工具执行时往里 append，流结束后随 done 事件下发
citations_var: ContextVar[list[Citation]] = ContextVar("citations")

_SYSTEM_PROMPT = """你是本地知识库的问答助手，用中文回答，使用 Markdown 格式。
回答规则：
1. 涉及知识库内容的问题，先调用 knowledge_search 工具检索，再基于检索结果回答，不要凭空编造知识库内容。
2. 回答中使用 [n] 标注信息来源，n 对应检索结果中的编号。
3. 检索无结果时，如实说明知识库中未找到相关内容；如基于常识补充，须注明该部分非来自知识库。
4. 闲聊或与知识库无关的问题直接回答。
"""


@lru_cache
def get_llm() -> ChatOpenAI:
    """聊天模型。"""
    settings = get_settings()
    return ChatOpenAI(
        model=settings.chat_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        stream_usage=True,
    )


@tool
def knowledge_search(query: Annotated[str, "检索查询，使用与提问一致的语言"]) -> str:
    """检索本地知识库，返回与查询最相关的文档片段。回答知识类问题前应先调用本工具。"""
    chunks = retrieve(query)
    if not chunks:
        return "未检索到相关内容。"

    citations = citations_var.get(None)
    blocks = []
    for i, chunk in enumerate(chunks, start=1):
        metadata = chunk.metadata
        citation = Citation(
            index=i,
            source=metadata.get("source", "未知来源"),
            page=metadata.get("page"),
            snippet=chunk.page_content[:100],
        )
        if citations is not None:
            citations.append(citation)
        blocks.append(
            f"[{citation.index}]（来源：{citation.source}"
            + (f"，第 {citation.page} 页" if citation.page else "")
            + "）\n"
            + chunk.page_content
        )
    return "\n\n".join(blocks)


def build_agent(checkpointer: AsyncSqliteSaver):
    """创建 agent：模型自主决定是否/如何检索，记忆按 thread_id 持久化。"""
    return create_agent(
        model=get_llm(),
        tools=[knowledge_search],
        system_prompt=_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )


_saver: AsyncSqliteSaver | None = None
_agent: CompiledStateGraph | None = None


async def init_agent():
    """初始化记忆库连接并构建 agent（应用启动时调用）。"""
    global _saver, _agent
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(MEMORY_DB))
    _saver = AsyncSqliteSaver(conn)
    await _saver.setup()
    _agent = build_agent(_saver)


async def close_agent():
    """关闭记忆库连接（应用停止时调用）。"""
    global _saver, _agent
    if _saver is not None:
        await _saver.conn.close()
        _saver = None
        _agent = None


def get_agent() -> CompiledStateGraph:
    """取 agent 实例；未初始化（生命周期未启动）时抛错。"""
    if _agent is None:
        raise RuntimeError("agent 未初始化")
    return _agent


def get_memory_saver() -> AsyncSqliteSaver:
    """取记忆库 saver；用于按 thread_id 清理记忆。"""
    if _saver is None:
        raise RuntimeError("记忆库未初始化")
    return _saver
