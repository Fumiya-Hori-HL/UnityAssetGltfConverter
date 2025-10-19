# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

Unity Cloud Asset Manager APIを使用してOBJファイルをGLB/GLTF形式に変換するPythonツール。2つの実装方式を提供：
- `main.py`: Unity Cloud Python SDK使用版
- `main_webapi.py`: 完全REST API実装版（**推奨**）

## 環境構築

### 必須：uvパッケージマネージャーを使用

```bash
# 既存の仮想環境を削除（存在する場合）
deactivate 2>/dev/null || true
rm -rf .venv

# uv で仮想環境を作成
uv venv

# 仮想環境を有効化
source .venv/bin/activate

# Unity特有のパッケージインデックスから依存パッケージをインストール
uv pip install -r requirements.txt --extra-index-url https://unity3ddist.jfrog.io/artifactory/api/pypi/am-pypi-prod-local/simple
```

**重要**: `--extra-index-url`パラメータは必須。Unity Cloud SDKがUnity専用のパッケージリポジトリでホストされているため。

### 環境変数設定

`.env`ファイルを作成（テンプレート無し、自分で作成）：
```env
UNITY_CLOUD_ORGANIZATION_ID=your_org_id
UNITY_CLOUD_PROJECT_ID=your_project_id
UNITY_CLOUD_KEY_ID=your_key_id
UNITY_CLOUD_SECRET_KEY=your_secret_key
```

**注意**: `.env`ファイルは`.gitignore`で除外されている。絶対にコミットしないこと。

## 実行方法

```bash
# REST API版（推奨）
.venv/bin/python main_webapi.py

# SDK版
.venv/bin/python main.py
```

**重要**: `.venv/bin/python`を使用する。システムの`python`や`python3`ではなく仮想環境のPythonを明示的に指定すること。

## アーキテクチャ

### main_webapi.pyの処理フロー（7ステップ）

詳細は`doc/sequence_diagram.md`のMermaidシーケンス図を参照。

1. **認証情報準備**: Key ID + Secret KeyをBase64エンコードしてBasic認証
2. **アセット作成**: `POST /assets` → assetId, assetVersion, datasets取得
3. **データセット取得**: レスポンスからSourceデータセットのIDを抽出
4. **ファイルアップロード**:
   - `POST /datasets/{datasetId}/files` → 署名付きURL取得
   - Unity管理のAzure Blob Storageへ`PUT`（ヘッダー: `x-ms-blob-type: BlockBlob`必須）
5. **変換開始**: `POST /transformations/start/{workflowType}` → transformationId取得
6. **ステータスポーリング**: 10秒間隔で最大5分間、status == "Succeeded"まで待機
7. **ファイルダウンロード**:
   - Asset詳細API (`GET /assets/{assetId}/versions/{versionId}?IncludeFields=files,files.*`) で`files`配列取得
   - `GET /files/{filePath}/download-url` → 署名付きURL取得
   - Azure Blob Storageから`GET`でダウンロード

### 重要な実装ポイント

#### OpenAPI仕様書準拠（doc/AssetManagerAPIv1.yaml）

すべてのAPIリクエスト/レスポンスは`doc/AssetManagerAPIv1.yaml`に厳密に準拠：

- **ファイルアップロード**: リクエストボディは`{"filePath": "filename"}`（camelCase）
- **変換開始**: `workflowType`はURLパスパラメータ、ボディは`{"extraParameters": {...}}`
- **変換レスポンス**: `transformationId`フィールド（`id`ではない）
- **ファイル取得**: Asset詳細APIの`files`フィールドを使用（データセットファイル一覧APIは変換直後に空を返すため使用しない）

#### ワークフロータイプ

- `higher-tier-optimize-and-convert`: 有料プラン専用
- `free-tier-optimize-and-convert`: 無料プラン用

無料プランで`higher-tier-*`を使用すると403エラー（"Organization does not have the entitlement"）が発生。

#### Azure Blob Storage

Unity APIが内部でAzure Blob Storageを使用（Unity側が管理、ユーザーのAzureアカウントは不要）：
- アップロード時必須ヘッダー: `x-ms-blob-type: BlockBlob`, `Content-Type: application/octet-stream`
- 署名付きURLの有効期限: 1時間

#### ファイル取得の注意点

**問題**: データセットファイル一覧API (`GET /datasets/{datasetId}/files`) は変換完了直後に空配列を返すことがある。

**解決策**: Asset詳細API (`GET /assets/{assetId}/versions/{versionId}`) の`files`フィールドを使用。
- パラメータ: `IncludeFields=["*", "datasets", "datasets.*", "files", "files.*"]`
- `files`配列内の各ファイルに`datasetIds`, `filePath`, `status`, `fileSize`が含まれる
- 対象ファイルを検索後、`GET /files/{encodedFilePath}/download-url`でダウンロードURL取得

#### エラーハンドリング

すべてのAPI呼び出しは`response.raise_for_status()`でHTTPエラーをチェック。
エラー時は`log_error_response()`で構造化ログ出力：
- `requestId`: リクエスト固有ID
- `code`: エラーコード
- `title`: エラー概要
- `detail`: 詳細メッセージ

## ディレクトリ構造

```
.
├── main.py                      # SDK版実装
├── main_webapi.py              # REST API版実装（推奨）
├── requirements.txt            # 依存パッケージ
├── .env                        # 環境変数（要作成、gitignore済み）
├── assets_input/               # 入力OBJファイル配置
├── assets_output/              # 出力GLB/GLTFファイル保存先
└── doc/
    ├── AssetManagerAPIv1.yaml  # OpenAPI仕様書（16,000行以上）
    └── sequence_diagram.md     # 処理フローのMermaid図
```

## 重要な制約・仕様

1. **入力ファイルパス変更**: `main_webapi.py`内の`INPUT_FILE_PATH`変数を編集（デフォルト: `assets_input/your_model.obj`）

2. **変換タイムアウト**: デフォルト300秒（5分）。大きなファイルの場合は`main_webapi.py`内のタイムアウト値を調整。

3. **変換パラメータ**:
   ```python
   {
       "outputFileName": "model_name",  # 拡張子なし
       "exportFormats": ["glb"]         # "glb" or "gltf"
   }
   ```

4. **認証方式**: 現在はBasic認証を使用。本番環境ではBearer Token認証（Token Exchange API経由）が推奨。

5. **環境変数の上書き**: `python-dotenv`は既存の環境変数を上書きしない。テスト時に`.env`を切り替える場合は事前に`unset`が必要：
   ```bash
   unset UNITY_CLOUD_ORGANIZATION_ID UNITY_CLOUD_PROJECT_ID UNITY_CLOUD_KEY_ID UNITY_CLOUD_SECRET_KEY
   .venv/bin/python main_webapi.py
   ```

## 参考資料

- OpenAPI仕様書: `doc/AssetManagerAPIv1.yaml`（必読）
- 処理フロー図: `doc/sequence_diagram.md`
- Unity公式: https://services.docs.unity.com/assets-manager/v1/
