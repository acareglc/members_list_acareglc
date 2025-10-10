# =================================================
# 이미지 업로드 & 검색 라우트 (members_list_main / 이미지메모)
# =================================================
import os
import json
import traceback
from datetime import datetime
from flask import request, jsonify
from werkzeug.utils import secure_filename
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build
from google.oauth2 import service_account

# -------------------------------------------------
# ✅ utils.sheets 불러오기
# -------------------------------------------------
from utils.sheets import (
    get_worksheet,
    append_row,
)

# -------------------------------------------------
# ✅ Google Drive 인증 설정
# -------------------------------------------------
def get_drive_service():
    """환경변수 GOOGLE_SERVICE_ACCOUNT_JSON 기반으로 Drive API 인증"""
    creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not creds_json:
        raise EnvironmentError("❌ GOOGLE_SERVICE_ACCOUNT_JSON 환경변수가 설정되지 않았습니다.")

    # credentials.json 파일 경로 또는 JSON 문자열 둘 다 허용
    if os.path.exists(creds_json):
        creds = service_account.Credentials.from_service_account_file(
            creds_json,
            scopes=[
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets"
            ]
        )
    else:
        creds_dict = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets"
            ]
        )
    return build("drive", "v3", credentials=creds)


# -------------------------------------------------
# ✅ 초기 설정
# -------------------------------------------------
drive_service = get_drive_service()
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")   # ✅ 기본값 제거 (환경변수만 사용)
UPLOAD_FOLDER = "./uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# -------------------------------------------------
# ✅ 시트에 이미지 정보 추가
# -------------------------------------------------
def append_image_to_sheet(filename: str, file_link: str, description: str):
    """
    Google Sheets '이미지메모' 시트에 이미지 정보 저장
    members_list_main 문서 내 구조: [날짜, 파일명, 링크, 이미지메모]
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        ws = get_worksheet("이미지메모")
        ws.append_row([now, filename, file_link, description], value_input_option="USER_ENTERED")
        print(f"[INFO] ✅ 이미지메모 시트 기록 완료: {filename}")
    except Exception as e:
        print(f"[ERROR] append_image_to_sheet 실패: {e}")


# -------------------------------------------------
# ✅ 이미지 업로드 (설명 수동 입력)
# -------------------------------------------------
def upload_image_func():
    """
    이미지 업로드 + 수동 설명 기록
    - form-data:
        - file: 이미지 파일
        - description: 설명 텍스트
    """
    try:
        if "file" not in request.files:
            return jsonify({"error": "❌ 이미지 파일이 없습니다."}), 400

        file = request.files["file"]
        description = request.form.get("description", "").strip()
        filename = secure_filename(file.filename)
        local_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(local_path)

        # ✅ Google Drive 업로드
        file_metadata = {"name": filename, "parents": [DRIVE_FOLDER_ID]}
        media = MediaFileUpload(local_path, mimetype=file.mimetype)
        uploaded = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink"
        ).execute()

        file_link = uploaded.get("webViewLink")

        # ✅ Google Sheets에 기록
        append_image_to_sheet(filename, file_link, description)

        # ✅ 임시 파일 삭제
        os.remove(local_path)

        return jsonify({
            "message": "✅ 이미지 업로드 및 '이미지메모' 시트 기록 완료",
            "file_link": file_link,
            "description": description
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -------------------------------------------------
# ✅ 이미지 검색 (설명 텍스트 기반)
# -------------------------------------------------
def search_image_func():
    """
    설명(이미지메모)에 포함된 키워드로 검색
    예: /search_image?keyword=다이어트
    """
    keyword = request.args.get("keyword", "").strip()
    if not keyword:
        return jsonify({"error": "검색어(keyword)를 입력하세요."}), 400

    try:
        ws = get_worksheet("이미지메모")
        records = ws.get_all_records()
        results = [
            r for r in records
            if keyword.lower() in str(r.get("이미지메모", "")).lower()
        ]

        return jsonify({
            "count": len(results),
            "results": results
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
