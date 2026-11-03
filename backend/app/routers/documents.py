"""文档管理路由：上传（后台向量化）/ 列表 / 删除。"""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Annotated, BinaryIO
from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Path as PathParam,
    Request,
    UploadFile,
)

from app.config import UPLOADS_DIR
from app.core.document_processing import allowed_suffixes, ingest_document, upload_limits
from app.core.vector_store import delete_document_vectors
from app.db import connect, now
from app.schemas import DocumentOut

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger(__name__)

_DOCUMENT_COLUMNS = "id, document_name, status, error, chunk_count, created_at"
_UPLOAD_CHUNK_BYTES = 1024 * 1024

# 同时解析/向量化的文档上限：批量上传时避免同时打满 MinerU 与 Embedding 配额
_MAX_CONCURRENT_INGEST = 2
_INGEST_SEMAPHORE = asyncio.Semaphore(_MAX_CONCURRENT_INGEST)

class _UploadTooLarge(Exception):
    """上传文件超过大小上限。"""


def _save_upload(src: BinaryIO, dest: Path, max_bytes: int) -> int:
    """分块拷贝上传文件到磁盘并返回字节数；超限时抛出 _UploadTooLarge。"""
    size = 0
    with dest.open("wb") as out:
        while chunk := src.read(_UPLOAD_CHUNK_BYTES):
            size += len(chunk)
            if size > max_bytes:
                raise _UploadTooLarge
            out.write(chunk)
    return size

@router.get("")
async def list_documents() -> list[DocumentOut]:
    """全部文档，新上传的在前。"""
    async with connect() as db:
        rows = await (
            await db.execute(
                f"SELECT {_DOCUMENT_COLUMNS} FROM documents"
                " ORDER BY created_at DESC, rowid DESC"
            )
        ).fetchall()
    return [DocumentOut.model_validate(dict(row)) for row in rows]


@router.post("", status_code=201)
async def upload_document(
    request: Request, background_tasks: BackgroundTasks, file: UploadFile
) -> DocumentOut:
    """上传文档：校验 → 分块落盘 → 入库 → 后台向量化。"""
    suffix = Path(file.filename or "").suffix.lower()
    supported = allowed_suffixes()
    if suffix not in supported:
        raise HTTPException(
            status_code=400,
            detail=(
                f"当前解析模式不支持 {suffix or '无扩展名'} 文件，"
                f"支持：{' / '.join(sorted(supported))}"
            ),
        )

    max_bytes, _ = upload_limits()
    limit_mb = max_bytes // (1024 * 1024)
    # 提前按请求体大小拒绝明显超限的上传
    content_length = request.headers.get("content-length", "")
    if content_length.isdigit() and int(content_length) > max_bytes + 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"文件大小超过 {limit_mb}MB 上限")

    doc = DocumentOut(
        id=uuid.uuid4().hex,
        document_name=file.filename,
        status="processing",
        chunk_count=0,
        created_at=now(),
    )
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOADS_DIR / f"{doc.id}{suffix}"
    # 分块拷贝放到线程池，避免大文件读入内存并阻塞事件循环
    try:
        size = await asyncio.to_thread(_save_upload, file.file, file_path, max_bytes)
    except _UploadTooLarge:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"文件大小超过 {limit_mb}MB 上限")
    if size == 0:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="文件为空")

    async with connect() as db:
        await db.execute(
            f"INSERT INTO documents ({_DOCUMENT_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?)",
            (doc.id, doc.document_name, doc.status, doc.error, doc.chunk_count, doc.created_at),
        )
        await db.commit()

    background_tasks.add_task(_vectorize, doc.id, doc.document_name, file_path)
    logger.info(
        "文档已接收 id=%s name=%s size=%dKB 已转后台向量化",
        doc.id,
        doc.document_name,
        size // 1024,
    )
    return doc


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: Annotated[str, PathParam()]):
    """删除文档：向量数据库分块、业务库记录、上传文件的目录三处同步清理。"""
    await asyncio.to_thread(delete_document_vectors, doc_id)

    async with connect() as db:
        cursor = await db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="文档不存在")
        await db.commit()

    for path in UPLOADS_DIR.glob(f"{doc_id}.*"):
        path.unlink(missing_ok=True)
    logger.info("文档已删除 id=%s（向量、记录与源文件已清理）", doc_id)


@router.post("/{doc_id}/retry")
async def retry_document(
    background_tasks: BackgroundTasks, doc_id: Annotated[str, PathParam()]
) -> DocumentOut:
    """重新解析失败文档：仅 failed 状态可重试，原文件缺失时要求重新上传。"""
    async with connect() as db:
        row = await (
            await db.execute(
                f"SELECT {_DOCUMENT_COLUMNS} FROM documents WHERE id = ?", (doc_id,)
            )
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    if row["status"] != "failed":
        raise HTTPException(status_code=409, detail="仅解析失败的文档可重试")

    file_path = next(UPLOADS_DIR.glob(f"{doc_id}.*"), None)
    if file_path is None:
        raise HTTPException(status_code=400, detail="原文件不存在，请重新上传")

    # 条件更新抢占状态，避免并发重复触发解析
    async with connect() as db:
        cursor = await db.execute(
            "UPDATE documents SET status = 'processing', error = NULL, chunk_count = 0"
            " WHERE id = ? AND status = 'failed'",
            (doc_id,),
        )
        await db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=409, detail="文档状态已变化，请刷新后重试")

    await asyncio.to_thread(delete_document_vectors, doc_id)  # 清掉可能残留的分块，避免重复入库
    background_tasks.add_task(_vectorize, doc_id, row["document_name"], file_path)
    logger.info("文档重试 id=%s name=%s", doc_id, row["document_name"])
    return DocumentOut(
        id=doc_id,
        document_name=row["document_name"],
        status="processing",
        error=None,
        chunk_count=0,
        created_at=row["created_at"],
    )


async def _vectorize(doc_id: str, document_name: str, file_path: Path):
    """后台向量化，完成后更新状态：ready / empty / failed。"""
    async with _INGEST_SEMAPHORE:
        logger.info("开始向量化 id=%s name=%s", doc_id, document_name)
        try:
            chunk_count = await ingest_document(doc_id, document_name, file_path)
            status = "ready" if chunk_count else "empty"
            async with connect() as db:
                cursor = await db.execute(
                    "UPDATE documents SET status = ?, chunk_count = ? WHERE id = ?",
                    (status, chunk_count, doc_id),
                )
                await db.commit()
            if cursor.rowcount == 0:
                # 向量化期间文档已被删除：清理刚写入的向量
                logger.info("向量化期间文档已删除，清理残留向量 id=%s", doc_id)
                await asyncio.to_thread(delete_document_vectors, doc_id)
            else:
                logger.info("向量化完成 id=%s status=%s chunks=%d", doc_id, status, chunk_count)
        except Exception as exc:
            logger.exception("向量化失败 id=%s name=%s", doc_id, document_name)
            async with connect() as db:
                await db.execute(
                    "UPDATE documents SET status = 'failed', error = ? WHERE id = ?",
                    (str(exc)[:500], doc_id),
                )
                await db.commit()
            # 失败时可能已写入部分分块，必须清理，避免"失败文档"仍被检索到
            try:
                await asyncio.to_thread(delete_document_vectors, doc_id)
            except Exception:
                pass  # 清理失败不应掩盖原始解析错误；启动对账会再次兜底
