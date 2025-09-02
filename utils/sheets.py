import os
import time
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import WorksheetNotFound, APIError
from config import SHEET_KEY, GOOGLE_SHEET_TITLE


# --------------------------------------------------
# ✅ Google Sheets 클라이언트 생성
# --------------------------------------------------
def get_gspread_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")  # Render 환경
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:  # 로컬 개발용
        creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)

    return gspread.authorize(creds)


# --------------------------------------------------
# ✅ 시트 연결 (전역)
# --------------------------------------------------
client = get_gspread_client()
SHEET_KEY = os.getenv("GOOGLE_SHEET_KEY")
if not SHEET_KEY:
    raise EnvironmentError("환경변수 GOOGLE_SHEET_KEY가 설정되지 않았습니다.")

spreadsheet = client.open_by_key(SHEET_KEY)
print(f"시트에 연결되었습니다. (ID={SHEET_KEY})")


# --------------------------------------------------
# ✅ 워크시트 핸들 가져오기
# --------------------------------------------------
def get_worksheet(sheet_name: str):
    try:
        return spreadsheet.worksheet(sheet_name)
    except WorksheetNotFound:
        raise FileNotFoundError(f"워크시트를 찾을 수 없습니다: {sheet_name}")


# ✅ 별칭 (호환성)
get_ws = get_worksheet


# --------------------------------------------------
# ✅ 공통 I/O 유틸
# --------------------------------------------------
def append_row(sheet_name: str, row: list):
    ws = get_worksheet(sheet_name)
    ws.append_row(row, value_input_option="USER_ENTERED")


def update_cell(sheet_name: str, row: int, col: int, value, clear_first=True):
    ws = get_worksheet(sheet_name)
    if clear_first:
        ws.update_cell(row, col, "")
    ws.update_cell(row, col, value)


def delete_row(sheet_name: str, row: int):
    ws = get_worksheet(sheet_name)
    ws.delete_rows(row)


def safe_update_cell(sheet, row, col, value, clear_first=True, max_retries=3, delay=2):
    """Google Sheets 셀 안전 업데이트 (재시도 포함)"""
    for attempt in range(1, max_retries + 1):
        try:
            if clear_first:
                sheet.update_cell(row, col, "")
            sheet.update_cell(row, col, value)
            return True
        except APIError as e:
            if "429" in str(e):
                print(f"[⏳ 재시도 {attempt}] 429 오류 → {delay}초 대기")
                time.sleep(delay)
                delay *= 2
            else:
                raise
    print("[❌ 실패] 최대 재시도 초과")
    return False


def get_all(ws):
    """워크시트 모든 데이터를 dict 리스트로 반환"""
    return ws.get_all_records()


def header_maps(sheet):
    """시트 헤더 매핑 (컬럼명 → 인덱스)"""
    headers = [h.strip() for h in sheet.row_values(1)]
    idx = {h: i + 1 for i, h in enumerate(headers)}
    idx_l = {h.lower(): i + 1 for i, h in enumerate(headers)}
    return headers, idx, idx_l


# --------------------------------------------------
# 📌 전용 워크시트 핸들러
# --------------------------------------------------
# 회원
def get_db_sheet():
    return get_worksheet("DB")

def get_member_sheet():
    return get_worksheet("DB")


# 주문
def get_product_order_sheet():
    return get_worksheet("제품주문")

# alias (호환성 유지)
get_order_sheet = get_product_order_sheet
get_add_order_sheet = get_product_order_sheet
get_save_order_sheet = get_product_order_sheet
get_delete_order_request_sheet = get_product_order_sheet
get_delete_order_confirm_sheet = get_product_order_sheet


# 일지
def get_counseling_sheet():
    return get_worksheet("상담일지")

def get_personal_memo_sheet():
    return get_worksheet("개인일지")  # 예전 "개인메모"

def get_activity_log_sheet():
    return get_worksheet("활동일지")


# 후원수당
def get_commission_sheet():
    return get_worksheet("후원수당")


# 기타
def get_image_sheet():
    return get_worksheet("사진저장")

def get_backup_sheet():
    return get_worksheet("백업")


# --------------------------------------------------
# 📌 헬퍼 함수
# --------------------------------------------------
def get_member_info(member_name: str):
    """DB 시트에서 회원명으로 회원번호/휴대폰번호 조회"""
    ws = get_member_sheet()
    records = ws.get_all_records()
    for row in records:
        if (row.get("회원명") or "").strip() == member_name.strip():
            return row.get("회원번호", ""), row.get("휴대폰번호", "")
    return "", ""


def get_sheet():
    """스프레드시트 핸들 반환 (전역 spreadsheet 객체)"""
    return spreadsheet
