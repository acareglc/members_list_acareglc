# =====================================================
# 표준 라이브러리
# =====================================================
import os
import io
import re
import time
import json
import base64
from typing import Any, Dict, List, Optional

# =====================================================
# 외부 라이브러리
# =====================================================
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import WorksheetNotFound, APIError

# =====================================================
# 환경변수 기반 설정
# =====================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL")  # e.g. https://api.openai.com/v1/chat/completions
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o")



# ======================================================================================
# ✅ Google Sheets 유틸
# ======================================================================================

def get_gspread_client():
    """환경변수 기반 Google Sheets 클라이언트 생성"""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if creds_json:  # Render 환경
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:  # 로컬 개발용
        creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    return gspread.authorize(creds)


def get_spreadsheet():
    client = get_gspread_client()
    sheet_key = os.getenv("GOOGLE_SHEET_KEY")
    sheet_title = os.getenv("GOOGLE_SHEET_TITLE")

    if sheet_key:
        return client.open_by_key(sheet_key)
    elif sheet_title:
        return client.open(sheet_title)
    else:
        raise EnvironmentError("❌ GOOGLE_SHEET_KEY 또는 GOOGLE_SHEET_TITLE 필요")


# --------------------------------------------------
# ✅ 워크시트 핸들 가져오기
# --------------------------------------------------
import unicodedata
from gspread.exceptions import WorksheetNotFound

def normalize_name(name: str) -> str:
    """시트명 비교용 정규화 (유니코드 NFC + 공백제거 + 소문자화)"""
    if not name:
        return ""
    return unicodedata.normalize("NFC", name).strip().lower()


# -----------------------------
# 문자열 정규화
# -----------------------------
def normalize_text(s) -> str:
    """문자열을 NFC 정규화 + strip 처리"""
    if s is None:
        return ""
    return unicodedata.normalize("NFC", str(s)).strip()

# -----------------------------
# 워크시트 안전 조회
# -----------------------------
def get_worksheet(sheet_name):
    """
    지정된 이름의 워크시트를 가져옴.
    - sheet_name 이 Worksheet 객체면 .title 사용
    - 대소문자, 공백, 유니코드 차이 무시
    """
    sheet = get_spreadsheet()   # ✅ 기존 연결 함수 사용

    # Worksheet 객체가 넘어오면 title 추출
    if hasattr(sheet_name, "title") and not isinstance(sheet_name, str):
        sheet_name = sheet_name.title  # Worksheet.title → 문자열
    elif isinstance(sheet_name, str):
        sheet_name = sheet_name.strip()

    target = normalize_text(sheet_name).lower()

    for ws in sheet.worksheets():
        if normalize_text(ws.title).lower() == target:
            return ws

    raise FileNotFoundError(f"❌ 워크시트를 찾을 수 없습니다: {sheet_name}")






# --------------------------------------------------
# ✅ 시트에서 모든 행 불러오기
# --------------------------------------------------
def get_rows_from_sheet(sheet_name: str):
    try:
        client = get_gspread_client()

        # 환경변수에서 Sheet key/title 불러오기
        sheet_key = os.getenv("GOOGLE_SHEET_KEY")
        sheet_title = os.getenv("GOOGLE_SHEET_TITLE")

        if sheet_key:
            sheet = client.open_by_key(sheet_key).worksheet(sheet_name)
        elif sheet_title:
            sheet = client.open(sheet_title).worksheet(sheet_name)
        else:
            raise ValueError("❌ GOOGLE_SHEET_KEY 또는 GOOGLE_SHEET_TITLE 환경변수가 필요합니다.")

        # ✅ dict 리스트 반환
        return sheet.get_all_records()

    except WorksheetNotFound:
        raise ValueError(f"❌ 시트 '{sheet_name}'을(를) 찾을 수 없습니다.")
    except Exception as e:
        raise RuntimeError(f"❌ 시트 데이터 불러오기 실패: {e}")
    



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


def delete_row(sheet_or_name, row: int):
    """
    워크시트 이름(str) 또는 Worksheet 객체를 받아서 행 삭제
    """
    if isinstance(sheet_or_name, str):
        ws = get_worksheet(sheet_or_name)
    else:
        ws = sheet_or_name
    ws.delete_rows(row)



def safe_update_cell(sheet, row, col, value, clear_first=True, max_retries=3, delay=2):
    """Google Sheets 셀 안전 업데이트 (재시도 포함)"""
    for attempt in range(1, max_retries + 1):
        try:
            if clear_first:
                sheet.update_cell(row, col, "")

            print(f"[DEBUG] 시트 업데이트: row={row}, col={col}, value={value}")
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




def header_maps(sheet):
    """시트 헤더 매핑 (컬럼명 → 인덱스)"""
    headers = [h.strip() for h in sheet.row_values(1)]
    idx = {h: i + 1 for i, h in enumerate(headers)}
    idx_l = {h.lower(): i + 1 for i, h in enumerate(headers)}
    return headers, idx, idx_l



# --------------------------------------------------
# 📌 전용 워크시트 핸들러
# --------------------------------------------------

def get_db_sheet():
    return get_worksheet("DB")

def get_member_sheet():
    return get_worksheet("DB")

def get_product_order_sheet():
    return get_worksheet("제품주문")

def get_order_sheet():
    return get_worksheet("제품주문")

def get_counseling_sheet():
    return get_worksheet("상담일지")

def get_personal_memo_sheet():
    return get_worksheet("개인일지")  # 예전 "개인메모"

def get_activity_log_sheet():
    return get_worksheet("활동일지")

def get_commission_sheet():
    return get_worksheet("후원수당")

def get_image_sheet():
    return get_worksheet("사진저장")

def get_backup_sheet():
    return get_worksheet("백업")


def get_member_info(member_name: str):
    """DB 시트에서 회원명으로 회원번호/휴대폰번호 조회"""
    ws = get_member_sheet()
    records = ws.get_all_records()
    for row in records:
        if (row.get("회원명") or "").strip() == member_name.strip():
            return row.get("회원번호", ""), row.get("휴대폰번호", "")
    return "", ""




# --------------------------------------------------
# 📌 전용 워크시트 핸들러
# --------------------------------------------------
def get_gsheet_data(sheet_name: str = "DB"):
    """
    구글 시트 데이터 가져오기
    - sheet_name 기본값은 'DB'
    - 실제 gspread 서비스 계정 필요
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    client = gspread.authorize(creds)

    sheet = client.open("회원관리").worksheet(sheet_name)
    return sheet.get_all_records()







# --------------------------------------------------
# ✅ OpenAI 유틸
# --------------------------------------------------

def _ensure_orders_list(data: Any) -> List[Dict[str, Any]]:
    """응답을 무조건 orders 리스트 형태로 보정"""
    if isinstance(data, dict) and "orders" in data:
        return data["orders"] or []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return []


def openai_vision_extract_orders(image_bytes: io.BytesIO) -> List[Dict[str, Any]]:
    """
    이미지 → 주문 JSON 추출 (OpenAI Vision 모델)
    반환: [{'제품명':..., '제품가격':..., 'PV':..., '소비자_고객명':..., '소비자_휴대폰번호':..., '배송처':..., '결재방법': '', '수령확인': ''}, ...]
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY 미설정")
    if not OPENAI_API_URL:
        raise RuntimeError("OPENAI_API_URL 미설정")

    image_b64 = base64.b64encode(image_bytes.getvalue()).decode("utf-8")

    prompt = (
        "이미지를 분석하여 JSON 형식으로 추출하세요. "
        "여러 개의 제품이 있을 경우 'orders' 배열에 모두 담으세요. "
        "질문하지 말고 추출된 orders 전체를 그대로 저장할 준비를 하세요. "
        "(이름, 휴대폰번호, 주소)는 소비자 정보임. "
        "회원명, 결재방법, 수령확인, 주문일자 무시. "
        "필드: 제품명, 제품가격, PV, 소비자_고객명, 소비자_휴대폰번호, 배송처"
    )

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
            ]
        }],
        "temperature": 0
    }

    r = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=60)
    r.raise_for_status()

    resp = r.json()
    msg = resp["choices"][0]["message"]
    content = msg.get("content", "")

    # 문자열/리스트 모두 대응
    if isinstance(content, list):
        content_text = " ".join(
            c.get("text", "")
            for c in content
            if isinstance(c, dict) and c.get("type") == "text"
        ).strip()
    else:
        content_text = str(content).strip()

    # 코드펜스(json/일반) 제거
    clean = re.sub(r"```(?:json)?|```", "", content_text, flags=re.IGNORECASE).strip()

    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        # 모델이 순수 JSON이 아닌 텍스트를 반환한 경우, raw 텍스트로 보존
        data = {"raw_text": content_text}

    orders_list = _ensure_orders_list(data)

    # 정책: 결재방법/수령확인은 공란 유지 + 문자열 필드 trim
    for o in orders_list:
        o.setdefault("결재방법", "")
        o.setdefault("수령확인", "")
        for k, v in list(o.items()):
            if isinstance(v, str):
                o[k] = v.strip()

    return orders_list











# --------------------------------------------------
# ✅ 시트 연결 (전역)
# --------------------------------------------------
client = get_gspread_client()
SHEET_KEY = os.getenv("GOOGLE_SHEET_KEY")
if not SHEET_KEY:
    raise EnvironmentError("환경변수 GOOGLE_SHEET_KEY가 설정되지 않았습니다.")

spreadsheet = client.open_by_key(SHEET_KEY)
print(f"시트에 연결되었습니다. (ID={SHEET_KEY})")


# ✅ 별칭 (호환성)
get_ws = get_worksheet



def get_all(ws):
    """워크시트 모든 데이터를 dict 리스트로 반환"""
    return ws.get_all_records()



# 주문
def get_product_order_sheet():
    return get_worksheet("제품주문")

def get_order_sheet():
    return get_worksheet("제품주문")


# alias (호환성 유지)
get_order_sheet = get_product_order_sheet
get_add_order_sheet = get_product_order_sheet
get_save_order_sheet = get_product_order_sheet
get_delete_order_request_sheet = get_product_order_sheet
get_delete_order_confirm_sheet = get_product_order_sheet




def get_sheet():
    """스프레드시트 핸들 반환 (전역 spreadsheet 객체)"""
    return spreadsheet


# ======================================================================================
# http
# ======================================================================================

# ⬇️ 로컬에서만 .env 자동 로드
if os.getenv("RENDER") is None:
    try:
        from dotenv import load_dotenv
        if os.path.exists(".env"):
            load_dotenv(".env")
    except Exception:
        pass






