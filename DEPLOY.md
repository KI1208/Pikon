# Hayaoshy – Google Cloud Run デプロイガイド

本アプリケーション（Hayaoshy）を Google Cloud Run にデプロイするための手順と、インメモリ設計に伴う重要な設定項目について説明します。

---

## ⚠️ 最も重要な設定（インメモリ状態の保持）

本システムは、早押し判定の極限までの低遅延化（ミリ秒精度）とシンプルな構成を実現するため、**クイズ of 部屋状態（参加者リスト、早押し順位など）をサーバーのメモリ上（インメモリ）で管理**しています。

そのため、Cloud Run にデプロイする際は以下の設定が**必須**となります。この設定を行わない場合、複数のサーバーに接続が分散され、正しく早押しが動作しなくなります。

1. **最大インスタンス数（Max Instances）を `1` に設定する**
   * インスタンスが複数立ち上がると、参加者と司会者が異なるサーバーに接続されてしまい、状態の同期ができなくなります。最大インスタンス数を必ず `1` に制限してください。
2. **最小インスタンス数（Min Instances）の推奨設定**
   * **推奨**: `1`（コールドスタートの防止、およびアクセスがない時間帯にサーバーが自動停止してメモリ状態が消去されるのを防ぐため）。
   * **非推奨（コスト削減優先の場合のみ）**: `0`（一定時間アクセスがないとインスタンスが停止し、部屋の状態や参加者情報がリセットされます）。

---

## 1. 事前準備

1. **Google Cloud SDK (gcloud CLI)** がローカル環境にインストールされ、認証が完了していること。
   ```bash
   gcloud auth login
   gcloud config set project [YOUR_PROJECT_ID]
   ```
2. デプロイ先のリージョンを決めておく（例: `asia-northeast1` (東京)）。

---

## 2. デプロイ手順

プロジェクトのルートディレクトリ（`c:\Projects\Hayaoshy`）で以下のコマンドを実行します。

### 方法A: ソースコードから直接デプロイ（推奨・簡単）

gcloud のソースデプロイ機能を使用すると、自動的に Cloud Build で Docker イメージがビルドされ、Cloud Run にデプロイされます。

```bash
gcloud run deploy hayaoshy \
  --source . \
  --platform managed \
  --region asia-northeast1 \
  --allow-unauthenticated \
  --max-instances 1 \
  --min-instances 1 \
  --port 8080 \
  --set-env-vars="JWT_SECRET=super-secret-key-change-me,HOST_USERNAME=admin,HOST_PASSWORD=secure-password"
```

> [!NOTE]
> `JWT_SECRET` には、推測不可能なランダムな長い文字列を指定してください。
> `HOST_USERNAME` と `HOST_PASSWORD` は、司会者パネルのログインに使用する任意の文字列を指定してください。

### 方法B: 手動でビルドしてデプロイ

Docker イメージを一度 Artifact Registry / Container Registry に登録してからデプロイする場合の手順です。

```bash
# 1. Cloud Build でイメージをビルド・登録
gcloud builds submit --tag gcr.io/[PROJECT_ID]/hayaoshy:latest

# 2. 登録したイメージを Cloud Run にデプロイ
gcloud run deploy hayaoshy \
  --image gcr.io/[PROJECT_ID]/hayaoshy:latest \
  --platform managed \
  --region asia-northeast1 \
  --allow-unauthenticated \
  --max-instances 1 \
  --min-instances 1 \
  --port 8080 \
  --set-env-vars="JWT_SECRET=super-secret-key-change-me,HOST_USERNAME=admin,HOST_PASSWORD=secure-password"
```

---

## 3. デプロイ後の設定（QRコード用URLの更新）

デプロイが完了すると、以下のようなサービス URL が発行されます。
`https://hayaoshy-xxxxxx-an.a.run.app`

司会者パネルで表示される参加者用 QR コードに本番環境の正しい URL を埋め込むため、環境変数 `QR_BASE_URL` にこの URL を設定して再反映します。

```bash
gcloud run services update hayaoshy \
  --region asia-northeast1 \
  --update-env-vars "QR_BASE_URL=https://hayaoshy-xxxxxx-an.a.run.app"
```

---

## 4. 環境変数一覧

デプロイ時に `--set-env-vars` または Google Cloud コンソールから設定する環境変数は以下の通りです。

| 変数名 | 説明 | 例 |
| :--- | :--- | :--- |
| `JWT_SECRET` | 司会者ログインセッション認証用の暗号鍵 | 32文字以上のランダムな文字列 |
| `HOST_USERNAME`| 司会者コントロールパネルのログインID | `host_admin` |
| `HOST_PASSWORD`| 司会者コントロールパネルのログインパスワード| `your-secure-password` |
| `QR_BASE_URL` | 参加用QRコードに埋め込む基準URL (本番用) | `https://hayaoshy-xxxxxx-an.a.run.app` |
