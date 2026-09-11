# RAG 知识库助手 · 后端镜像
# 运行：FastAPI + uvicorn（由 docker-compose 编排，数据卷挂载 /app/backend/data）
FROM python:3.13-slim

# uv 官方独立二进制，用于按 uv.lock 精确安装依赖
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app/backend

# 先装依赖再拷贝代码：代码变动时不触发依赖重装（层缓存）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 应用代码（.env 与 data/ 由运行时挂载，不打进镜像）
COPY app ./app

# 非 root 运行；data 目录随卷首次挂载时继承该属主
RUN useradd --create-home appuser \
    && mkdir -p /app/backend/data \
    && chown -R appuser:appuser /app/backend
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

# 0.0.0.0：需接受来自 frontend 容器的反代流量
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
