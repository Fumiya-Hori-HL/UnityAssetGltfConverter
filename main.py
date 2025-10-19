import os
import time
import sys
import base64
import json
from dotenv import load_dotenv
from pathlib import PurePath, PurePosixPath
import unity_cloud
from unity_cloud.assets import AssetCreation, AssetType, FileUploadInformation
import requests

# .envファイルから環境変数を読み込む
load_dotenv()

# --- 設定項目 ---
# .envファイルから設定を読み込む (新しい変数名に対応)
ORG_ID = os.getenv("UNITY_CLOUD_ORGANIZATION_ID")
PROJECT_ID = os.getenv("UNITY_CLOUD_PROJECT_ID")
KEY_ID = os.getenv("UNITY_CLOUD_KEY_ID")
SECRET_KEY = os.getenv("UNITY_CLOUD_SECRET_KEY")

# 変換対象のファイルパス
INPUT_FILE_PATH = "assets_input/your_model.obj"
OUTPUT_FOLDER = "assets_output"

# Unity Services API Base URL
UNITY_SERVICES_API_BASE = "https://services.api.unity.com"


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
    # Base64エンコード: key_id:secret_key
    credentials = f"{key_id}:{secret_key}"
    encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

    # Token Exchange APIを呼び出し
    url = f"{UNITY_SERVICES_API_BASE}/auth/v1/token-exchange"
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
        return token_data.get("token")
    except requests.exceptions.RequestException as e:
        print(f"アクセストークンの取得に失敗しました: {e}")
        if hasattr(e.response, 'text'):
            print(f"エラー詳細: {e.response.text}")
        raise


def start_transformation_via_api(access_token, org_id, project_id, asset_id, version_id, dataset_id, workflow_type, parameters):
    """
    Web APIで変換処理を開始する

    Parameters
    ----------
    access_token : str
        アクセストークン
    org_id : str
        組織ID
    project_id : str
        プロジェクトID
    asset_id : str
        アセットID
    version_id : str
        バージョンID
    dataset_id : str
        データセットID
    workflow_type : str
        ワークフロータイプ
    parameters : dict
        変換パラメータ

    Returns
    -------
    dict
        変換情報（transformation IDを含む）
    """
    url = f"{UNITY_SERVICES_API_BASE}/assets/v1/orgs/{org_id}/projects/{project_id}/assets/{asset_id}/versions/{version_id}/datasets/{dataset_id}/transformations"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    body = {
        "workflowType": workflow_type,
        "parameters": parameters
    }

    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()

        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"変換処理の開始に失敗しました: {e}")
        if hasattr(e.response, 'text'):
            print(f"エラー詳細: {e.response.text}")
        raise


def get_transformation_status_via_api(access_token, org_id, project_id, asset_id, version_id, dataset_id, transformation_id):
    """
    Web APIで変換ステータスを確認する

    Parameters
    ----------
    access_token : str
        アクセストークン
    org_id : str
        組織ID
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
    url = f"{UNITY_SERVICES_API_BASE}/assets/v1/orgs/{org_id}/projects/{project_id}/assets/{asset_id}/versions/{version_id}/datasets/{dataset_id}/transformations/{transformation_id}"

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"変換ステータスの取得に失敗しました: {e}")
        if hasattr(e.response, 'text'):
            print(f"エラー詳細: {e.response.text}")
        raise


def main():
    """
    OBJファイルのアップロード、GLTFへの変換、ダウンロードまでの一連の処理を実行する。
    """
    # --- 0. 事前チェック ---
    required_configs = [ORG_ID, PROJECT_ID, KEY_ID, SECRET_KEY]
    if not all(required_configs):
        print("エラー:.envファイルに必要な設定が不足しています。")
        print("UNITY_CLOUD_ORGANIZATION_ID, UNITY_CLOUD_PROJECT_ID, UNITY_CLOUD_KEY_ID, UNITY_CLOUD_SECRET_KEY の4つ全てが設定されているか確認してください。")
        sys.exit(1)

    if not os.path.exists(INPUT_FILE_PATH):
        print(f"エラー: 入力ファイルが見つかりません: {INPUT_FILE_PATH}")
        sys.exit(1)

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # --- 1. SDKの初期化 ---
    print("Unity Cloud SDKを初期化しています...")
    try:
        # Unity Cloud SDKの初期化（引数なし）
        unity_cloud.initialize()

        # サービスアカウントで認証
        unity_cloud.identity.service_account.use(
            key_id=KEY_ID,
            key=SECRET_KEY
        )
        print("SDKの初期化と認証が完了しました。")
    except Exception as e:
        print(f"SDKの初期化中にエラーが発生しました: {e}")
        unity_cloud.uninitialize()  # 失敗した場合はクリーンアップ
        sys.exit(1)

    try:
        # --- 2. ファイルのアップロード ---
        print(
            f"\n--- ステップ2: '{os.path.basename(INPUT_FILE_PATH)}' をアップロードしています ---")

        print("アセットを作成中...")
        asset_creation = AssetCreation(
            name=f"Automated Upload - {os.path.basename(INPUT_FILE_PATH)}",
            description="OBJファイルからの自動変換",
            type=AssetType.MODEL_3D
        )
        asset = unity_cloud.assets.create_asset(
            asset_creation=asset_creation,
            org_id=ORG_ID,
            project_id=PROJECT_ID
        )
        print(f"アセットを作成しました。Asset ID: {asset.id}")

        print("データセットを作成中...")
        dataset_id = unity_cloud.assets.create_dataset(
            org_id=ORG_ID,
            project_id=PROJECT_ID,
            asset_id=asset.id,
            asset_version=asset.version,
            dataset_name="source_obj"
        )
        print(f"データセットを作成しました。Dataset ID: {dataset_id}")

        print("ファイルをアップロード中...")
        upload_info = FileUploadInformation(
            organization_id=ORG_ID,
            project_id=PROJECT_ID,
            asset_id=asset.id,
            asset_version=asset.version,
            dataset_id=dataset_id,
            upload_file_path=PurePath(INPUT_FILE_PATH),
            cloud_file_path=PurePosixPath(os.path.basename(INPUT_FILE_PATH))
        )
        unity_cloud.assets.upload_file(asset_upload_information=upload_info)
        print(f"ファイルのアップロードが完了しました。")

        # --- 3. 変換処理の開始（Web API使用）---
        print("\n--- ステップ3: GLTFへの変換処理を開始します ---")

        # Web API用のアクセストークンを取得
        print("アクセストークンを取得中...")
        access_token = get_access_token(KEY_ID, SECRET_KEY, PROJECT_ID)
        print("アクセストークンを取得しました。")

        output_filename = f"{os.path.splitext(os.path.basename(INPUT_FILE_PATH))[0]}.gltf"

        # 変換パラメータ
        transformation_params = {
            "outputs": [
                {
                    "outputName": output_filename,
                    "outputFormat": "gltf"
                }
            ]
        }

        # Web APIで変換処理を開始
        transformation_response = start_transformation_via_api(
            access_token=access_token,
            org_id=ORG_ID,
            project_id=PROJECT_ID,
            asset_id=asset.id,
            version_id=asset.version,
            dataset_id=dataset_id,
            workflow_type="OptimizeAndConvert",
            parameters=transformation_params
        )
        transformation_id = transformation_response.get("id")
        print(f"変換を開始しました。Transformation ID: {transformation_id}")

        # --- 4. 変換ステータスのポーリング（Web API使用）---
        print("\n--- ステップ4: 変換処理の完了を待っています (最大5分)... ---")
        start_time = time.time()
        while time.time() - start_time < 300:  # 5分間のタイムアウト
            # Web APIで変換ステータスを取得
            transformation_status_response = get_transformation_status_via_api(
                access_token=access_token,
                org_id=ORG_ID,
                project_id=PROJECT_ID,
                asset_id=asset.id,
                version_id=asset.version,
                dataset_id=dataset_id,
                transformation_id=transformation_id
            )
            status = transformation_status_response.get("status")
            print(f"現在のステータス: {status}")
            if status == "SUCCEEDED":
                print("変換に成功しました！")
                break
            elif status == "FAILED":
                print("エラー: 変換に失敗しました。")
                sys.exit(1)
            time.sleep(10)  # 10秒待機
        else:
            print("エラー: 変換がタイムアウトしました。")
            sys.exit(1)

        # --- 5. 変換後ファイルのダウンロード ---
        print("\n--- ステップ5: 変換されたGLTFファイルをダウンロードします ---")

        print("変換後のデータセットを検索中...")
        asset_details = unity_cloud.assets.get_asset(
            org_id=ORG_ID,
            project_id=PROJECT_ID,
            asset_id=asset.id
        )
        optimized_dataset = next(
            (ds for ds in asset_details.datasets if ds.name == "Optimize and convert"), None)

        if not optimized_dataset:
            print("エラー: 'Optimize and convert' データセットが見つかりませんでした。")
            sys.exit(1)
        print(f"データセットを発見しました。Dataset ID: {optimized_dataset.id}")

        target_file = next(
            (f for f in optimized_dataset.files if f.name == output_filename), None)
        if not target_file:
            print(f"エラー: データセット内で '{output_filename}' が見つかりませんでした。")
            sys.exit(1)

        print(f"ダウンロード対象ファイルを発見: {target_file.name}")

        download_url = target_file.get_download_url()
        print("ダウンロードURLを取得しました。ダウンロードを開始します...")

        response = requests.get(download_url)
        response.raise_for_status()

        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        with open(output_path, "wb") as f:
            f.write(response.content)

        print(f"\nダウンロードが完了しました！ ファイルは '{output_path}' に保存されました。")

    except Exception as e:
        print(f"\n処理中に予期せぬエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # --- 6. クリーンアップ ---
        print("SDKを終了処理しています...")
        unity_cloud.uninitialize()
        print("処理を終了します。")


if __name__ == "__main__":
    main()
