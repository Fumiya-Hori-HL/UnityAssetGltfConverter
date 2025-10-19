# UnityAssetGltfConverter

Unity Cloud Asset Manager APIを使用して、3Dモデルファイル（OBJ形式）をGLTF形式に変換するPythonツールです。

## 概要

このツールは、Unity Cloud Asset Manager APIと連携し、以下の処理を自動化します：

1. 3Dモデルファイルのアップロード
2. Unity Asset Managerでのフォーマット変換（OBJ → GLTF）
3. 変換済みファイルのダウンロード

## 機能

- **Unity Cloud SDK版**: `main.py` - Unity Cloud Python SDKを使用した実装
- **完全REST API版**: `main_webapi.py` - REST APIのみを使用した完全実装
- サービスアカウント認証によるセキュアなAPI通信
- 変換ステータスの自動ポーリング
- エラーハンドリングと詳細なログ出力

## 必要要件

- Python 3.12以上
- Unity Cloudアカウント
- Unity Cloud Asset Managerが有効なプロジェクト
- サービスアカウントの認証情報（Key ID、Secret Key）

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

プロジェクトルートに `.env` ファイルを作成し、以下の情報を設定します：

```env
UNITY_CLOUD_ORGANIZATION_ID=your_organization_id
UNITY_CLOUD_PROJECT_ID=your_project_id
UNITY_CLOUD_KEY_ID=your_key_id
UNITY_CLOUD_SECRET_KEY=your_secret_key
```

### 3. Unity Cloudサービスアカウントの設定

#### サービスアカウントの作成

1. **Unity Dashboardにアクセス**
   - [Unity Dashboard](https://dashboard.unity3d.com/)にサインイン

2. **サービスアカウントの作成**
   - Administration > Service accounts に移動
   - `+ New` ボタンをクリック
   - アカウント名（例：`asset-manager-converter`）と説明を入力
   - `Create` をクリック

3. **認証情報の生成**
   - 作成したアカウントの詳細画面で `Keys` セクションに移動
   - `+ Add key` をクリック
   - **重要**: Secret Keyは一度しか表示されません。必ず安全な場所に保管してください

4. **ロールの割り当て**
   - アカウント詳細画面の `Project roles` セクションで `+ Manage project roles` をクリック
   - 対象のプロジェクトを選択
   - `Asset Manager Contributor` または `Asset Manager Admin` ロールを割り当て
   - 保存

#### プロジェクトIDと組織IDの確認方法

**Unity Editorから確認:**
- Edit > Project Settings > Services でプロジェクトIDを確認

**Unity Cloud Dashboardから確認:**
- プロジェクトのAsset Managerページにアクセス
- URLから確認: `https://cloud.unity.com/home/organizations/{組織ID}/projects/{プロジェクトID}/...`

#### 認証方式について

このツールは2種類の認証方式に対応しています：

1. **Basic認証** (`main_webapi.py`で使用)
   - Key IDとSecret Keyをコロン(:)で連結し、Base64エンコード
   - `Authorization: Basic <encoded_credentials>` ヘッダーで送信
   - シンプルだが、リクエストごとにマスターキーを送信

2. **Bearer トークン認証** (推奨)
   - Token Exchange APIでアクセストークンを取得
   - エンドポイント: `https://services.api.unity.com/auth/v1/token-exchange`
   - 取得したトークンを `Authorization: Bearer <token>` で送信
   - セキュアで、トークンは有限の寿命を持つ

### 4. 入力ファイルの配置

変換したいOBJファイルを `assets_input/` ディレクトリに配置します。

```bash
assets_input/your_model.obj
```

スクリプト内の `INPUT_FILE_PATH` 変数を適宜変更してください。

## 使用方法

### SDK版を使用する場合

```bash
python main.py
```

### 完全REST API版を使用する場合

```bash
python main_webapi.py
```

### 処理の流れ

1. **環境変数とファイルの存在確認**
2. **認証**
   - SDK版: Unity Cloud SDKの初期化とサービスアカウント認証
   - REST API版: Basic認証情報の準備
3. **アセットの作成**
   - POST `/assets/v1/projects/{projectId}/assets`
4. **データセットの作成**
   - POST `/assets/v1/projects/{projectId}/assets/{assetId}/versions/{version}/datasets`
5. **ファイルのアップロード**
   - 署名付きURLを取得してファイルをアップロード
6. **GLTF変換処理の開始**
   - POST `.../datasets/{datasetId}/transformations`
   - ワークフロータイプ: `OptimizeAndConvert`
7. **変換ステータスのポーリング**
   - GET `.../transformations/{transformationId}`
   - 最大5分間、10秒間隔でステータスを確認
8. **変換済みファイルのダウンロード**
   - 変換後のデータセット（`Optimize and convert`）から該当ファイルを検索
   - ダウンロードURLを取得してファイルを保存

変換されたGLTFファイルは `assets_output/` ディレクトリに保存されます。

## ファイル構成

```
.
├── main.py                  # Unity Cloud SDK使用版のメインスクリプト
├── main_webapi.py          # 完全REST API実装版のメインスクリプト
├── requirements.txt        # 依存パッケージリスト
├── .env                    # 環境変数設定ファイル（要作成）
├── .gitignore              # Git除外設定
├── assets_input/           # 入力ファイル格納ディレクトリ
├── assets_output/          # 出力ファイル格納ディレクトリ
└── README.md               # このファイル
```

## API仕様

### ベースURL

- **本番環境**: `https://services.api.unity.com`
- **ステージング環境**: `https://staging.services.api.unity.com` (テスト用)

### 主要エンドポイント

| 操作 | メソッド | エンドポイント |
|------|---------|--------------|
| トークン取得 | POST | `/auth/v1/token-exchange?projectId={projectId}` |
| アセット作成 | POST | `/assets/v1/projects/{projectId}/assets` |
| アセット一覧 | GET | `/assets/v1/projects/{projectId}/assets` |
| アセット詳細 | GET | `/assets/v1/projects/{projectId}/assets/{assetId}` |
| データセット作成 | POST | `/assets/v1/projects/{projectId}/assets/{assetId}/versions/{version}/datasets` |
| ファイルアップロード | POST | `/assets/v1/projects/{projectId}/assets/{assetId}/versions/{version}/datasets/{datasetId}/files` |
| 変換開始 | POST | `/assets/v1/projects/{projectId}/assets/{assetId}/versions/{version}/datasets/{datasetId}/transformations` |
| 変換ステータス確認 | GET | `/assets/v1/projects/{projectId}/assets/{assetId}/versions/{version}/datasets/{datasetId}/transformations/{transformationId}` |

### エラーレスポンス構造

APIが返すエラーレスポンスには以下の情報が含まれます：

```json
{
  "requestId": "リクエスト固有のID",
  "code": "数値エラーコード",
  "title": "エラーの概要",
  "detail": "詳細なエラーメッセージ"
}
```

一般的なHTTPステータスコード：
- `2xx`: 成功
- `400`: 不正なリクエスト
- `401`: 認証エラー（トークンが無効または期限切れ）
- `403`: 権限不足（ロールが適切に割り当てられていない）
- `404`: リソースが見つからない
- `5xx`: サーバーエラー

## トラブルシューティング

### 認証エラー（401 Unauthorized）

- `.env` ファイルの設定値が正しいか確認
- Key IDとSecret Keyに余分な空白や改行が含まれていないか確認
- サービスアカウントのキーが有効か確認（無効化されていないか）

### 権限エラー（403 Forbidden）

- サービスアカウントに適切なロール（`Asset Manager Contributor` または `Asset Manager Admin`）が割り当てられているか確認
- 対象プロジェクトに対してロールが割り当てられているか確認（組織レベルではなくプロジェクトレベル）

### 変換エラー

- 入力ファイルが有効なOBJフォーマットか確認
- ファイルサイズがUnity Asset Managerの制限を超えていないか確認
- 変換ステータスのエラーメッセージを確認

### タイムアウトエラー

- 大きなファイルの場合、変換に5分以上かかる場合があります
- スクリプト内のタイムアウト設定（デフォルト300秒）を調整してください：

```python
# main.pyまたはmain_webapi.pyで
timeout = 600  # 10分に延長
```

### ファイルが見つからないエラー

- `INPUT_FILE_PATH` が正しく設定されているか確認
- `assets_input/` ディレクトリが存在するか確認
- ファイルパスが正しいか確認（相対パス）

## 技術詳細

### 変換パラメータ

```python
transformation_params = {
    "outputs": [
        {
            "outputName": "output.gltf",
            "outputFormat": "gltf"
        }
    ]
}
```

### 対応フォーマット

- **入力**: OBJ（Wavefront OBJ形式）
- **出力**: GLTF（GL Transmission Format）

### ファイルアップロードの仕組み

1. Unity APIから署名付きURL（Azure Blob Storage）を取得
2. 取得したURLに対してPUT リクエストでファイルをアップロード
3. 必要に応じてアップロード完了を通知

## セキュリティ上の注意

- **Secret Keyを絶対に公開リポジトリにコミットしないでください**
- `.env` ファイルは `.gitignore` に含まれています
- 本番環境では環境変数を安全に管理してください（環境変数、シークレット管理サービスなど）
- Bearer トークン認証方式の使用を推奨します

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 参考リンク

- [Unity Asset Manager ドキュメント](https://docs.unity.com/en-us/cloud/asset-manager/)
- [Unity Cloud Python SDK](https://pypi.org/project/unity-cloud/)
- [Unity Services Web API](https://services.docs.unity.com/)
- [Unity Service Accounts](https://docs.unity.com/ugs/en-us/manual/game-server-hosting/manual/concepts/authentication-service-accounts)
- [Asset Manager API v1 仕様](https://services.docs.unity.com/assets-manager/v1/)

## 貢献

バグ報告や機能追加のプルリクエストを歓迎します。