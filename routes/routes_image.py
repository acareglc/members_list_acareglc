# =================================================
# 이미지 업로드 & 검색 라우트 (OAuth 개인계정용 + 시트 기록 유지)
# =================================================
import os
import json
import pickle
import traceback
from datetime import datetime
from flask import request, jsonify
from werkzeug.utils import secure_filename

# -------------------------------------------------
# ✅ Google API 관련 모듈
# -------------------------------------------------
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# -------------------------------------------------
# ✅ utils.sheets 불러오기 (시트 기록용, 기존 유지)
# -------------------------------------------------
from utils.sheets import get_worksheet  # (유지 OK, append_image_to_sheet는 이 파일 내부 함수 사용)
import time

# -------------------------------------------------
# ✅ 초기 설정
# -------------------------------------------------
UPLOAD_FOLDER = "./uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
SCOPES = ["https://www.googleapis.com/auth/drive.file"]  # 개인 Drive 업로드 전용 권한

# -------------------------------------------------
# ✅ Drive 서비스 (OAuth 사용자 로그인)
# -------------------------------------------------
def get_drive_service_user():
    """
    boraminfo@gmail.com 계정으로 OAuth 로그인하여 Google Drive 업로드용 서비스 생성
    - 최초 실행 시 브라우저 창이 열리며 로그인 필요
    - 이후 token_user.pkl 에 토큰 저장 → 자동 로그인
    """
    creds = None
    token_path = "token_user.pkl"

    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            creds = pickle.load(token)

    # 토큰 없거나 만료된 경우 새 로그인
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials_user.json"):
                raise FileNotFoundError("❌ credentials_user.json 파일이 없습니다.")
            flow = InstalledAppFlow.from_client_secrets_file("credentials_user.json", SCOPES)

            creds = flow.run_local_server(port=61617, prompt="consent")

        with open(token_path, "wb") as token:
            pickle.dump(creds, token)

    return build("drive", "v3", credentials=creds)


# -------------------------------------------------
# ✅ 시트에 이미지 정보 추가
# -------------------------------------------------
def append_image_to_sheet(member_name: str, file_link: str, description: str):
    """
    Google Sheets '이미지메모' 시트의 2행에 이미지 정보 추가
    구조: [날짜, 회원명, 링크, 내용]
    """
    now = datetime.now().strftime("%Y-%m-%d")  # ✅ 날짜만 기록 (시간 제외)
    try:
        ws = get_worksheet("이미지메모")
        # ✅ 제목행(1행) 아래 2행에 삽입
        ws.insert_row([now, member_name, file_link, description], index=2, value_input_option="USER_ENTERED")
        print(f"[INFO] ✅ 이미지메모 시트 2행 기록 완료: {member_name}")
    except Exception as e:
        print(f"[ERROR] append_image_to_sheet 실패: {e}")



# -------------------------------------------------
# ✅ 이미지 업로드 (설명 수동 입력)
# -------------------------------------------------
def upload_image_func():
    """
    이미지 업로드 + 설명 기록
    - form-data:
        - image: 이미지 파일
        - member_name: 회원명
        - description: 설명 텍스트
    """
    try:
        if "image" not in request.files:
            return jsonify({"error": "❌ 'image' 필드에 파일이 없습니다."}), 400

        file = request.files["image"]
        description = request.form.get("description", "").strip()
        member_name = request.form.get("member_name", "").strip() or "미입력"   # ✅ 회원명 입력값
        filename = secure_filename(file.filename)
        local_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(local_path)

        # ✅ 개인 OAuth 계정으로 Drive 연결
        drive_service_user = get_drive_service_user()

        DRIVE_FOLDER_ID = "1v-tTh8oHJVqOBBEAxNv1Q3XulEhxxFwL"  # 👈 본인 폴더 ID 지정
        file_metadata = {"name": filename, "parents": [DRIVE_FOLDER_ID]}
        media = MediaFileUpload(local_path, mimetype=file.mimetype)

        print("🚀 [DEBUG] Google Drive 업로드 시작:", filename)
        uploaded = drive_service_user.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink"
        ).execute()

        file_link = uploaded.get("webViewLink")
        print(f"✅ [DEBUG] 업로드 완료: {file_link}")

        # ✅ Google Sheets에 기록 (회원명 사용)
        append_image_to_sheet(member_name, file_link, description)

        # ✅ 임시 파일 삭제 (Windows 잠금 방지)
        try:
            time.sleep(0.5)  # 파일 핸들 해제 대기 (0.3~0.5초면 충분)

            # 🔒 파일 잠금 프로세스 해제 (Windows 전용)
            import psutil
            for proc in psutil.process_iter():
                try:
                    for item in proc.open_files():
                        if local_path == item.path:
                            proc.kill()
                            print(f"[FIX] 잠금 프로세스 종료: {proc.pid}")
                except Exception:
                    pass


            os.remove(local_path)
            print(f"[CLEANUP] 임시 파일 삭제 완료: {local_path}")




        except PermissionError:
            print(f"[WARN] 파일 잠금 중이어서 삭제 생략: {local_path}")
        except Exception as e:
            print(f"[ERROR] 파일 삭제 실패: {e}")

        return jsonify({
            "message": "✅ 이미지 업로드 및 '이미지메모' 시트 기록 완료",
            "member_name": member_name,
            "file_link": file_link,
            "description": description
        }), 200

    except Exception as e:
        print("🚨 [DEBUG] 업로드 중 예외 발생:\n", traceback.format_exc())
        return jsonify({"error": str(e)}), 500



# -------------------------------------------------
# ✅ 이미지 검색 (설명 텍스트 기반)
# -------------------------------------------------
# -------------------------------------------------
# ✅ 이미지 검색 (회원명/설명 텍스트 기반)
# -------------------------------------------------
def search_image_func():
    """
    Google Sheets '이미지메모' 시트에서 검색어(keyword)에 해당하는 이미지 검색
    예: /search_image?keyword=홍길동
    반환: 일치하는 행들의 JSON 배열
    """
    keyword = request.args.get("keyword", "").strip()
    if not keyword:
        return jsonify({"error": "검색어(keyword)를 입력하세요."}), 400

    try:
        ws = get_worksheet("이미지메모")
        records = ws.get_all_records()

        # ✅ 검색 로직 (회원명 or 이미지메모 설명 내 포함 여부)
        results = [
            r for r in records
            if keyword.lower() in str(r.get("회원명", "")).lower()
            or keyword.lower() in str(r.get("이미지메모", "")).lower()
            or keyword.lower() in str(r.get("설명", "")).lower()
        ]

        # ✅ 최신순 정렬 (최근에 추가된 게 위로)
        results = results[::-1]

        # ✅ 결과 구성
        formatted_results = [
            {
                "날짜": r.get("날짜", ""),
                "회원명": r.get("회원명", ""),
                "이미지링크": r.get("링크", ""),
                "설명": r.get("이미지메모", "") or r.get("설명", "")
            }
            for r in results
        ]

        return jsonify({
            "count": len(formatted_results),
            "keyword": keyword,
            "results": formatted_results
        }), 200

    except Exception as e:
        print("🚨 [DEBUG] 검색 중 예외 발생:\n", traceback.format_exc())
        return jsonify({"error": str(e)}), 500


