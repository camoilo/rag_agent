"""混合检索：向量召回 + BM25 关键词召回，RRF 融合。"""

import hashlib
import heapq
import jieba
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from app.config import get_settings
from app.core.vector_store import get_vector_store

_RRF_K = 60  # RRF 平滑常数，默认60，按需调整
_BM25_K1 = 1.5  # BM25 词频饱和速度，通常1.2~2.0
_BM25_B = 0.75  # BM25 文档长度归一化强度（惩罚程度），默认0.75


def _tokenize(text: str) -> list[str]:
    """分词：jieba 搜索模式切分。"""
    return jieba.lcut_for_search(text)


def _chunk_key(doc: Document) -> str:
    """分块标识：来源 + 内容哈希，用于混合检索时去重。"""
    metadata = doc.metadata
    digest = hashlib.md5(doc.page_content.encode("utf-8")).hexdigest()
    return f"{metadata.get('source', '')}|{digest}"


class _BM25Index:
    """全部分块的内存索引，仅加载于内存"""

    def __init__(self, corpus: list[Document], ids: list[str]):
        self.fingerprint = hash(tuple(ids))  # 所有分块的id的集合指纹
        self.texts = corpus
        self.bm25 = (
            BM25Okapi([_tokenize(d.page_content) for d in corpus], k1=_BM25_K1, b=_BM25_B) if corpus else None
        )


# 索引缓存，每次运行项目时需重新构建
_bm25_index: _BM25Index | None = None


def _get_bm25_index() -> _BM25Index:
    """取 BM25 索引；未构建或构建过期时从 Chroma 全量重建。"""
    global _bm25_index
    # 只取 id 算指纹（ids 始终随结果返回），避免每次检索都拉取全部分块正文与元数据
    fingerprint = hash(tuple(get_vector_store().get(include=[])["ids"]))
    if _bm25_index is None or _bm25_index.fingerprint != fingerprint:
        result = get_vector_store().get()
        corpus = [
            Document(page_content=text, metadata=metadata or {})
            for text, metadata in zip(result["documents"], result["metadatas"])
        ]
        _bm25_index = _BM25Index(corpus, result["ids"])
    return _bm25_index


def _bm25_search(query: str, k: int) -> list[Document]:
    """关键词召回；过滤零分分块。"""
    index = _get_bm25_index()
    if index.bm25 is None:
        return []
    scores = index.bm25.get_scores(_tokenize(query))
    # 只取分数最高的 k 个，避免对全库做完整排序
    ranked = heapq.nlargest(k, range(len(scores)), key=scores.__getitem__)
    return [index.texts[i] for i in ranked if scores[i] > 0]


def _vector_search(query: str, k: int) -> list[Document]:
    """向量召回；按语义相似度排序。"""
    return get_vector_store().similarity_search(query, k=k)


def retrieve(query: str) -> list[Document]:
    """检索知识库，返回 top_k 分块。"""
    settings = get_settings()
    if not settings.use_hybrid:
        return _vector_search(query, settings.top_k)

    vector_chunks = _vector_search(query, settings.candidate_k)
    bm25_chunks = _bm25_search(query, settings.candidate_k)

    # RRF 融合：score = Σ 1/(k + rank)，同一分块两路命中则分数累加
    score_dict: dict[str, float] = {}
    chunk_dict: dict[str, Document] = {}
    for chunks in (vector_chunks, bm25_chunks):
        for rank, chunk in enumerate(chunks, start=1):
            key = _chunk_key(chunk)
            score_dict[key] = 1.0 / (_RRF_K + rank) + score_dict.get(key, 0.0)
            chunk_dict[key] = chunk

    ranked: list[str] = sorted(score_dict, key=lambda i: score_dict[i], reverse=True)
    return [chunk_dict[key] for key in ranked[: settings.top_k]]
