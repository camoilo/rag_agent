"""文档管理路由：上传（后台向量化）/ 列表 / 删除。"""

import uuid
from pathlib import Path
from typing import Annotated
from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Path as PathParam,
    UploadFile,
)

from app.config import UPLOADS_DIR, get_settings
from app.core.document_processing import allowed_suffixes, ingest_document
from app.core.vector_store import delete_document_vectors
from app.db import connect, now
from app.schemas import DocumentOut

router = APIRouter(prefix="/api/documents", tags=["documents"])

_DOCUMENT_COLUMNS = "id, document_name, status, error, chunk_count, created_at"


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
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile) -> DocumentOut:
    """上传文档：校验 → 保存文件 → 入库 → 后台向量化。"""
    settings = get_settings()
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

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(content) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes // (1024 * 1024)
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
    file_path.write_bytes(content)

    async with connect() as db:
        await db.execute(
            f"INSERT INTO documents ({_DOCUMENT_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?)",
            (doc.id, doc.document_name, doc.status, doc.error, doc.chunk_count, doc.created_at),
        )
        await db.commit()

    background_tasks.add_task(_vectorize, doc.id, doc.document_name, file_path)
    return doc


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: Annotated[str, PathParam()]):
    """删除文档：向量数据库分块、业务库记录、上传文件的目录三处同步清理。"""
    delete_document_vectors(doc_id)

    async with connect() as db:
        cursor = await db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="文档不存在")
        await db.commit()

    for path in UPLOADS_DIR.glob(f"{doc_id}.*"):
        path.unlink(missing_ok=True)


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

    delete_document_vectors(doc_id)  # 清掉可能残留的分块，避免重复入库
    background_tasks.add_task(_vectorize, doc_id, row["document_name"], file_path)
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
            delete_document_vectors(doc_id)  # 向量化期间文档已被删除：清理刚写入的向量
    except Exception as exc:
        async with connect() as db:
            await db.execute(
                "UPDATE documents SET status = 'failed', error = ? WHERE id = ?",
                (str(exc)[:500], doc_id),
            )
            await db.commit()
