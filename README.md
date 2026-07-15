# ⚡ Pikon — リアルタイム早押しクイズシステム

不特定多数が同時接続し、ミリ秒単位の精度で回答者を選出するリアルタイム WebSocket 早押しシステムです。

## 特徴

- 🎯 サーバーサイドタイムスタンプによるミリ秒精度の順位判定
- 👥 100人規模の同時接続に対応
- 📱 モバイルフレンドリーな参加者画面（大型早押しボタン）
- 🖥️ 司会者向けコントロールパネル（QR コード・参加者リスト・順位表示）
- 🔐 JWT による司会者認証
- ☁️ Google Cloud Run 対応

## ディレクトリ構成

```
Pikon/
├── main.py                   # FastAPI エントリーポイント
├── auth.py                   # JWT 認証
├── room.py                   # ルーム状態管理
├── connection_manager.py     # WebSocket 接続管理
├── routers/
│   ├── host_api.py           # 司会者 REST API
│   └── ws.py                 # WebSocket エンドポイント
├── static/
│   ├── participant/          # 参加者フロントエンド
│   └── host/                 # 司会者フロントエンド
├── Dockerfile
├── requirements.txt
└── .env.example
```

## ローカル起動

### 1. 依存関係のインストール

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. 環境変数の設定

```bash
cp .env.example .env
# .env を編集して SECRET_KEY, HOST_USERNAME, HOST_PASSWORD を設定
```

### 3. サーバー起動

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- 参加者画面: http://localhost:8000/
- 司会者ログイン: http://localhost:8000/host/login
- 司会者パネル: http://localhost:8000/host

## 使い方

1. **参加者への案内**: 司会者パネルの QR コードをスクリーンに表示し、参加者に読み込んでもらう
2. **エントリー**: 参加者が社員番号等の ID を入力して参加登録
3. **ボタン開放**: 司会者が「ボタン開放」を押すと参加者全員の早押しが有効化される
4. **早押し**: 参加者がボタンを押すと、自分が何番目に押したかがリアルタイム表示される
5. **締め切り**: 司会者が「締め切る」を押すと受付終了・順位確定
6. **回答**: 一番早かった人が回答
   - 正解 → 「次の問題へ」でリセット
   - 不正解 → 「次の候補へ」で 2 番目の人を表示

## Google Cloud Run へのデプロイ

```bash
# プロジェクト設定
gcloud config set project <YOUR_PROJECT_ID>

# シークレット登録 (初回のみ)
echo -n "your-secret-key" | gcloud secrets create HAYAOSHY_SECRET_KEY --data-file=-
echo -n "your-password"   | gcloud secrets create HAYAOSHY_HOST_PASSWORD --data-file=-

# サービスアカウントへのシークレット参照権限の付与 (初回のみ)
# ※ <PROJECT_NUMBER> はご自身のGoogle Cloudプロジェクト番号に置き換えてください
gcloud secrets add-iam-policy-binding HAYAOSHY_SECRET_KEY \
  --member="serviceAccount:<PROJECT_NUMBER>-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding HAYAOSHY_HOST_PASSWORD \
  --member="serviceAccount:<PROJECT_NUMBER>-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Cloud Run へデプロイ
gcloud run deploy pikon \
  --source . \
  --region asia-northeast1 \
  --platform managed \
  --allow-unauthenticated \
  --max-instances 1 \
  --min-instances 1 \
  --timeout 3600 \
  --set-env-vars HOST_USERNAME=host \
  --set-secrets "SECRET_KEY=HAYAOSHY_SECRET_KEY:latest,HOST_PASSWORD=HAYAOSHY_HOST_PASSWORD:latest"
```

> **Note**: `--max-instances=1` は必須です。インメモリ状態管理のため、複数インスタンスへのスケールアウトはサポートしていません。

## WebSocket イベント仕様

### 参加者 `/ws/participant`

| 送受信 | イベント | 説明 |
|---|---|---|
| 送信 | `join` | ID を登録してルームに参加 |
| 送信 | `press` | 早押しボタンを押す |
| 受信 | `join_ack` | 参加成功/失敗 |
| 受信 | `status_change` | ボタン開放/締め切り通知 |
| 受信 | `press_ack` | 自分の順位 (N 番目) |
| 受信 | `result_update` | 全体の順位リスト |
| 受信 | `reset` | 次の問題へのリセット |

### 司会者 `/ws/host?token=<JWT>`

| 送受信 | イベント | 説明 |
|---|---|---|
| 送信 | `host_open` | ボタン開放 |
| 送信 | `host_close` | 締め切り |
| 送信 | `host_next_candidate` | 次の候補へ |
| 送信 | `host_reset` | 次の問題へリセット |
| 受信 | `init` | 初期状態 |
| 受信 | `participant_update` | 参加者リスト更新 |
| 受信 | `result_update` | 順位リスト更新 |
