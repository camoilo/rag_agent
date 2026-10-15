"""文档处理：解析 → 切分 → 向量化入库。
"""

import asyncio
from pathlib import Path

from langchain_core.documents import Document
from langchain_mineru import MinerULoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings
from app.core.vector_store import get_vector_store

# MinerU 无法解析的纯文本格式，直接本地读取
LOCAL_SUFFIXES = {".txt", ".md"}

# MinerU 各解析模式支持的格式
MINERU_SUFFIXES: dict[str, set[str]] = {
    "precision": {
        ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".html",
        ".png", ".jpg", ".jpeg", ".jp2", ".webp", ".gif", ".bmp",
    },
    "flash": {
        ".pdf", ".docx", ".pptx", ".xls", ".xlsx",
        ".png", ".jpg", ".jpeg", ".jp2", ".webp", ".gif", ".bmp",
    },
}


def _mineru_mode() -> str:
    """当前解析模式；配置非法时立即报错。"""
    mode = get_settings().mineru_mode
    if mode not in MINERU_SUFFIXES:
        raise RuntimeError(f"mineru_mode 配置无效：{mode}，可选 {' / '.join(MINERU_SUFFIXES)}")
    return mode


def allowed_suffixes() -> set[str]:
    """当前解析模式允许上传的格式（含本地读取的纯文本）。"""
    return MINERU_SUFFIXES[_mineru_mode()] | LOCAL_SUFFIXES


def _load_documents(file_path: Path) -> list[Document]:
    """解析文档为 Markdown 文本"""
    if file_path.suffix.lower() in LOCAL_SUFFIXES:
        return [Document(page_content=file_path.read_text(encoding="utf-8"))]

    settings = get_settings()
    mode = _mineru_mode()
    if mode == "precision" and not settings.mineru_token:
        raise RuntimeError(
            "当前解析模式为 precision，需填写 MinerU token，或改用 flash 模式"
        )

    options: dict = {
        "source": str(file_path),
        "mode": mode,
        "language": settings.mineru_language,
        "timeout": settings.mineru_timeout,
    }
    if mode == "precision":
        # 仅 precision 模式接受以下四个参数
        options |= {
            "token": settings.mineru_token,
            "ocr": settings.mineru_ocr,
            "formula": settings.mineru_formula,
            "table": settings.mineru_table,
        }
    return MinerULoader(**options).load()


def _split_documents(documents: list[Document], doc_id: str, document_name: str) -> list[Document]:
    """切分为分块，元数据统一为 doc_id 与来源文件名。"""
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    metadata = {"doc_id": doc_id, "source": document_name}
    chunks: list[Document] = []
    for document in documents:
        for text in splitter.split_text(document.page_content):
            chunks.append(Document(page_content=text, metadata=dict(metadata)))
    return chunks


async def ingest_document(doc_id: str, document_name: str, file_path: Path) -> int:
    """文档存入向量库，返回分块数；无有效内容返回 0。"""
    parsed = await asyncio.to_thread(_load_documents, file_path)
    content = [document for document in parsed if document.page_content.strip()]
    chunks = await asyncio.to_thread(_split_documents, content, doc_id, document_name)
    if not chunks:
        return 0
    store = get_vector_store()
    await asyncio.to_thread(store.add_documents, chunks)
    return len(chunks)
