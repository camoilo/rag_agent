"""API 请求/响应模型。"""

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """引用来源。"""

    index: int
    source: str
    page: int | None = None
    snippet: str    # 截取的短文本片段


class SessionOut(BaseModel):
    """会话。"""

    id: str
    title: str
    created_at: str


class MessageOut(BaseModel):
    """聊天消息。"""

    id: int
    role: str
    content: str
    citations: list[Citation] = Field(default_factory=list) # 每次生成新的空列表
    created_at: str


class SessionRenameRequest(BaseModel):
    """重命名会话的请求。"""

    title: str = Field(min_length=1, max_length=30)
