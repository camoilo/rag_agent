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

    # 允许的跨域来源（逗号分隔）；开发直连 5173，生产由 nginx 同源反代，无需跨域
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # LLM 配置（OpenAI 协议兼容，当前使用阿里云百炼）
    openai_api_key: str = ""    # 在.env 中配置
    openai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    chat_model: str = "qwen3.8-flash"
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_model: str = "qwen3.7-text-embedding-flash"
    embed_batch_size: int = 20  # 单次嵌入请求的文本行数，需 ≤ 最大行数上限

    # 文档解析（MinerU）
    mineru_token: str = ""            # 在.env 中配置，仅 precision 模式生效
    mineru_mode: str = "precision"    # precision（需 token，单文件 ≤200MB 且 ≤200 页）/ flash（免 token，单文件 ≤10MB 且 ≤20 页）
    mineru_language: str = "ch"       # 文档语言，留空默认中文
    mineru_ocr: bool = False          # 扫描件需开启 OCR；仅 precision 生效
    mineru_formula: bool = True       # 公式识别；仅 precision 生效
    mineru_table: bool = True         # 表格识别；仅 precision 生效
    mineru_timeout: int = 600         # 单文件解析等待上限（秒）
    # 上传限制
    max_upload_bytes: int = 200 * 1024 * 1024  # 200MB

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
