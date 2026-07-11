FROM python:3.12-slim

WORKDIR /app

# 依存関係を先にコピー (Docker レイヤーキャッシュ活用)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ソースをコピー
COPY . .

# Cloud Run はポート 8080 を使用する
EXPOSE 8080

# Uvicorn で起動
# --workers 1 : インメモリ状態の一貫性を保つため単一ワーカー固定
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
