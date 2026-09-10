"""应用配置：通过环境变量 / .env 加载。"""

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# 锚定 backend/ 目录：.env 与存储路径不随当前工作目录（cwd）变化
BASE_DIR = Path(__file__).resolve().parent.parent

# 存储路径为项目约定，直接指定 backend/data
DATA_DIR = BASE_DIR / "data"
APP_DB = DATA_DIR / "app.db"    # 业务数据库
MEMORY_DIR = DATA_DIR / "agent_memory"  # 记忆库目录
MEMORY_DB = MEMORY_DIR / "agent_memory.db"  # LangGraph 记忆库
CHROMA_DIR = DATA_DIR / "chroma"
UPLOADS_DIR = DATA_DIR / "uploads"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM 配置（OpenAI 协议兼容，当前使用阿里云百炼）
    openai_api_key: str = ""
    openai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    chat_model: str = "qwen3.7-plus"
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_model: str = "qwen3.7-text-embedding"
    embed_batch_size: int = 20  # 单次嵌入请求的文本行数，需 ≤ 最大行数上限

    # 上传限制
    max_upload_bytes: int = 20 * 1024 * 1024  # 20MB

    # RAG 参数
    chunk_size: int = 800
    chunk_overlap: int = 100
    top_k: int = 4
    use_hybrid: bool = True  # 混合检索（向量 + BM25，RRF 融合）；False 为纯向量
    candidate_k: int = 20  # 混合检索时每路召回的候选数


@lru_cache
def get_settings() -> Settings:
    """进程内单例的配置实例。"""
    return Settings()
