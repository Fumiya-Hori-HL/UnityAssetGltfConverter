# Unity Asset Manager REST API - シーケンス図

main_webapi.pyの処理フローを示すシーケンス図です。

## 全体フロー

```mermaid
sequenceDiagram
    participant User as ユーザー
    participant Script as main_webapi.py
    participant UnityAPI as Unity Asset Manager API
    participant AzureBlob as Azure Blob Storage

    User->>Script: スクリプト実行

    %% ステップ1: 認証
    Note over Script: ステップ1: 認証情報の準備
    Script->>Script: Basic認証情報を作成<br/>(Key ID + Secret Key)

    %% ステップ2: アセット作成
    Note over Script,UnityAPI: ステップ2: アセット作成
    Script->>UnityAPI: POST /assets<br/>{"name": "Web API - your_model.obj"}
    UnityAPI-->>Script: {"assetId", "assetVersion", "datasets"}

    %% ステップ3: データセット取得
    Note over Script: ステップ3: データセット取得
    Script->>Script: レスポンスから<br/>Sourceデータセットを抽出

    %% ステップ4: ファイルアップロード
    Note over Script,AzureBlob: ステップ4: ファイルアップロード
    Script->>UnityAPI: POST /datasets/{datasetId}/files<br/>{"filePath": "your_model.obj"}
    UnityAPI-->>Script: {"uploadUrl": "https://..."}
    Script->>AzureBlob: PUT {uploadUrl}<br/>Content-Type: application/octet-stream<br/>x-ms-blob-type: BlockBlob
    AzureBlob-->>Script: 200 OK

    %% ステップ5: 変換開始
    Note over Script,UnityAPI: ステップ5: GLTF変換処理の開始
    Script->>UnityAPI: POST /transformations/start/{workflowType}<br/>{"extraParameters": {...}}
    UnityAPI-->>Script: {"transformationId": "..."}

    %% ステップ5.5: AutoSubmit
    Note over Script,UnityAPI: ステップ5.5: AutoSubmit有効化（オプション）
    Script->>UnityAPI: POST /autosubmit<br/>{"changeLog": "..."}
    UnityAPI-->>Script: 400 Bad Request<br/>(変換中は失敗)

    %% ステップ6: ステータスポーリング
    Note over Script,UnityAPI: ステップ6: 変換処理の完了を待機
    loop 10秒ごとにポーリング (最大5分)
        Script->>UnityAPI: GET /transformations/{transformationId}
        UnityAPI-->>Script: {"status": "Pending/Running/Succeeded"}
        alt status == "Succeeded"
            Note over Script: 変換完了
        else status == "Failed"
            Script->>User: エラー終了
        end
    end

    %% ステップ7: ダウンロード
    Note over Script,UnityAPI: ステップ7: 変換後ファイルのダウンロード
    Script->>UnityAPI: GET /assets/{assetId}/versions/{versionId}<br/>?IncludeFields=files,files.*
    UnityAPI-->>Script: {"files": [{"filePath": "your_model.glb", ...}]}
    Script->>Script: filesフィールドから<br/>対象ファイルを検索
    Script->>UnityAPI: GET /files/{filePath}/download-url
    UnityAPI-->>Script: {"url": "https://..."}
    Script->>AzureBlob: GET {downloadUrl}
    AzureBlob-->>Script: GLBファイルデータ
    Script->>Script: assets_output/your_model.glb に保存

    Script->>User: 処理完了
```

## 詳細フロー（各ステップ）

### ステップ4: ファイルアップロード詳細

```mermaid
sequenceDiagram
    participant Script as main_webapi.py
    participant UnityAPI as Unity API
    participant AzureBlob as Azure Blob Storage

    Note over Script,AzureBlob: ファイルアップロードの詳細フロー

    Script->>Script: ファイルサイズを取得<br/>your_model.obj (34MB)

    Script->>UnityAPI: POST /files<br/>{"filePath": "your_model.obj"}
    Note right of UnityAPI: OpenAPI仕様書準拠<br/>filePath (required)
    UnityAPI->>UnityAPI: 署名付きURL生成<br/>(Azure Blob Storage)
    UnityAPI-->>Script: {"uploadUrl": "https://blob.core.windows.net/..."}

    Script->>Script: ファイルを読み込み<br/>(バイナリモード)
    Script->>AzureBlob: PUT {uploadUrl}<br/>Headers:<br/>- Content-Type: application/octet-stream<br/>- x-ms-blob-type: BlockBlob
    Note right of AzureBlob: Azure必須ヘッダー
    AzureBlob->>AzureBlob: ファイルを保存
    AzureBlob-->>Script: 200 OK

    opt completeUrlが存在する場合
        Script->>UnityAPI: POST {completeUrl}
        UnityAPI-->>Script: 200 OK
    end
```

### ステップ5: 変換処理開始詳細

```mermaid
sequenceDiagram
    participant Script as main_webapi.py
    participant UnityAPI as Unity API
    participant TransformEngine as 変換エンジン

    Note over Script,TransformEngine: GLTF変換処理の開始

    Script->>Script: 変換パラメータを準備<br/>{"outputFileName": "your_model",<br/>"exportFormats": ["glb"]}

    Script->>UnityAPI: POST /transformations/start/higher-tier-optimize-and-convert<br/>{"extraParameters": {...}}
    Note right of UnityAPI: OpenAPI仕様書準拠<br/>workflowTypeはURLパス

    UnityAPI->>UnityAPI: パラメータを検証
    UnityAPI->>TransformEngine: 変換ジョブを作成
    TransformEngine-->>UnityAPI: jobId
    UnityAPI-->>Script: {"transformationId": "...",<br/>"jobId": "...",<br/>"status": "Pending"}

    Note over TransformEngine: バックグラウンドで変換処理
```

### ステップ6: ステータスポーリング詳細

```mermaid
sequenceDiagram
    participant Script as main_webapi.py
    participant UnityAPI as Unity API
    participant TransformEngine as 変換エンジン

    Note over Script,TransformEngine: 変換ステータスのポーリング (最大5分)

    loop 10秒間隔でポーリング
        Script->>UnityAPI: GET /transformations/{transformationId}
        UnityAPI->>TransformEngine: ステータス確認
        TransformEngine-->>UnityAPI: status, progress
        UnityAPI-->>Script: {"status": "Pending",<br/>"progress": 0}
        Note over Script: 10秒待機

        Script->>UnityAPI: GET /transformations/{transformationId}
        UnityAPI->>TransformEngine: ステータス確認
        TransformEngine-->>UnityAPI: status, progress
        UnityAPI-->>Script: {"status": "Running",<br/>"progress": 50}
        Note over Script: 10秒待機

        Script->>UnityAPI: GET /transformations/{transformationId}
        UnityAPI->>TransformEngine: ステータス確認
        TransformEngine-->>UnityAPI: status, progress
        UnityAPI-->>Script: {"status": "Succeeded",<br/>"progress": 100,<br/>"outputDatasetId": "..."}

        Note over Script: status.upper() == "SUCCEEDED"<br/>→ ループ終了
    end
```

### ステップ7: ファイルダウンロード詳細

```mermaid
sequenceDiagram
    participant Script as main_webapi.py
    participant UnityAPI as Unity API
    participant AzureBlob as Azure Blob Storage

    Note over Script,AzureBlob: 変換後ファイルのダウンロード

    Script->>UnityAPI: GET /assets/{assetId}/versions/{versionId}<br/>?IncludeFields=files,files.*,datasets,datasets.*
    Note right of UnityAPI: Asset詳細APIを使用<br/>(filesフィールドを取得)
    UnityAPI-->>Script: {"files": [<br/>  {"filePath": "your_model.obj",<br/>   "datasetIds": ["source-id"]},<br/>  {"filePath": "your_model.glb",<br/>   "datasetIds": ["output-id"],<br/>   "status": "Uploaded",<br/>   "fileSize": 23041308}<br/>],<br/>"datasets": [...]}

    Script->>Script: filesフィールドから検索<br/>- filePath == "your_model.glb"<br/>- datasetIds内のデータセット名が<br/>  "Optimize and convert"

    Script->>Script: ファイルパスをURLエンコード<br/>requests.utils.quote("your_model.glb")

    Script->>UnityAPI: GET /files/{encodedFilePath}/download-url
    Note right of UnityAPI: ダウンロードURL取得API
    UnityAPI->>UnityAPI: 署名付きURL生成<br/>(Azure Blob Storage)
    UnityAPI-->>Script: {"url": "https://blob.core.windows.net/..."}

    Script->>AzureBlob: GET {downloadUrl}
    AzureBlob-->>Script: GLBファイルデータ (23MB)

    Script->>Script: ファイルを保存<br/>assets_output/your_model.glb
```

## エラーハンドリング

```mermaid
sequenceDiagram
    participant Script as main_webapi.py
    participant UnityAPI as Unity API
    participant User as ユーザー

    Note over Script,User: エラーハンドリングのフロー

    Script->>UnityAPI: API リクエスト

    alt 認証エラー (401)
        UnityAPI-->>Script: 401 Unauthorized
        Script->>Script: log_error_response()
        Script->>User: エラーメッセージ表示:<br/>認証情報を確認してください
        Script->>User: sys.exit(1)
    else 権限エラー (403)
        UnityAPI-->>Script: 403 Forbidden<br/>{"detail": "Organization does not have<br/>the entitlement..."}
        Script->>Script: log_error_response()
        Script->>User: エラーメッセージ表示:<br/>ワークフロータイプを確認してください<br/>(無料プランではfree-tier-*を使用)
        Script->>User: sys.exit(1)
    else リソースが見つからない (404)
        UnityAPI-->>Script: 404 Not Found
        Script->>Script: log_error_response()
        Script->>User: エラーメッセージ表示:<br/>指定されたリソースが見つかりません
        Script->>User: sys.exit(1)
    else サーバーエラー (500)
        UnityAPI-->>Script: 500 Internal Server Error
        Script->>Script: log_error_response()
        Script->>User: エラーメッセージ表示:<br/>サーバーエラーが発生しました
        Script->>User: sys.exit(1)
    else 変換失敗
        UnityAPI-->>Script: {"status": "Failed",<br/>"errorMessage": "..."}
        Script->>User: エラーメッセージ表示:<br/>変換が失敗しました
        Script->>User: sys.exit(1)
    else 変換タイムアウト
        Note over Script: 5分経過してもSucceededにならない
        Script->>User: エラーメッセージ表示:<br/>変換がタイムアウトしました
        Script->>User: sys.exit(1)
    else ファイルが見つからない
        Script->>Script: Asset詳細APIのfiles配列を検索
        Note over Script: 対象ファイルが見つからない
        Script->>User: エラーメッセージ表示:<br/>ファイル '{file_name}' が<br/>データセット '{dataset_name}'<br/>内に見つかりません
        Script->>User: sys.exit(1)
    else 正常
        UnityAPI-->>Script: 200 OK
        Script->>User: 処理継続
    end
```

## データフロー

```mermaid
graph LR
    A[ユーザー] -->|実行| B[main_webapi.py]
    B -->|1. 認証| C[Unity API]
    B -->|2. アセット作成| C
    C -->|assetId, datasets| B
    B -->|3. データセットID取得| B
    B -->|4. ファイルアップロード準備| C
    C -->|uploadUrl| B
    B -->|4. PUT ファイル| D[Azure Blob Storage]
    D -->|200 OK| B
    B -->|5. 変換開始| C
    C -->|transformationId| B
    B -->|6. ステータスポーリング| C
    C -->|status: Succeeded| B
    B -->|7. Asset詳細取得| C
    C -->|files配列| B
    B -->|7. ダウンロードURL取得| C
    C -->|downloadUrl| B
    B -->|7. GET ファイル| D
    D -->|GLBデータ| B
    B -->|保存| E[assets_output/your_model.glb]
    E -->|完了| A

    style B fill:#e1f5ff
    style C fill:#fff4e1
    style D fill:#f0e1ff
    style E fill:#e1ffe1
```

## OpenAPI仕様書準拠のポイント

### リクエストフィールド名

```mermaid
graph TD
    A[OpenAPI仕様書] -->|ファイルアップロード| B["filePath (camelCase)"]
    A -->|変換リクエスト| C["extraParameters (camelCase)"]
    A -->|変換URL| D["workflowType in URL path"]

    B -.->|以前は| B2["FilePath (PascalCase) ❌"]
    C -.->|以前は| C2["parameters ❌"]
    D -.->|以前は| D2["workflowType in body ❌"]

    style B fill:#e1ffe1
    style C fill:#e1ffe1
    style D fill:#e1ffe1
    style B2 fill:#ffe1e1
    style C2 fill:#ffe1e1
    style D2 fill:#ffe1e1
```

### レスポンスフィールド名

```mermaid
graph TD
    A[OpenAPI仕様書] -->|ファイルアップロード| B["uploadUrl"]
    A -->|変換開始| C["transformationId"]
    A -->|ダウンロードURL| D["url"]

    B -.->|以前は| B2["uploadUrl or url ❌"]
    C -.->|以前は| C2["id ❌"]

    style B fill:#e1ffe1
    style C fill:#e1ffe1
    style D fill:#e1ffe1
    style B2 fill:#ffe1e1
    style C2 fill:#ffe1e1
```
