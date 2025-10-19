"""
Unity Asset Manager - 全Web API実装版

このスクリプトは、Unity Cloud Asset ManagerのREST APIのみを使用して
ファイルのアップロードと変換を行います。

段階的なテスト用に各ステップを分離しています。
"""

import os
import base64
import json
import time
import sys
import requests
from dotenv import load_dotenv
from pathlib import Path

# .envファイルから環境変数を読み込む
load_dotenv()

# --- 設定項目 ---
ORG_ID = os.getenv("UNITY_CLOUD_ORGANIZATION_ID")
PROJECT_ID = os.getenv("UNITY_CLOUD_PROJECT_ID")
KEY_ID = os.getenv("UNITY_CLOUD_KEY_ID")
SECRET_KEY = os.getenv("UNITY_CLOUD_SECRET_KEY")

# 変換対象のファイルパス
INPUT_FILE_PATH = "assets_input/your_model.obj"
OUTPUT_FOLDER = "assets_output"

# Unity Services API Base URL
UNITY_API_BASE = "https://services.api.unity.com"


def log_error_response(error_response):
    """
    Unity API のエラーレスポンスを構造化してログ出力する

    Parameters
    ----------
    error_response : requests.Response
        エラーレスポンスオブジェクト
    """
    try:
        error_data = error_response.json()
        print(f"    エラーステータス: {error_response.status_code}")

        # webapi_endpoint.mdに記載されている構造化エラーフィールド
        if "requestId" in error_data:
            print(f"    Request ID: {error_data['requestId']}")
        if "code" in error_data:
            print(f"    Error Code: {error_data['code']}")
        if "title" in error_data:
            print(f"    Title: {error_data['title']}")
        if "detail" in error_data:
            print(f"    Detail: {error_data['detail']}")

        # その他のフィールドも表示
        other_fields = {k: v for k, v in error_data.items()
                       if k not in ["requestId", "code", "title", "detail"]}
        if other_fields:
            print(f"    その他の情報: {json.dumps(other_fields, indent=6, ensure_ascii=False)}")
    except json.JSONDecodeError:
        # JSONでない場合はテキストをそのまま表示
        print(f"    エラーステータス: {error_response.status_code}")
        print(f"    エラーレスポンス: {error_response.text}")


def get_access_token(key_id, secret_key, project_id):
    """
    サービスアカウント認証でアクセストークンを取得する

    Parameters
    ----------
    key_id : str
        サービスアカウントのKey ID
    secret_key : str
        サービスアカウントのSecret Key
    project_id : str
        プロジェクトID

    Returns
    -------
    str
        アクセストークン
    """
    print("  アクセストークンを取得中...")

    # Base64エンコード: key_id:secret_key
    credentials = f"{key_id}:{secret_key}"
    encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

    # Token Exchange APIを呼び出し
    url = f"{UNITY_API_BASE}/auth/v1/token-exchange"
    headers = {
        "Authorization": f"Basic {encoded_credentials}"
    }
    params = {
        "projectId": project_id
    }

    try:
        response = requests.post(url, headers=headers, params=params)
        response.raise_for_status()

        token_data = response.json()

        # レスポンス構造を確認
        print(f"  レスポンス構造: {list(token_data.keys())}")

        # 複数の可能性のあるキー名を試す
        token = token_data.get("token") or token_data.get("accessToken") or token_data.get("access_token")

        if not token:
            print(f"  警告: トークンが見つかりません。レスポンス全体: {token_data}")
            raise ValueError("アクセストークンがレスポンスに含まれていません")

        print(f"  ✓ アクセストークン取得成功")
        print(f"    トークン（最初の10文字）: {token[:10]}...")

        return token
    except requests.exceptions.RequestException as e:
        print(f"  ✗ アクセストークンの取得に失敗: {e}")
        if hasattr(e, 'response') and e.response is not None:
            log_error_response(e.response)
        raise


def create_asset_via_api(auth_credentials, project_id, asset_name, asset_type="MODEL_3D", description=""):
    """
    Web APIでアセットを作成する

    Parameters
    ----------
    auth_credentials : str
        Base64エンコードされた認証情報
    project_id : str
        プロジェクトID
    asset_name : str
        アセット名
    asset_type : str
        アセットタイプ（デフォルト: MODEL_3D）
    description : str
        アセットの説明（オプション）

    Returns
    -------
    dict
        作成されたアセット情報
    """
    print(f"  アセット '{asset_name}' を作成中...")

    url = f"{UNITY_API_BASE}/assets/v1/projects/{project_id}/assets"

    headers = {
        "Authorization": f"Basic {auth_credentials}",
        "Content-Type": "application/json"
    }

    body = {
        "name": asset_name,
        "type": asset_type
    }

    if description:
        body["description"] = description

    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()

        asset_data = response.json()

        print(f"  ✓ アセット作成成功")
        print(f"    Asset ID: {asset_data.get('assetId')}")
        print(f"    Version: {asset_data.get('assetVersion')}")

        return asset_data
    except requests.exceptions.RequestException as e:
        print(f"  ✗ アセット作成に失敗: {e}")
        if hasattr(e, 'response') and e.response is not None:
            log_error_response(e.response)
        raise


def create_dataset_via_api(auth_credentials, project_id, asset_id, version_id, dataset_name):
    """
    Web APIでデータセットを作成する

    Parameters
    ----------
    auth_credentials : str
        Base64エンコードされた認証情報
    project_id : str
        プロジェクトID
    asset_id : str
        アセットID
    version_id : str
        バージョンID
    dataset_name : str
        データセット名

    Returns
    -------
    dict
        作成されたデータセット情報
    """
    print(f"  データセット '{dataset_name}' を作成中...")

    url = f"{UNITY_API_BASE}/assets/v1/projects/{project_id}/assets/{asset_id}/versions/{version_id}/datasets"

    headers = {
        "Authorization": f"Basic {auth_credentials}",
        "Content-Type": "application/json"
    }

    body = {
        "name": dataset_name
    }

    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()

        dataset_data = response.json()

        print(f"  ✓ データセット作成成功")
        print(f"    Dataset ID: {dataset_data.get('datasetId')}")

        return dataset_data
    except requests.exceptions.RequestException as e:
        print(f"  ✗ データセット作成に失敗: {e}")
        if hasattr(e, 'response') and e.response is not None:
            log_error_response(e.response)
        raise


def upload_file_via_api(auth_credentials, project_id, asset_id, version_id, dataset_id, file_path):
    """
    Web APIでファイルをアップロードする

    Parameters
    ----------
    auth_credentials : str
        Base64エンコードされた認証情報
    project_id : str
        プロジェクトID
    asset_id : str
        アセットID
    version_id : str
        バージョンID
    dataset_id : str
        データセットID
    file_path : str
        アップロードするファイルのパス

    Returns
    -------
    dict
        アップロード結果情報
    """
    print(f"  ファイル '{os.path.basename(file_path)}' をアップロード中...")

    # ステップ1: アップロード用の署名付きURLを取得
    # このエンドポイントはAPIパターンから推測
    url_request = f"{UNITY_API_BASE}/assets/v1/projects/{project_id}/assets/{asset_id}/versions/{version_id}/datasets/{dataset_id}/files"

    headers = {
        "Authorization": f"Basic {auth_credentials}",
        "Content-Type": "application/json"
    }

    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    body = {
        "FilePath": file_name,
        "Length": file_size
    }

    try:
        # 署名付きURLの取得
        print(f"    署名付きURLを取得中...")
        response = requests.post(url_request, headers=headers, json=body)
        response.raise_for_status()

        upload_info = response.json()
        print(f"    ✓ 署名付きURL取得成功")

        # ステップ2: 署名付きURLにファイルをアップロード
        upload_url = upload_info.get("uploadUrl") or upload_info.get("url")

        if not upload_url:
            print(f"    警告: アップロードURLが見つかりません。レスポンス: {upload_info}")
            raise ValueError("アップロードURLがレスポンスに含まれていません")

        print(f"    ファイルをアップロード中... (サイズ: {file_size} bytes)")

        with open(file_path, 'rb') as f:
            file_data = f.read()

        # 署名付きURLへのアップロード（Azure Blob Storage）
        upload_headers = {
            'Content-Type': 'application/octet-stream',
            'x-ms-blob-type': 'BlockBlob'  # Azure Blob Storage必須ヘッダー
        }
        upload_response = requests.put(
            upload_url,
            data=file_data,
            headers=upload_headers
        )
        upload_response.raise_for_status()

        print(f"  ✓ ファイルアップロード成功")

        # ステップ3: アップロード完了を通知（必要な場合）
        # 一部のAPIでは完了通知が必要な場合がある
        complete_url = upload_info.get("completeUrl")
        if complete_url:
            print(f"    アップロード完了を通知中...")
            complete_headers = {
                "Authorization": f"Basic {auth_credentials}"
            }
            complete_response = requests.post(complete_url, headers=complete_headers)
            complete_response.raise_for_status()
            print(f"    ✓ アップロード完了通知成功")

        return upload_info

    except requests.exceptions.RequestException as e:
        print(f"  ✗ ファイルアップロードに失敗: {e}")
        if hasattr(e, 'response') and e.response is not None:
            log_error_response(e.response)
        raise


def start_transformation_via_api(auth_credentials, project_id, asset_id, version_id, dataset_id, workflow_type, parameters):
    """
    Web APIで変換処理を開始する

    Parameters
    ----------
    auth_credentials : str
        Base64エンコードされた認証情報
    project_id : str
        プロジェクトID
    asset_id : str
        アセットID
    version_id : str
        バージョンID
    dataset_id : str
        データセットID
    workflow_type : str
        ワークフロータイプ（例: OptimizeAndConvert）
    parameters : dict
        変換パラメータ

    Returns
    -------
    dict
        変換情報（transformation IDを含む）
    """
    print(f"  変換処理を開始中... (ワークフロー: {workflow_type})")

    # このエンドポイントはAPIパターンから推測
    url = f"{UNITY_API_BASE}/assets/v1/projects/{project_id}/assets/{asset_id}/versions/{version_id}/datasets/{dataset_id}/transformations"

    headers = {
        "Authorization": f"Basic {auth_credentials}",
        "Content-Type": "application/json"
    }

    body = {
        "workflowType": workflow_type,
        "parameters": parameters
    }

    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()

        transformation_data = response.json()

        print(f"  ✓ 変換処理開始成功")
        print(f"    Transformation ID: {transformation_data.get('id')}")

        return transformation_data

    except requests.exceptions.RequestException as e:
        print(f"  ✗ 変換処理の開始に失敗: {e}")
        if hasattr(e, 'response') and e.response is not None:
            log_error_response(e.response)
        raise


def get_transformation_status_via_api(auth_credentials, project_id, asset_id, version_id, dataset_id, transformation_id):
    """
    Web APIで変換ステータスを確認する

    Parameters
    ----------
    auth_credentials : str
        Base64エンコードされた認証情報
    project_id : str
        プロジェクトID
    asset_id : str
        アセットID
    version_id : str
        バージョンID
    dataset_id : str
        データセットID
    transformation_id : str
        変換ID

    Returns
    -------
    dict
        変換ステータス情報
    """
    url = f"{UNITY_API_BASE}/assets/v1/projects/{project_id}/assets/{asset_id}/versions/{version_id}/datasets/{dataset_id}/transformations/{transformation_id}"

    headers = {
        "Authorization": f"Basic {auth_credentials}"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"  ✗ 変換ステータスの取得に失敗: {e}")
        if hasattr(e, 'response') and e.response is not None:
            log_error_response(e.response)
        raise


def get_asset_details_via_api(auth_credentials, project_id, asset_id):
    """
    Web APIでアセットの詳細情報を取得する

    Parameters
    ----------
    auth_credentials : str
        Base64エンコードされた認証情報
    project_id : str
        プロジェクトID
    asset_id : str
        アセットID

    Returns
    -------
    dict
        アセットの詳細情報
    """
    url = f"{UNITY_API_BASE}/assets/v1/projects/{project_id}/assets/{asset_id}"

    headers = {
        "Authorization": f"Basic {auth_credentials}"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"  ✗ アセット詳細の取得に失敗: {e}")
        if hasattr(e, 'response') and e.response is not None:
            log_error_response(e.response)
        raise


def download_file_via_api(auth_credentials, project_id, asset_id, version_id, dataset_name, file_name, output_path):
    """
    Web APIで変換後のファイルをダウンロードする

    Parameters
    ----------
    auth_credentials : str
        Base64エンコードされた認証情報
    project_id : str
        プロジェクトID
    asset_id : str
        アセットID
    version_id : str
        バージョンID
    dataset_name : str
        データセット名
    file_name : str
        ダウンロードするファイル名
    output_path : str
        保存先のパス

    Returns
    -------
    str
        保存されたファイルのパス
    """
    print(f"  ファイル '{file_name}' をダウンロード中...")

    try:
        # ステップ1: アセット詳細を取得してデータセットIDを見つける
        print(f"    アセット詳細を取得中...")
        asset_details = get_asset_details_via_api(auth_credentials, project_id, asset_id)

        # データセットを検索
        target_dataset = None
        if "datasets" in asset_details:
            for dataset in asset_details["datasets"]:
                if dataset.get("name") == dataset_name:
                    target_dataset = dataset
                    break

        if not target_dataset:
            raise ValueError(f"データセット '{dataset_name}' が見つかりません")

        dataset_id = target_dataset.get("id")
        print(f"    ✓ データセット発見 (ID: {dataset_id})")

        # ステップ2: ファイル情報を取得
        print(f"    ファイル情報を取得中...")
        target_file = None
        if "files" in target_dataset:
            for file_info in target_dataset["files"]:
                if file_info.get("path") == file_name or file_info.get("name") == file_name:
                    target_file = file_info
                    break

        if not target_file:
            raise ValueError(f"ファイル '{file_name}' がデータセット内に見つかりません")

        print(f"    ✓ ファイル発見")

        # ステップ3: ダウンロードURLを取得
        # ファイル情報にURLが含まれている場合
        download_url = target_file.get("downloadUrl") or target_file.get("url")

        # URLが含まれていない場合は、別のエンドポイントから取得
        if not download_url:
            file_id = target_file.get("id")
            url_request = f"{UNITY_API_BASE}/assets/v1/projects/{project_id}/assets/{asset_id}/versions/{version_id}/datasets/{dataset_id}/files/{file_id}"
            headers = {"Authorization": f"Basic {auth_credentials}"}

            response = requests.get(url_request, headers=headers)
            response.raise_for_status()

            file_details = response.json()
            download_url = file_details.get("downloadUrl") or file_details.get("url")

        if not download_url:
            raise ValueError("ダウンロードURLが取得できませんでした")

        print(f"    ダウンロードURL取得成功")

        # ステップ4: ファイルをダウンロード
        print(f"    ファイルをダウンロード中...")
        response = requests.get(download_url)
        response.raise_for_status()

        # ステップ5: ファイルを保存
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)

        print(f"  ✓ ファイルダウンロード成功: {output_path}")

        return output_path

    except requests.exceptions.RequestException as e:
        print(f"  ✗ ファイルダウンロードに失敗: {e}")
        if hasattr(e, 'response') and e.response is not None:
            log_error_response(e.response)
        raise
    except Exception as e:
        print(f"  ✗ ファイルダウンロードに失敗: {e}")
        raise


def main():
    """
    メイン処理：OBJファイルのアップロード、GLTF変換、ダウンロードの完全なワークフロー
    """
    print("\n" + "="*60)
    print("Unity Asset Manager - 完全REST API実装版")
    print("="*60)

    # --- 0. 事前チェック ---
    required_configs = [ORG_ID, PROJECT_ID, KEY_ID, SECRET_KEY]
    if not all(required_configs):
        print("\nエラー: .envファイルに必要な設定が不足しています。")
        print("UNITY_CLOUD_ORGANIZATION_ID, UNITY_CLOUD_PROJECT_ID, UNITY_CLOUD_KEY_ID, UNITY_CLOUD_SECRET_KEY")
        sys.exit(1)

    if not os.path.exists(INPUT_FILE_PATH):
        print(f"\nエラー: 入力ファイルが見つかりません: {INPUT_FILE_PATH}")
        sys.exit(1)

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    print(f"\n設定情報:")
    print(f"  Organization ID: {ORG_ID}")
    print(f"  Project ID: {PROJECT_ID}")
    print(f"  Key ID: {KEY_ID[:8]}...")
    print(f"  入力ファイル: {INPUT_FILE_PATH}")
    print(f"  出力フォルダ: {OUTPUT_FOLDER}")

    try:
        # === ステップ1: 認証情報の準備 ===
        print("\n" + "-"*60)
        print("ステップ1: 認証情報の準備")
        print("-"*60)

        # Basic認証用の認証情報を作成
        credentials = f"{KEY_ID}:{SECRET_KEY}"
        auth_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        print("  ✓ Basic認証情報を作成しました")

        # === ステップ2: アセット作成 ===
        print("\n" + "-"*60)
        print("ステップ2: アセット作成")
        print("-"*60)

        asset_name = f"Web API - {os.path.basename(INPUT_FILE_PATH)}"
        asset = create_asset_via_api(
            auth_credentials=auth_credentials,
            project_id=PROJECT_ID,
            asset_name=asset_name,
            description="REST API経由でアップロードされた3Dモデル"
        )

        asset_id = asset.get("assetId")
        version_id = asset.get("assetVersion")

        if not asset_id or not version_id:
            raise ValueError("アセット作成に失敗: IDまたはバージョンが取得できませんでした")

        # === ステップ3: データセット作成 ===
        print("\n" + "-"*60)
        print("ステップ3: データセット作成")
        print("-"*60)

        dataset = create_dataset_via_api(
            auth_credentials=auth_credentials,
            project_id=PROJECT_ID,
            asset_id=asset_id,
            version_id=version_id,
            dataset_name="source_obj"
        )

        dataset_id = dataset.get("datasetId")

        if not dataset_id:
            raise ValueError("データセット作成に失敗: IDが取得できませんでした")

        # === ステップ4: ファイルアップロード ===
        print("\n" + "-"*60)
        print("ステップ4: ファイルアップロード")
        print("-"*60)

        upload_file_via_api(
            auth_credentials=auth_credentials,
            project_id=PROJECT_ID,
            asset_id=asset_id,
            version_id=version_id,
            dataset_id=dataset_id,
            file_path=INPUT_FILE_PATH
        )

        # === ステップ5: 変換処理の開始 ===
        print("\n" + "-"*60)
        print("ステップ5: GLTF変換処理の開始")
        print("-"*60)

        output_filename = f"{os.path.splitext(os.path.basename(INPUT_FILE_PATH))[0]}.gltf"

        transformation_params = {
            "outputs": [
                {
                    "outputName": output_filename,
                    "outputFormat": "gltf"
                }
            ]
        }

        transformation = start_transformation_via_api(
            auth_credentials=auth_credentials,
            project_id=PROJECT_ID,
            asset_id=asset_id,
            version_id=version_id,
            dataset_id=dataset_id,
            workflow_type="OptimizeAndConvert",
            parameters=transformation_params
        )

        transformation_id = transformation.get("id")

        if not transformation_id:
            raise ValueError("変換処理の開始に失敗: Transformation IDが取得できませんでした")

        # === ステップ6: 変換ステータスのポーリング ===
        print("\n" + "-"*60)
        print("ステップ6: 変換処理の完了を待機 (最大5分)")
        print("-"*60)

        start_time = time.time()
        timeout = 300  # 5分

        while time.time() - start_time < timeout:
            transformation_status = get_transformation_status_via_api(
                auth_credentials=auth_credentials,
                project_id=PROJECT_ID,
                asset_id=asset_id,
                version_id=version_id,
                dataset_id=dataset_id,
                transformation_id=transformation_id
            )

            status = transformation_status.get("status")
            print(f"  現在のステータス: {status}")

            if status == "SUCCEEDED":
                print("  ✓ 変換が成功しました！")
                break
            elif status == "FAILED":
                error_msg = transformation_status.get("error", "不明なエラー")
                print(f"  ✗ 変換が失敗しました: {error_msg}")
                sys.exit(1)

            time.sleep(10)  # 10秒待機
        else:
            print("  ✗ 変換がタイムアウトしました（5分経過）")
            sys.exit(1)

        # === ステップ7: 変換後ファイルのダウンロード ===
        print("\n" + "-"*60)
        print("ステップ7: 変換後ファイルのダウンロード")
        print("-"*60)

        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        download_file_via_api(
            auth_credentials=auth_credentials,
            project_id=PROJECT_ID,
            asset_id=asset_id,
            version_id=version_id,
            dataset_name="Optimize and convert",
            file_name=output_filename,
            output_path=output_path
        )

        # === 完了 ===
        print("\n" + "="*60)
        print("すべての処理が完了しました！")
        print("="*60)
        print(f"\n作成されたリソース:")
        print(f"  Asset ID: {asset_id}")
        print(f"  Version ID: {version_id}")
        print(f"  Dataset ID: {dataset_id}")
        print(f"  Transformation ID: {transformation_id}")
        print(f"\n出力ファイル:")
        print(f"  {output_path}")

    except Exception as e:
        print(f"\n\n✗ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
