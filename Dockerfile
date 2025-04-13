FROM python:3.10-slim

WORKDIR /app

# システムの依存関係をインストール
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 必要なファイルをコピー
COPY pyproject.toml ./
COPY README.md ./
COPY apm_mcp_server/ ./apm_mcp_server/
COPY data/ ./data/
COPY tools/ ./tools/

# パッケージのインストール
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# 環境変数の設定
ENV PYTHONUNBUFFERED=1
# OpenAI API キーと使用モデルのデフォルト値（実行時オーバーライド推奨）
ENV OPENAI_API_KEY=""

# エントリーポイント
ENTRYPOINT ["python", "-m", "apm_mcp_server"]