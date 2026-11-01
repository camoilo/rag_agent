"""向量库：嵌入模型与 Chroma 单例。"""

from functools import lru_cache
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from app.config import CHROMA_DIR, get_settings


@lru_cache
def get_embeddings() -> OpenAIEmbeddings:
    """嵌入模型。"""
    settings = get_settings()
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
        base_url=settings.embedding_base_url,
        check_embedding_ctx_length=False,
        chunk_size=settings.embed_batch_size,  # 单次请求的文本数上限，控制分批请求
        timeout=settings.embedding_timeout,
        max_retries=settings.max_retries,
    )


@lru_cache
def get_vector_store() -> Chroma:
    """嵌入式 Chroma，持久化到 data/chroma。"""
    return Chroma(
        persist_directory=str(CHROMA_DIR),
        embedding_function=get_embeddings(),
    )


def delete_document_vectors(doc_id: str) -> None:
    """删除指定文档的全部向量分块。"""
    get_vector_store().delete(where={"doc_id": doc_id})
