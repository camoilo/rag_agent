"""文档处理：解析 → 切分 → 向量化入库。"""

import asyncio
from pathlib import Path
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.config import get_settings
from app.core.vector_store import get_vector_store


def _extract_pages(file_path: Path) -> list[str]:
    """按页提取文本；纯文本文件整体作为一页。"""
    if file_path.suffix.lower() == ".pdf":
        with file_path.open("rb") as f:
            return [page.extract_text() or "" for page in PdfReader(f).pages]
    return [file_path.read_text(encoding="utf-8")]


def _split_pages(pages: list[str], doc_id: str, document_name: str) -> list[Document]:
    """切分为分块，带 doc_id / 来源文件名 / 页码元数据。"""
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    documents = []
    for page_number, text in enumerate(pages, start=1):
        for chunk in splitter.split_text(text):
            documents.append(
                Document(
                    page_content=chunk,
                    metadata={"doc_id": doc_id, "source": document_name, "page": page_number},
                )
            )
    return documents


async def ingest_document(doc_id: str, document_name: str, file_path: Path) -> int:
    """文档存入向量库，返回分块数；无有效内容返回 0。"""
    pages = await asyncio.to_thread(_extract_pages, file_path)
    chunks = await asyncio.to_thread(_split_pages, [page for page in pages if page.strip()], doc_id, document_name)
    if not chunks:
        return 0
    store = get_vector_store()
    await asyncio.to_thread(store.add_documents, chunks)
    return len(chunks)
