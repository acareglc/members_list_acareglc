from flask import Flask, request, jsonify, Response
import base64
import requests
import os
import io
import json
import re

from openai import OpenAI
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytz
import uuid
from gspread.utils import rowcol_to_a1
from collections import Counter

import time
from PIL import Image
import mimetypes
import traceback
from urllib.parse import urljoin



# 잘됨
# 동작




# ✅ 환경 변수 로드
if os.getenv("RENDER") is None:  # 로컬에서 실행 중일 때만
    from dotenv import load_dotenv
    dotenv_path = os.path.abspath('.env')
    if not os.path.exists(dotenv_path):
        raise FileNotFoundError(f".env 파일이 존재하지 않습니다: {dotenv_path}")
    load_dotenv(dotenv_path)

# 환경변수에서 불러오기
prompt_id = os.getenv("PROMPT_ID")
prompt_version = os.getenv("PROMPT_VERSION")

# ✅ OpenAI 클라이언트 초기화
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
GOOGLE_SHEET_TITLE = os.getenv("GOOGLE_SHEET_TITLE")

# OpenAI API 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL")

# ✅ memberslist API 엔드포인트
MEMBERSLIST_API_URL = os.getenv("MEMBERSLIST_API_URL")


# ✅ Google Sheets 클라이언트 생성 함수
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")  # Render에서 환경변수로 넣은 값
    if creds_json:  # Render 환경
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:  # 로컬 개발용 (credentials.json 파일 사용)
        creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)

    return gspread.authorize(creds)



# ✅ 시트 연결
client = get_gspread_client()
SHEET_KEY = os.getenv("GOOGLE_SHEET_KEY")
if not SHEET_KEY:
    raise EnvironmentError("환경변수 GOOGLE_SHEET_KEY가 설정되지 않았습니다.")
spreadsheet = client.open_by_key(SHEET_KEY)
print(f"시트에 연결되었습니다. (ID={SHEET_KEY})")


# ✅ 필수 환경 변수 확인
if not GOOGLE_SHEET_TITLE:
    raise EnvironmentError("환경변수 GOOGLE_SHEET_TITLE이 설정되지 않았습니다.")


# ✅ 날짜 처리
def process_order_date(text):
    if not text:
        return datetime.now().strftime("%Y-%m-%d")
    return text.strip()

# ✅ 한국 시간
def now_kst():
    return datetime.now(pytz.timezone("Asia/Seoul"))

# ✅ Flask 초기화
app = Flask(__name__)


# 전역에서 한 번만 open


def get_worksheet(sheet_name):
    try:
        return spreadsheet.worksheet(sheet_name)
    except Exception as e:
        raise RuntimeError(f"시트 '{sheet_name}'을 열 수 없습니다: {e}")

def some_function():
    print("작업 시작")
    time.sleep(1)
    print("작업 완료")


# ✅ 확인용 출력 (선택)
print("✅ GOOGLE_SHEET_TITLE:", os.getenv("GOOGLE_SHEET_TITLE"))
print("✅ GOOGLE_SHEET_KEY 존재 여부:", "Yes" if os.getenv("GOOGLE_SHEET_KEY") else "No")






# 자연어 명령 키워드 매핑
UPDATE_KEYS = {
    "회원": ["회원수정", "회원내용수정", "회원내용을 수정", "회원변경", "회원내용변경", "회원내용을 고쳐", "수정", "변경", "고쳐"],
    "주문": ["주문수정", "주문내용수정", "주문내용을 수정", "주문변경", "주문내용변경", "주문내용을 고쳐"],
    "후원수당": ["후원수당수정", "후원수당내용수정", "후원수당내용을 수정", "후원수당변경", "후원수당내용변경", "후원수당내용을 고쳐"]
}

# ✅ 주문 항목 헤더
ORDER_HEADERS = [
    "주문일자", "회원명", "회원번호", "휴대폰번호", "제품명",
    "제품가격", "PV", "결재방법", "주문자_고객명", "주문자_휴대폰번호",
    "배송처", "수령확인"
]




def parse_request(text):
    result = {"회원명": "", "수정목록": []}

    # 회원명 추출
    name_match = re.search(r"^([가-힣]{2,3})", text)
    if not name_match:
        name_match = re.search(r"([가-힣]{2,3})\s*회원[의은는이가]?", text)
    if name_match:
        result["회원명"] = name_match.group(1)

    # 전체 필드
    필드패턴 = r"(회원명|휴대폰번호|회원번호|특수번호|가입일자|생년월일|통신사|친밀도|근무처|계보도|소개한분|주소|메모|코드|카드사|카드주인|카드번호|유효기간|비번|카드생년월일|분류|회원단계|연령/성별|직업|가족관계|니즈|애용제품|콘텐츠|습관챌린지|비즈니스시스템|GLC프로젝트|리더님)"
    수정_패턴 = re.findall(rf"{필드패턴}\s*(?:은|는|을|를)?\s*([\w가-힣\d\-\.:/@]+)", text)

    for 필드, 값 in 수정_패턴:
        result["수정목록"].append({"필드": 필드, "값": 값})

    return result





@app.route("/")
def home():
    return "Flask 서버가 실행 중입니다."

def get_db_sheet():
    return get_worksheet("DB")

def get_member_sheet():
    return get_worksheet("DB")

def get_product_order_sheet():
    return get_worksheet("제품주문")

def get_add_order_sheet():
    return get_worksheet("제품주문")

def get_save_order_sheet():
    return get_worksheet("제품주문")

def get_delete_order_request_sheet():
    return get_worksheet("제품주문")

def get_delete_order_confirm_sheet():
    return get_worksheet("제품주문")

def get_ss_sheet():
    return get_worksheet("후원수당")

def get_counseling_sheet():
    return get_worksheet("상담일지")

def get_mymemo_sheet():
    return get_worksheet("개인일지")

def get_search_memo_by_tags_sheet():
    return get_worksheet("개인밀지")

def get_dailyrecord_sheet():
    return get_worksheet("활동일지")

def get_product_order_sheet():
    return get_worksheet("제품주문")    

def get_image_sheet():
    return get_worksheet("사진저장")

def get_backup_sheet():
    return get_worksheet("백업")






# ✅ 필드 키워드 → 시트의 실제 컬럼명 매핑
field_map = {
    "휴대폰번호": "휴대폰번호",
    "핸드폰": "휴대폰번호",
    "계보도": "계보도",
    "주소": "주소",
    "회원번호": "회원번호",
    "이름": "회원명",
    "생일": "생년월일",
    "생년월일": "생년월일",
    "특수번호": "특수번호",
    "직업": "근무처",
    "직장": "근무처",
    # 필요한 항목 계속 추가 가능
}



# 🔽 파일 하단에 삽입 예시
def save_member(name):
    print(f"[✅] '{name}' 회원 등록")

def update_member_fields(name, fields):
    print(f"[✏️] '{name}' 필드 업데이트: {fields}")







# ✅ 회원 조회
@app.route("/find_member", methods=["POST"])
def find_member():
    try:
        data = request.get_json()
        name = data.get("회원명", "").strip()
        number = data.get("회원번호", "").strip()

        if not name and not number:
            return jsonify({"error": "회원명 또는 회원번호를 입력해야 합니다."}), 400

        sheet = get_member_sheet()
        db = sheet.get_all_values()
        headers, rows = db[0], db[1:]

        matched = []
        for row in rows:
            row_dict = dict(zip(headers, row))
            if name and row_dict.get("회원명") == name:
                matched.append(row_dict)
            elif number and row_dict.get("회원번호") == number:
                matched.append(row_dict)

        if not matched:
            return jsonify({"error": "해당 회원 정보를 찾을 수 없습니다."}), 404

        if len(matched) == 1:
            return jsonify(matched[0]), 200

        result = []
        for idx, member in enumerate(matched, start=1):
            result.append({
                "번호": idx,
                "회원명": member.get("회원명"),
                "회원번호": member.get("회원번호"),
                "휴대폰번호": member.get("휴대폰번호")
            })
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500











def safe_update_cell(sheet, row, col, value, clear_first=True, max_retries=3, delay=2):
    """
    시트 셀을 안전하게 업데이트합니다.
    - clear_first=True: 기존 값을 먼저 삭제한 후 새 값 기록
    - max_retries: API 호출 재시도 횟수
    - delay: 재시도 대기 시간 (지수 증가)
    """
    for attempt in range(1, max_retries + 1):
        try:
            if clear_first:
                sheet.update_cell(row, col, "")  # ① 기존 값 비우기
            sheet.update_cell(row, col, value)  # ② 새 값 쓰기
            return True
        except gspread.exceptions.APIError as e:
            if "429" in str(e):
                print(f"[⏳ 재시도 {attempt}] 429 오류 → {delay}초 대기")
                time.sleep(delay)
                delay *= 2  # 재시도 시 대기 시간 2배 증가
            else:
                raise
    print("[❌ 실패] 최대 재시도 초과")
    return False









# 수정 루틴
# =======================================================================================

import re

def clean_value_expression(text: str) -> str:
    # 문장 끝에 붙은 조사나 표현만 제거
    particles = ['로', '으로', '은', '는', '을', '를', '값을','수정해 줘']
    for p in particles:
        # 끝에 붙은 조사 제거: "서울로", "회원번호는", "주소를" 등
        pattern = rf'({p})\s*$'
        text = re.sub(pattern, '', text)
    return text.strip()








# ======================================================================================

@app.route("/update_member", methods=["POST"])
@app.route("/updateMember", methods=["POST"])
def update_member():
    try:
        data = request.get_json(force=True)
        요청문 = data.get("요청문", "").strip()

        요청문 = clean_value_expression(요청문)  # ✅ 추가

        if not 요청문:
            return jsonify({"error": "요청문이 비어 있습니다."}), 400

        # ✅ 회원 전체 삭제 감지
        if "삭제" in 요청문:
            sheet = get_member_sheet()
            db = sheet.get_all_records()
            member_names = [str(row.get("회원명", "")).strip() for row in db if row.get("회원명")]

            name = None
            for candidate in sorted(member_names, key=lambda x: -len(x)):
                if candidate in 요청문:
                    name = candidate
                    break

            if not name:
                return jsonify({"error": "삭제할 회원명을 찾을 수 없습니다."}), 400

            # 👉 요청문에 필드명이 같이 들어 있으면 전체삭제가 아님
            field_keywords = {
                "주소", "휴대폰번호", "회원번호", "특수번호", "가입일자", "생년월일",
                "통신사", "친밀도", "근무처", "계보도", "소개한분", "메모", "코드"
            }

            if any(field in 요청문 for field in field_keywords):
                # 🔥 기존: 에러 반환 → 변경: updateMember 실행
              
                요청문 = re.sub(r"삭제$", "비움", 요청문.strip())  # 끝에 오는 '삭제'만 안전하게 치환
                return updateMember({"요청문": 요청문})

            # 👉 전체삭제는 '회원명 + 삭제' 두 단어일 때만 진행
            tokens = 요청문.replace(",", " ").split()
            if len(tokens) == 2 and tokens[0] == name and tokens[1] == "삭제":
                return delete_member_direct(name)

            return jsonify({
                "message": "회원 전체 삭제는 '회원명 삭제' 형식으로만 가능합니다."
            }), 400

        # ✅ 여기서부터 일반 updateMember 로직
        sheet = get_member_sheet()
        db = sheet.get_all_records()
        headers = [h.strip() for h in sheet.row_values(1)]

        member_names = [str(row.get("회원명", "")).strip() for row in db if row.get("회원명")]

        # ✅ 계보도 대상자 추출
        lineage_match = re.search(r"계보도[를은는]?\s*([가-힣]{2,})\s*(좌측|우측|라인|왼쪽|오른쪽)", 요청문)
        계보도_대상 = lineage_match.group(1) if lineage_match else None

        # 회원명 찾기
        name = None
        # ✅ 계보도 대상자는 제외하고 회원명 찾기
        for candidate in sorted(member_names, key=lambda x: -len(x)):
            if candidate and candidate != 계보도_대상 and candidate in 요청문:
                name = candidate
                break

        if not name:
            return jsonify({"error": "요청문에서 유효한 회원명을 찾을 수 없습니다."}), 400

        matching_rows = [i for i, row in enumerate(db) if row.get("회원명") == name]
        if not matching_rows:
            return jsonify({"error": f"'{name}' 회원을 찾을 수 없습니다."}), 404

        row_index = matching_rows[0] + 2
        member = db[matching_rows[0]]

        # ✅ 계보도 등 모든 필드는 parse_request_and_update 에서만 처리
        수정된필드 = {}
        updated_member, 수정된필드 = parse_request_and_update(요청문, member)
        print("[🧪 디버그] 수정된 필드:", 수정된필드)

        수정결과 = []
        # 수정된 필드만 순회
        for key, value in 수정된필드.items():
            if key.strip().lower() in headers:
                col = headers.index(key.strip().lower()) + 1
                print(f"[⬆️ 저장 시도] row={row_index}, col={col}, value={value}")
                success = safe_update_cell(sheet, row_index, col, value, clear_first=True)
                if success:
                    수정결과.append({"필드": key, "값": value})

        return jsonify({"status": "success", "회원명": name, "수정": 수정결과}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500








# ========================================================================================
# 예시 데이터베이스 (실제 환경에서는 DB 연동)
mock_db = {
    "홍길동": {
        "회원명": "홍길동",
        "회원번호": "12345678",
        "휴대폰번호": "010-1234-5678",
        "주소": "서울시 강남구"
    }
}

# 동의어 포함 field_map
field_map = {
    "회원명": "회원명", "이름": "회원명", "성함": "회원명",
    "회원번호": "회원번호", "번호": "회원번호", "아이디": "회원번호",
    "생년월일": "생년월일", "생일": "생년월일", "출생일": "생년월일",
    "성별": "연령/성별", "연령": "연령/성별", "나이": "연령/성별",
    "휴대폰번호": "휴대폰번호", "전화번호": "휴대폰번호", "연락처": "휴대폰번호", "폰": "휴대폰번호",
    "주소": "주소", "거주지": "주소", "사는곳": "주소",
    "직업": "직업", "일": "직업", "하는일": "직업",
    "가입일자": "가입일자", "입회일": "가입일자", "등록일": "가입일자",
    "가족관계": "가족관계", "가족": "가족관계",
    "추천인": "소개한분", "소개자": "소개한분",
    "계보도": "계보도",
    "후원인": "카드주인", "카드주인": "카드주인", "스폰서": "카드주인",
    "카드사": "카드사", "카드번호": "카드번호", "카드생년월일": "카드생년월일",
    "리더": "리더님", "리더님": "리더님", "멘토": "리더님",
    "비번": "비번",   
    "특수번호": "특수번호",
    "시스템코드": "코드", "코드": "코드", "시스템": "비즈니스시스템",
    "콘텐츠": "콘텐츠", "통신사": "통신사", "유효기간": "유효기간", "수신동의": "수신동의",
    "메모": "메모", "비고": "메모", "노트": "메모",
    "GLC": "GLC프로젝트", "프로젝트": "GLC프로젝트", "단계": "회원단계",
    "분류": "분류", "니즈": "니즈", "관심": "니즈",
    "애용제품": "애용제품", "제품": "애용제품", "주력제품": "애용제품",
    "친밀도": "친밀도", "관계": "친밀도",
    "근무처": "근무처", "회사": "근무처", "직장": "근무처"
}









# 다중 필드 업데이트 함수
def parse_request_and_update_multi(data: str, member: dict) -> dict:
    field_map = {
        "휴대폰번호": "휴대폰번호", "회원번호": "회원번호", "특수번호": "특수번호",
        "가입일자": "가입일자", "생년월일": "생년월일", "통신사": "통신사",
        "친밀도": "친밀도", "근무처": "근무처", "소개한분": "소개한분",
        "메모": "메모", "코드": "코드",
        "주소": "주소", "계보도": "계보도", "회원명": "회원명"
    }

    # 키워드 등장 위치 수집
    positions = []
    for keyword in field_map:
        for match in re.finditer(rf"{keyword}\s*(?:를|은|는|이|가|:|：)?", data):
            positions.append((match.start(), keyword))
    positions.sort()

    # 위치 기반 블록 추출 및 필드 저장
    for idx, (start, keyword) in enumerate(positions):
        end = positions[idx + 1][0] if idx + 1 < len(positions) else len(data)
        value_block = data[start:end]
        value_match = re.search(rf"{keyword}\s*(?:를|은|는|이|가|:|：)?\s*(.+)", value_block)
        if value_match:
            value = value_match.group(1).strip()

           

            # ✅ 불필요한 명령어 제거
            value = re.sub(r'(으로|로)?\s*(저장|변경|수정|입력|해)?해(줘|주세요)?\.?$', '', value).strip()



            # ✅ 숫자 필드 후처리
            if keyword == "휴대폰번호":
                # ✅ 조사 제거
                value = re.sub(r'(010[-\d]+)[으]?(?:로|으로|에|을|를|은|는|이|가|도|만|과|와|까지|부터)?(?:\s|[.,\n]|$)?', r'\1', value)

                # ✅ 숫자만 남기고 하이픈 포맷 적용
                digits = re.sub(r"\D", "", value)
                if len(digits) == 11 and digits.startswith("010"):
                    value = f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
                else:
                    value = digits





            elif keyword == "회원번호":
                # 조사 제거
                value = re.sub(r'(\d+)[으]?(?:로|으로|에|을|를|은|는|이|가|도|만|과|와|까지|부터)?(?:\s|[.,\n]|$)?', r'\1', value)
                print("조사 제거 후:", value)  # ← 여기에 추가

                # 숫자만 추출
                value = re.sub(r"\D", "", value)
                print("숫자 추출 후:", value)  # ← 여기에 추가







            field = field_map[keyword]
            
            
            member[field] = value
            member[f"{field}_기록"] = f"(기록됨: {value})"



    return member











# ✅ 꼬리 명령어 정제 함수 추가
def clean_tail_command(text):
    tail_phrases = [
        "로 정확히 수정해줘", "으로 정확히 수정해줘",
        "로 바꿔", "으로 바꿔", "로 변경", "으로 변경", 
        "로 수정", "으로 수정", 
        "정확히 수정해줘", "수정해줘", "변경해줘", 
        "바꿔줘", "변경해", "바꿔", "수정", "변경", 
        "저장해줘", "기록", "입력", "해줘", "남겨", "해주세요"
    ]







    for phrase in tail_phrases:
        # "로", "으로"가 꼬리 명령어 직전일 경우에만 함께 제거

        pattern = rf"(?:\s*(?:으로|로))?\s*{re.escape(phrase)}\s*[^\w가-힣]*$"


        text = re.sub(pattern, "", text)

    return text.strip()





def clean_affiliation(text):
    # 예외 처리: '이은혜', '이태수' 같은 고유명사는 보호
    exceptions = ['이은혜', '이태수']
    for name in exceptions:
        if name in text:
            return text.replace(name + "우측", name + " 우측")
    return text



def clean_name_field(value):
    # 고유명사 예외 목록 (필요 시 확장 가능)
    proper_nouns = ['이태수', '이은혜', '이판사', '임채영']
    
    # 정확히 일치하는 고유명사는 그대로 반환
    if value in proper_nouns:
        return value

    # 조사 제거 규칙 예시
    value = value.strip()
    if value.startswith("이") and len(value) > 2:
        # '이'를 조사로 간주하는 경우 잘못된 제거 방지
        return value
    return value




def extract_value(raw_text):
    # 명령어 후미 제거
    cleaned = raw_text.replace("로 정확히 수정해줘", "") \
                      .replace("정확히 수정해줘", "") \
                      .replace("수정해줘", "") \
                      .strip()
    return cleaned





def parse_field_value(field, raw_text):
    if field in ["주소", "메모"]:
        return raw_text.strip()
    else:
        return extract_value(raw_text)









def extract_phone(text):
    match = re.search(r'01[016789]-?\d{3,4}-?\d{4}', text)
    if match:
        number = match.group()
        number = re.sub(r'[^0-9]', '', number)
        return f"{number[:3]}-{number[3:7]}-{number[7:]}"
    return None







def extract_member_number(text):
    match = re.search(r'\b\d{7,8}\b', text)
    if match:
        return match.group()
    return None







def extract_password(text):
    # 특수번호 패턴: 영문/숫자/특수문자 포함, 6~20자
    match = re.search(r"특수번호(?:를|는)?\s*([^\s\"']{6,20})", text)
    if match:
        return match.group(1)
    return None















def extract_referrer(text):
    # "소개한분은 홍길동으로", "추천인은 박철수입니다" 등에서 이름 추출
    match = re.search(r"(소개한분|소개자|추천인)[은는을이]?\s*([가-힣]{2,10})", text)
    if match:
        이름 = match.group(2)
        
        # "로"로 끝나는 경우에만 삭제 ("로열", "로미오" 등은 유지)
        if 이름.endswith("로"):
            이름 = 이름[:-1]

        return 이름
    return None








def infer_field_from_value(value: str) -> str | None:
    value = value.strip()

    if re.match(r"010[-]?\d{3,4}[-]?\d{4}", value):
        return "휴대폰번호"
    elif re.fullmatch(r"\d{4,8}", value):
        return "회원번호"
    elif re.search(r"(좌측|우측|라인|왼쪽|오른쪽)", value):
        return "계보도"

    elif re.fullmatch(r"[a-zA-Z0-9@!#%^&*]{6,20}", value):
        return "특수번호"  # ✅ 특수번호 후보로 인식
    


    return None








# ✅ 회원 수정
# ✅ 자연어 요청문에서 필드와 값 추출, 회원 dict 수정


# ✅ 회원 수정 API
def parse_request_and_update(data: str, member: dict) -> tuple:
    수정된필드 = {}



    # ✅ 다중 필드 전체 순회용
    필드맵 = {
        "주소": "주소", "휴대폰번호": "휴대폰번호", "회원번호": "회원번호", "특수번호": "특수번호",
        "가입일자": "가입일자", "생년월일": "생년월일", "통신사": "통신사",
        "친밀도": "친밀도", "근무처": "근무처", "계보도": "계보도",
        "소개한분": "소개한분", "메모": "메모", "코드": "코드"
    }

    # ✅ 키워드 위치 수집
    positions = []
    for 키 in 필드맵:
        for match in re.finditer(rf"{키}\s*(?:를|은|는|이|가|:|：)?", data):
            positions.append((match.start(), 키))
    positions.sort()





    # ✅ 여기에 전처리 블록 추가
    if not positions:
        # 예: "홍길동 수정 휴대폰번호 010-2759-8000 회원번호 40005000"
        tokens = data.strip().split()
        for i in range(len(tokens) - 1):
            키워드 = tokens[i]
            값 = tokens[i + 1]



            if 키워드 in 필드맵:


                # ✅ 공백/삭제 키워드 처리
                if 값 in {"삭제", "지움", "비움", "공백", "없음", "없애기", "비워"}:
                    값 = ""

                필드 = 필드맵[키워드]

       
                member[필드] = 값
                member[f"{필드}_기록"] = f"(기록됨: {값})"
                수정된필드[필드] = 값









    # ✅ 각 필드 블록 파싱
    for idx, (start, 키) in enumerate(positions):
        끝 = positions[idx + 1][0] if idx + 1 < len(positions) else len(data)
        block = data[start:끝]
        match = re.search(rf"{키}(?:를|은|는|이|가|:|：)?\s*(.+)", block)


        if match:

            값 = match.group(1).strip()


            # ✅ 필드 삭제 키워드 즉시 처리
            field_delete_keywords = {"지움", "비움", "지우기", "없음", "없애기", "비워", "공백", "삭제"}
            if 값 in field_delete_keywords:
                필드 = 필드맵[키]
                수정된필드[필드] = ""
                member[필드] = ""
                member.pop(f"{필드}_기록", None)
                continue






            # ✅ 공통 꼬리 명령어 제거 대상 필드
            if 키 in {"주소", "메모", "휴대폰번호", "회원번호", "특수번호", "가입일자", "생년월일",
                    "통신사", "친밀도", "근무처", "계보도","소개한분", "코드"}:
                값 = clean_tail_command(값)

                값 = 값.strip().rstrip("'\"“”‘’.,)")



            # 세부 필드별 추가 정제
            elif 키 == "휴대폰번호":
                # ✅ 조사 제거
                값 = re.sub(r"(010[-]?\d{3,4}[-]?\d{4})(을|를|이|가|은|는|으로|로)?", r"\1", 값)
                값 = extract_phone(값)




            elif 키 == "회원번호":
                # ✅ 조사 제거
                값 = re.sub(r"([0-9]{6,8})(을|를|이|가|은|는|으로|로)", r"\1", 값)
                값 = extract_member_number(값) or 값




            elif 키 == "특수번호":
                # ✅ 조사 제거
                값 = re.sub(r"(\S+)(을|를|이|가|은|는|으로|로)?", r"\1", 값)
                값 = extract_password(값) or 값






            elif 키 == "가입일자":
                # ✅ 꼬리 명령어 제거
                값 = clean_tail_command(값)

                # ✅ 조사 제거 (예: '2023-05-01로' → '2023-05-01')
                값 = re.sub(r"(\d{4}-\d{2}-\d{2})(?:을|를|은|는|이|가|으로|로)?", r"\1", 값)

                # ✅ 날짜 형식 추출
                match = re.search(r"\d{4}-\d{2}-\d{2}", 값)
                값 = match.group() if match else ""






            elif 키 == "생년월일":
                if "지워" in block:
                    값 = ""
                else:
                    # ✅ 조사 제거 후 날짜 추출
                    값 = re.sub(r"(을|를|은|는|이|가|으로|로)?\s*(\d{4}-\d{2}-\d{2})", r"\2", 값)
                    match_date = re.search(r"\d{4}-\d{2}-\d{2}", 값)
                    값 = match_date.group() if match_date else ""




            elif 키 == "통신사":
                # ✅ 꼬리 명령어 제거
                값 = clean_tail_command(값)

                # ✅ 조사 제거 (예: 'KT로', 'SK는', 'LGU+를' → 'KT', 'SK', 'LGU+')
                값 = re.sub(r"([A-Za-z가-힣0-9\+\s]{2,10})(?:을|를|은|는|이|가|으로|로)?$", r"\1", 값)

                # ✅ 공백 정리
                값 = 값.strip()








            elif 키 == "친밀도":
                # ✅ 꼬리 명령어 제거
                값 = clean_tail_command(값)

                # ✅ 조사 제거: 상/중/하 뒤에 붙은 모든 조사 제거
                값 = re.sub(r"(상|중|하)(?:을|를|은|는|이|가|으로|로)?", r"\1", 값)

                # ✅ 최종 값 정제
                match = re.search(r"(상|중|하)", 값)
                값 = match.group(1) if match else ""







            elif 키 == "계보도":
                # ✅ 중간 조사 제거
                값 = re.sub(r"([가-힣]{2,4})(을|를|이|가|은|는)", r"\1", 값)

                # ✅ 이름과 방향 추출
                name_dir_match = re.search(r"([가-힣]{2,4})\s*(좌측|우측|라인|왼쪽|오른쪽)", 값)
                if name_dir_match:
                    이름 = name_dir_match.group(1)
                    방향 = name_dir_match.group(2)
                    값 = f"{이름}{방향}"
                else:
                    # 혹시 공백 없이 적힌 경우도 그대로 인정
                    값 = 값.replace(" ", "")






 


            elif 키 == "소개한분":
                # ✅ 꼬리 명령어 제거
                값 = clean_tail_command(값)

                # ✅ 조사 제거 (예: '홍길동으로', '박철수는', '김민수의' → '홍길동', '박철수', '김민수')
                값 = re.sub(r"([가-힣]{2,10})(?:을|를|은|는|이|가|의|으로|로)?$", r"\1", 값)

                # ✅ 추출 함수로 최종 보정 (예: '소개한분은 김민수입니다' → '김민수')
                값 = extract_referrer(block) or 값







            필드 = 필드맵[키]
            member[필드] = 값
            member[f"{필드}_기록"] = f"(기록됨: {값})"
            수정된필드[필드] = 값


 





    # ✅ 추론 블록은 따로 조건문으로 분리
    if not positions:
        # 키워드가 없을 경우 추론
        tokens = data.strip().split()
        
        # 기존 단일 추론 로직 (유지)
        if len(tokens) >= 2:
            name_candidate = tokens[0]
            value_candidate = ' '.join(tokens[1:]).replace("수정", "").strip()
            value_candidate = clean_tail_command(value_candidate)

            inferred_field = infer_field_from_value(value_candidate)
            if inferred_field:
                value = value_candidate
                if inferred_field == "회원번호":
                    value = re.sub(r"[^\d]", "", value)



            elif inferred_field == "휴대폰번호":
                digits = re.sub(r"\D", "", value)
                if len(digits) == 11 and digits.startswith("010"):
                    value = f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
                else:
                    value = digits






                수정된필드[inferred_field] = value
                member[inferred_field] = value
                member[f"{inferred_field}_기록"] = f"(기록됨: {value})"

        # ✅ 추가: 여러 값이 있을 경우 각각 형식 기반 추론
        for token in tokens:
            # 휴대폰번호 형태

            if re.match(r"010[-]?\d{3,4}[-]?\d{4}|010\d{8}", token):
                digits = re.sub(r"\D", "", token)
                if len(digits) == 11 and digits.startswith("010"):
                    phone = f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
                else:
                    phone = digits
                member["휴대폰번호"] = phone
                member["휴대폰번호_기록"] = f"(기록됨: {phone})"
                수정된필드["휴대폰번호"] = phone


            # 숫자 6~8자리: 회원번호 추정
            elif re.match(r"^\d{6,8}$", token):
                member_no = extract_member_number(token) or token
                member["회원번호"] = member_no
                member["회원번호_기록"] = f"(기록됨: {member_no})"
                수정된필드["회원번호"] = member_no




            # ✅ "삭제", "지움", "비움" 등은 모두 공란("")으로 변환
            delete_keywords = {"삭제", "지움", "비움", "지우기", "없음", "없애기", "비워"}
            for k, v in list(수정된필드.items()):
                if str(v).strip() in delete_keywords:
                    수정된필드[k] = ""
                    member[k] = ""
                    # ✅ 기록 자체도 아예 삭제
                    if f"{k}_기록" in member:
                        del member[f"{k}_기록"]




    return member, 수정된필드






















# ==========================================================================================================




# ✅ 명령어에서 회원명, 회원번호 추출
# ✅ 회원 등록 명령 파싱 함수
# ✅ 통합 파싱 함수 (개선된 정규식 + 안정성 보강)
def parse_registration(text):
    import re

    text = text.replace("\n", " ").replace("\r", " ").replace("\xa0", " ").strip()
    print(f"[🔍DEBUG] 전처리된 입력 text: '{text}'")

    name = number = phone = lineage = ""

    # ✅ 휴대폰번호 추출
    phone_match = re.search(r"010[-]?\d{4}[-]?\d{4}", text)
    if phone_match:
        phone = phone_match.group(0)
        print(f"[DEBUG] 📱 휴대폰번호 추출: {phone}")

    # ✅ 한글 단어 추출
    korean_words = re.findall(r"[가-힣]{2,}", text)
    print(f"[DEBUG] 🈶 한글 단어들: {korean_words}")

    # ✅ 이름 + 회원번호 추출
    match = re.search(r"(?:회원등록\s*)?([가-힣]{2,10})\s*회원번호\s*(\d+)", text)
    if match:
        name = match.group(1).strip()
        number = re.sub(r"[^\d]", "", match.group(2)).strip()
        print(f"[✅DEBUG] 회원번호 형식 매칭 → name: '{name}', number: '{number}'")
    else:
        match = re.search(r"([가-힣]{2,10})\s+(\d{6,})", text)
        if match and "회원등록" in text:
            name = match.group(1).strip()
            number = re.sub(r"[^\d]", "", match.group(2)).strip()
            print(f"[✅DEBUG] 번호 포함 등록 형식 → name: '{name}', number: '{number}'")
        else:
            match = re.search(r"^([가-힣]{2,10})\s*회원등록$", text)
            if match:
                name = match.group(1).strip()
                print(f"[✅DEBUG] 이름만 포함된 등록 형식 → name: '{name}'")

    # ✅ fallback
    if not name and korean_words:
        name = korean_words[0]
        print(f"[ℹ️DEBUG] fallback 적용 → name: {name}")
    if not number:
        print("[ℹ️DEBUG] 회원번호 없이 등록됨")
        number = ""

    # ❌ 계보도 추정 제거됨

    print(f"[RESULT] 이름={name}, 번호={number}, 휴대폰번호={phone}, 계보도={lineage}")
    return name or None, number or None, phone or None, lineage or None









# ✅ JSON 기반 회원 저장/수정 API
@app.route('/save_member', methods=['POST'])
def save_member():
    try:
        req = request.get_json()
        print(f"[DEBUG] 📥 요청 수신: {req}")

        요청문 = req.get("요청문") or req.get("회원명", "")
        if not 요청문:
            return jsonify({"error": "입력 문장이 없습니다"}), 400

        # ✅ 파싱
        name, number, phone, lineage = parse_registration(요청문)
        if not name:
            return jsonify({"error": "회원명을 추출할 수 없습니다"}), 400

        # ✅ 주소 기본값 처리 (iPad 등 환경에서 누락 방지)
        address = req.get("주소") or req.get("address", "")

        # ✅ 시트 접근
        sheet = get_member_sheet()
        headers = [h.strip() for h in sheet.row_values(1)]
        rows = sheet.get_all_records()

        print(f"[DEBUG] 시트 헤더: {headers}")

        # ✅ 기존 회원 여부 확인
        for i, row in enumerate(rows):
            if str(row.get("회원명", "")).strip() == name:
                print(f"[INFO] 기존 회원 '{name}' 발견 → 수정")
                for key, value in {
                    "회원명": name,
                    "회원번호": number,
                    "휴대폰번호": phone,
                    "계보도": lineage,
                    "주소": address
                }.items():
                    if key in headers and value:


                        row_idx = i + 2
                        col_idx = headers.index(key) + 1
                        safe_update_cell(sheet, row_idx, col_idx, value, clear_first=True)


                return jsonify({"message": f"{name} 기존 회원 정보 수정 완료"}), 200

        # ✅ 신규 등록
        print(f"[INFO] 신규 회원 '{name}' 등록")
        new_row = [''] * len(headers)
        for key, value in {
            "회원명": name,
            "회원번호": number,
            "휴대폰번호": phone,
            "계보도": lineage,
            "주소": address
        }.items():
            if key in headers and value:
                new_row[headers.index(key)] = value

        sheet.insert_row(new_row, 2)
        return jsonify({"message": f"{name} 회원 신규 등록 완료"}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


 



# ===============================================================================================================
    
# 📌 DB 시트에서 회원의 주소를 업데이트하는 함수
def update_member_address(member_name, address):
    sheet = get_worksheet("DB")  # Google Sheets의 DB 시트
    if not sheet:
        print("[오류] 'DB' 시트를 찾을 수 없습니다.")
        return False

    db = sheet.get_all_records()
    headers = [h.strip().lower() for h in sheet.row_values(1)]
    matches = [i for i, row in enumerate(db) if row.get("회원명") == member_name]

    if not matches:
        print(f"[오류] '{member_name}' 회원을 찾을 수 없습니다.")
        return False

    row_index = matches[0] + 2
    try:
        col_index = headers.index("주소") + 1
    except ValueError:
        print("[오류] '주소' 필드가 존재하지 않습니다.")
        return False

    safe_update_cell(sheet, row_index, col_index, address, clear_first=True)

    print(f"[주소 업데이트 완료] {member_name} → {address}")
    return True



@app.route("/save_memo", methods=["POST"])
def save_memo():
    data = request.json
    member_name = data.get("member_name", "")
    memo_text = data.get("memo", "")

    # 주소 키워드가 포함된 경우 → 주소 자동 업데이트
    if "주소" in memo_text:
        address_match = re.search(r"주소[:：]?\s*(.+)", memo_text)
        if address_match:
            extracted_address = address_match.group(1).strip()
            update_member_address(member_name, extracted_address)

    # (추후 구현) 메모 자체를 따로 메모 시트에 저장하려면 여기 구현
    print(f"[메모 저장] {member_name}: {memo_text}")
    return jsonify({"status": "success", "message": "메모 및 주소 처리 완료"})


























# ✅ 회원 삭제 공통 로직 (update_member에서도 호출 가능)
# ==========================================================================
# ✅ 회원 삭제 API (안전 확인 포함)
# ==========================================================================
# ✅ 회원 삭제 API
def delete_member_direct(name: str):
    try:
        if not name:
            return jsonify({"error": "회원명을 입력해야 합니다."}), 400

        sheet = get_member_sheet()
        data = sheet.get_all_records()

        for i, row in enumerate(data):
            if row.get('회원명') == name:
                # 삭제할 데이터 백업
                backup_sheet = get_backup_sheet()
                values = [[row.get(k, '') for k in row.keys()]]
                backup_sheet.append_row(values[0])

                # DB 시트에서 해당 행 삭제
                sheet.delete_rows(i + 2)  # 헤더 포함

                return jsonify({"message": f"'{name}' 회원 삭제 및 백업 완료"}), 200

        return jsonify({"error": f"'{name}' 회원을 찾을 수 없습니다."}), 404

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/delete_member', methods=['POST'])
def delete_member():
    name = request.get_json().get("회원명")
    return delete_member_direct(name)



























# ✅ 회원 삭제 API (안전 확인 + 디버깅 포함)
from itertools import chain

def remove_spaces(s):
    """문자열에서 모든 공백 제거"""
    return re.sub(r"\s+", "", s)

# 🔹 토큰 분리 유틸
def split_to_parts(text):
    """요청문을 구분자(와, 및, 그리고, , , 공백)로 분리"""
    clean_text = re.sub(r"\s+", " ", text.strip())
    return [p for p in re.split(r"와|및|그리고|,|\s+", clean_text) if p]




# ✅ 회원 삭제 API (안전 확인 + 디버깅 포함)
import re
from itertools import chain
from flask import request, jsonify

# 🔹 필드 매핑
field_map = {
    "휴대폰번호": ["휴대폰번호", "핸드폰", "폰번호", "전화번호", "휴대폰"],
    "회원번호": ["회원번호", "번호"],
    "특수번호": ["특수번호", "비번", "pw", "패스워드"],
    "가입일자": ["가입일자", "등록일", "가입일"],
    "생년월일": ["생년월일", "생일", "출생일"],
    "통신사": ["통신사", "이동통신사", "통신사명"],
    "친밀도": ["친밀도", "관계도", "친분도"],
    "근무처": ["근무처", "직장", "회사", "직장명"],
    "소개한분": ["소개한분", "추천인", "소개자"],
    "메모": ["메모", "노트", "비고"],
    "코드": ["코드", "회원코드", "code"],
    "주소": ["주소", "거주지", "배송지", "거주 주소"],
    "계보도": ["계보도", "계보", "네트워크"],
    "회원명": ["회원명", "이름", "성명", "Name"]
}

# 🔹 공백 제거 유틸
def remove_spaces(s):
    return re.sub(r"\s+", "", s)

# 🔹 토큰 분리 유틸
def split_to_parts(text):
    """요청문을 구분자(와, 및, 그리고, , , 공백)로 분리"""
    clean_text = re.sub(r"\s+", " ", text.strip())
    return [p for p in re.split(r"와|및|그리고|,|\s+", clean_text) if p]

@app.route('/delete_member_field_nl', methods=['POST'])
def delete_member_field_nl():
    try:
        print("=" * 50)
        print(f"[DEBUG] 요청 URL: {request.url}")
        print(f"[DEBUG] 요청 메서드: {request.method}")

        try:
            print(f"[DEBUG] Raw Body: {request.data.decode('utf-8')}")
        except Exception:
            pass

        req = request.get_json(force=True)
        print(f"[DEBUG] 파싱된 요청 JSON: {req}")

        text = req.get("요청문", "").strip()
        print(f"[DEBUG] 요청문: '{text}'")

        if not text:
            return jsonify({"error": "요청문을 입력해야 합니다."}), 400

        delete_keywords = ["삭제", "삭제해줘",  "비워", "비워줘", "초기화", "초기화줘",  "없애", "없애줘",  "지워", "지워줘"]

        # 1️⃣ 토큰 분리
        parts = split_to_parts(text)
        print(f"[DEBUG] 분리된 토큰: {parts}")

        # 2️⃣ 삭제 키워드 / 필드 키워드 매칭
        has_delete_kw = any(remove_spaces(dk) in [remove_spaces(p) for p in parts] for dk in delete_keywords)
        all_field_keywords = list(chain.from_iterable(field_map.values()))
        has_field_kw = any(remove_spaces(fk) in [remove_spaces(p) for p in parts] for fk in all_field_keywords)

        print(f"[DEBUG] 삭제 키워드 매칭: {has_delete_kw}, 필드 키워드 매칭: {has_field_kw}")

        if not (has_delete_kw and has_field_kw):
            print("[DEBUG] 삭제 명령 또는 필드 키워드 없음")
            return jsonify({"error": "삭제 명령이 아니거나 필드명이 포함되지 않았습니다."}), 400

        # 3️⃣ 정확 매칭된 필드 목록
        matched_fields = []
        for field, keywords in sorted(field_map.items(), key=lambda x: -max(len(k) for k in x[1])):
            for kw in keywords:
                if remove_spaces(kw) in [remove_spaces(p) for p in parts] and field not in matched_fields:
                    matched_fields.append(field)

        print(f"[DEBUG] 최종 매칭된 필드 목록: {matched_fields}")

        return delete_member_field_nl_internal(text, matched_fields)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def delete_member_field_nl_internal(text, matched_fields):
    print(f"[DEBUG] 내부 로직 시작. 요청문: '{text}'")

    # 회원명 추출
    name_match = re.match(r"^(\S+)", text)
    if not name_match:
        return jsonify({"error": "회원명을 찾을 수 없습니다."}), 400
    name = name_match.group(1)
    print(f"[DEBUG] 추출된 회원명: '{name}'")

    # 시트 데이터 로드
    sheet = get_member_sheet()
    try:
        print(f"[DEBUG] 연결된 시트 ID: {sheet.spreadsheet.id}, 시트 이름: {sheet.title}")
    except Exception as e:
        print(f"[DEBUG] 시트 메타정보 조회 실패: {e}")

    headers = sheet.row_values(1)
    print(f"[DEBUG] 시트 헤더: {headers}")

    data = sheet.get_all_records()
    all_names = [row.get('회원명') for row in data]
    print(f"[DEBUG] 시트 회원명 목록: {all_names}")

    # 회원 찾기 및 필드 업데이트
    for i, row in enumerate(data):
        if row.get('회원명') == name:
            print(f"[DEBUG] '{name}' 회원 발견 (시트 행 {i+2})")
            for field in matched_fields:
                if field in headers:
                    col_index = headers.index(field) + 1
                    print(f"[DEBUG] '{field}' → 열 인덱스 {col_index} 업데이트")
                    sheet.update_cell(i + 2, col_index, "")
                    sheet.update_cell(i + 2, col_index, "")
                    print(f"[DEBUG] '{field}' 필드 공란 처리 완료")
                else:
                    print(f"[DEBUG] '{field}' 필드가 시트 헤더에 없음 → 업데이트 불가")
            return jsonify({
                "message": f"'{name}' 회원의 {matched_fields} 필드가 삭제(공란 처리)되었습니다."
            }), 200

    print(f"[DEBUG] '{name}' 회원을 시트에서 찾지 못함")
    return jsonify({"error": f"'{name}' 회원을 찾을 수 없습니다."}), 404



















# 시트/DB 업데이트 함수 (샘플)
def append_to_sheet(sheet_name, row):
    ws = get_worksheet(sheet_name)
    ws.append_row(row, value_input_option="USER_ENTERED")

def update_member_field(member_name, field, value):
    ws = get_worksheet("회원DB")
    data = ws.get_all_values()
    headers = data[0]
    try:
        idx_name = headers.index("회원명")
        idx_field = headers.index(field)
    except ValueError:
        return False
    for i, row in enumerate(data[1:], start=2):
        if row[idx_name] == member_name:
            ws.update_cell(i, idx_field + 1, value)
            return True
    return False






# 메모 저장 루틴
# ==================================================================================
API_BASE = os.getenv("API_BASE")
API_URL = os.getenv("COUNSELING_API_URL")
HEADERS = {"Content-Type": "application/json"}

try:
    app
except NameError:
    app = Flask(__name__)

SHEET_KEYWORDS = {"상담일지", "개인일지", "활동일지", "회원메모", "회원주소"}
ACTION_KEYWORDS = {"저장", "기록", "입력"}

_SHEET_PAT = r"(?:상담\s*일지|개인\s*일지|활동\s*일지|회원\s*메모|회원\s*주소|상담일지|개인일지|활동일지|회원메모|회원주소)"
_ACTION_PAT = r"(?:저장|기록|입력)"

def quote_safe(text: str) -> str:
    if text is None:
        return ""
    return str(text).replace("\n", " ").replace("\r", " ").strip()

def _post(path: str, payload: dict):
    url = urljoin(API_BASE.rstrip('/') + '/', path.lstrip('/'))
    r = requests.post(url, json=payload, timeout=15, headers=HEADERS)
    r.raise_for_status()
    return r

def update_member_field(member_name, field, value):
    member_name = quote_safe(member_name)
    field = quote_safe(field)
    value = quote_safe(value)
    _post("/updateMember", {"요청문": f"{member_name} {field} ''"})
    _post("/updateMember", {"요청문": f"{member_name} {field} {value}"})

def get_member_sheet():
    return get_worksheet("DB")

def now_str_kr():
    tz = pytz.timezone("Asia/Seoul")
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M")

def update_member_field_strict(member_name: str, field_name: str, value: str) -> bool:
    sheet = get_member_sheet()
    headers = [h.strip() for h in sheet.row_values(1)]
    if "회원명" not in headers:
        raise RuntimeError("DB 시트에 '회원명' 헤더가 없습니다.")
    if field_name not in headers:
        raise RuntimeError(f"DB 시트에 '{field_name}' 헤더가 없습니다.")
    values = sheet.get_all_values()
    member_col = headers.index("회원명") + 1
    field_col = headers.index(field_name) + 1
    target_row = None
    for i, row in enumerate(values[1:], start=2):
        if len(row) >= member_col and row[member_col - 1] == member_name:
            target_row = i
            break
    if target_row is None:
        return False
    return bool(safe_update_cell(sheet, target_row, field_col, value, clear_first=True))






def save_to_sheet(sheet_name: str, member_name: str, content: str) -> bool:
    sheet = get_worksheet(sheet_name)
    if sheet is None:
        raise RuntimeError(f"'{sheet_name}' 시트를 찾을 수 없습니다.")

    ts = now_str_kr()

    # ✅ 저장 전에 내용 앞부분에서 회원명이 중복되면 제거
    clean_content = (content or "").strip()
    if member_name and clean_content.startswith(member_name):
        clean_content = clean_content[len(member_name):].strip()

    sheet.insert_row([ts, (member_name or "").strip(), clean_content], index=2)
    return True








def parse_request_line(text: str):
    if not text or not text.strip():
        return None, None, None, None
    s = text.strip()
    m = re.match(rf"^\s*(\S+)\s+({_SHEET_PAT})\s+({_ACTION_PAT})\s*(.*)$", s)
    if m:
        member_name, sheet_keyword_raw, action_keyword, content = m.groups()
        sheet_keyword = sheet_keyword_raw.replace(" ", "")
    else:
        parts = s.split(maxsplit=3)
        if len(parts) < 3:
            return None, None, None, None
        member_name, sheet_keyword, action_keyword = parts[0], parts[1], parts[2]
        content = parts[3] if len(parts) > 3 else ""
        sheet_keyword = sheet_keyword.replace(" ", "")
    if sheet_keyword not in SHEET_KEYWORDS:
        return member_name, None, action_keyword, content
    if action_keyword not in ACTION_KEYWORDS:
        return member_name, sheet_keyword, None, content
    return member_name, sheet_keyword, action_keyword, content







@app.route('/add_counseling', methods=['POST'])
def add_counseling():
    try:
        data = request.get_json()
        text = data.get("요청문", "").replace(".", "").strip()

        # ✅ 키워드 정규화
        replacements = {
            "개인 메모": "개인일지", "상담 일지": "상담일지",
            "활동 일지": "활동일지", "회원 메모": "회원메모",
            "제품 주문": "제품주문", "회원 주소": "회원주소"
        }
        for k, v in replacements.items():
            text = text.replace(k, v)

        # ✅ sheet 키워드 (띄어쓰기 허용 버전 포함)
        sheet_keywords = [
            "상담일지", "개인일지", "활동일지", "회원메모", "제품주문", "회원주소",
            "상담 일지", "개인 일지", "활동 일지", "회원 메모", "제품 주문", "회원 주소"
        ]
        action_keywords = ["저장", "기록", "입력"]

        # ✅ 회원명 추출 (띄어쓰기 버전 포함)
        match = re.search(r"([가-힣]{2,10})\s*(상담\s*일지|개인\s*일지|활동\s*일지|회원\s*메모|회원\s*주소|제품\s*주문)", text)
        if not match:
            return jsonify({"message": "회원명을 인식할 수 없습니다."})
        member_name = match.group(1)

        # ✅ 시트 키워드 추출 후 정규화 (공백 제거)
        matched_sheet = next((kw for kw in sheet_keywords if kw in text), None)
        if not matched_sheet:
            return jsonify({"message": "저장할 시트를 인식할 수 없습니다."})
        matched_sheet = matched_sheet.replace(" ", "")  # "개인 일지" → "개인일지"

        # ✅ 불필요한 키워드 제거 (회원명은 보존)
        for kw in sheet_keywords + action_keywords:
            text = text.replace(kw, "")
        text = text.strip()
        text = re.sub(r'^[:：]\s*', '', text)

        # ✅ 상담일지, 개인일지, 활동일지 저장
        if matched_sheet in ["상담일지", "개인일지", "활동일지"]:
            content = text.strip()
            if not content:
                return jsonify({"message": "저장할 내용이 비어 있습니다."}), 400
            if save_to_sheet(matched_sheet, member_name, content):
                return jsonify({"message": f"{member_name}님의 {matched_sheet} 저장이 완료되었습니다."})

        return jsonify({"message": "처리할 수 없는 시트입니다."})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500




    











# ======================================================================
# 메모 검색 (개인/상담/활동/전체)
# ======================================================================
# ======================================================================
# 메모 검색 (개인/상담/활동/전체)
# ======================================================================
SHEET_MAP = {
    "개인": "개인일지",
    "상담": "상담일지",
    "활동": "활동일지",
}

DT_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]


# ---------- Utils ----------
def parse_dt(dt_str: str):
    for fmt in DT_FORMATS:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return None


def parse_date_yyyymmdd(date_str: str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return None


def match_condition(text: str, keywords, mode: str):
    if not keywords:
        return True
    text_l = text.lower()
    kws = [kw.lower() for kw in keywords]
    if mode == "동시검색":
        return all(kw in text_l for kw in kws)
    return any(kw in text_l for kw in kws)


def search_in_sheet(sheet_name, keywords, search_mode="any",
                    start_date=None, end_date=None, limit=20):
    sheet = get_worksheet(sheet_name)   # ✅ 전역 spreadsheet 재사용
    rows = sheet.get_all_values()
    if not rows or len(rows[0]) < 3:
        return [], False

    records = rows[1:]  # 헤더 제외
    results = []

    for row in records:
        if len(row) < 3:
            continue

        작성일자, 회원명, 내용 = (row[0] or "").strip(), (row[1] or "").strip(), (row[2] or "").strip()
        작성일_dt = parse_dt(작성일자)
        if 작성일_dt is None:
            continue

        # 날짜 범위 필터
        if start_date and 작성일_dt < start_date:
            continue
        if end_date and 작성일_dt > (end_date + timedelta(days=1) - timedelta(seconds=1)):
            continue

        combined_text = f"{회원명} {내용}"
        if match_condition(combined_text, keywords, search_mode):
            results.append({
                "작성일자": 작성일자,
                "회원명": 회원명,
                "내용": 내용,
                "_작성일_dt": 작성일_dt
            })

    results.sort(key=lambda x: x["_작성일_dt"], reverse=True)
    for r in results:
        r.pop("_작성일_dt", None)

    has_more = len(results) > limit
    return results[:limit], has_more


# ---------- Routes ----------
@app.route("/search_memo", methods=["POST"])
def search_memo():
    """
    {
      "keywords": ["세금", "부가세"],
      "mode": "개인",             # 개인 / 상담 / 활동 / 전체
      "search_mode": "동시검색",  # any(기본) / 동시검색
      "start_date": "2025-01-01",
      "end_date": "2025-12-31",
      "limit": 20
    }
    """
    data = request.get_json(silent=True) or {}

    keywords = data.get("keywords", [])
    mode = data.get("mode", "전체")
    search_mode = data.get("search_mode", "any")
    limit = int(data.get("limit", 20))

    start_dt = parse_date_yyyymmdd(data.get("start_date")) if data.get("start_date") else None
    end_dt = parse_date_yyyymmdd(data.get("end_date")) if data.get("end_date") else None

    if not isinstance(keywords, list) or not keywords:
        return jsonify({"error": "keywords는 비어있지 않은 리스트여야 합니다."}), 400

    results, more_map = {}, {}

    try:
        if mode == "전체":
            for m, sheet_name in SHEET_MAP.items():
                r, more = search_in_sheet(sheet_name, keywords, search_mode, start_dt, end_dt, limit)
                results[m] = r
                if more: more_map[m] = True
        else:
            sheet_name = SHEET_MAP.get(mode)
            if not sheet_name:
                return jsonify({"error": f"잘못된 mode 값입니다: {mode}"}), 400
            r, more = search_in_sheet(sheet_name, keywords, search_mode, start_dt, end_dt, limit)
            results[mode] = r
            if more: more_map[mode] = True

        resp = {
            "status": "success",
            "search_params": {
                "keywords": keywords,
                "mode": mode,
                "search_mode": search_mode,
                "start_date": data.get("start_date"),
                "end_date": data.get("end_date"),
                "limit": limit
            },
            "results": results
        }
        if more_map:
            resp["more_results"] = {k: "더 많은 결과가 있습니다." for k in more_map}
        return jsonify(resp), 200
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/search_memo_from_text", methods=["POST"])
def search_memo_from_text():
    """
    {
      "text": "전체메모 검색 포항 동시",
      "limit": 20
    }
    """
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    limit = int(data.get("limit", 20))

    if not text:
        return jsonify({"error": "text가 비어 있습니다."}), 400

    tokens = text.split()
    mode = "전체"
    if "개인" in tokens: mode = "개인"
    elif "상담" in tokens: mode = "상담"
    elif "활동" in tokens: mode = "활동"
    elif "전체" in tokens or "전체메모" in tokens: mode = "전체"

    search_mode = "동시검색" if ("동시" in tokens or "동시검색" in tokens) else "any"

    ignore = {"검색","에서","해줘","해","줘","동시","동시검색","개인","상담","활동","전체","전체메모"}
    keywords = [t for t in tokens if t not in ignore]

    with app.test_request_context(json={
        "keywords": keywords,
        "mode": mode,
        "search_mode": search_mode,
        "limit": limit
    }):
        return search_memo()


# ---------- 내부 호출용 ----------
def run_all_memo_search_from_natural_text(text: str):
    """
    자연어 문장에서 keywords, search_mode를 추출해
    /search_memo API를 내부 호출합니다. (mode=전체 고정)
    """
    ignore_words = {"전체메모", "검색", "에서", "해줘", "해", "줘"}
    tokens = text.split()

    has_dongsi = "동시" in tokens or "동시검색" in tokens
    search_mode = "동시검색" if has_dongsi else "any"

    keywords = [kw for kw in tokens if kw not in ignore_words and kw not in {"동시", "동시검색"}]

    if not keywords:
        return jsonify({"error": "검색어가 없습니다."}), 400

    payload = {
        "keywords": keywords,
        "mode": "전체",
        "search_mode": search_mode,
        "limit": 20
    }

    with app.test_request_context(json=payload):
        return search_memo()





























    





# ✅ 제품주문시 날짜 입력으로 등록처리 
# ✅ 날짜 처리 통합 함수
def process_order_date(raw_date: str) -> str:
    try:
        if not raw_date or raw_date.strip() == "":
            return now_kst().strftime('%Y-%m-%d')

        text = raw_date.strip()
        today = now_kst()

        # ✅ "오늘", "어제", "내일"
        if "오늘" in text:
            return today.strftime('%Y-%m-%d')
        elif "어제" in text:
            return (today - timedelta(days=1)).strftime('%Y-%m-%d')
        elif "내일" in text:
            return (today + timedelta(days=1)).strftime('%Y-%m-%d')

        # ✅ YYYY-MM-DD 포맷 직접 확인
        try:
            dt = datetime.strptime(text, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

        # ✅ YYYY.MM.DD or YYYY/MM/DD → YYYY-MM-DD 변환
        match = re.search(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})", text)
        if match:
            y, m, d = match.groups()
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    except Exception as e:
        print(f"[날짜 파싱 오류] {e}")

    # ✅ 실패 시 오늘 날짜 반환
    return now_kst().strftime('%Y-%m-%d')













# parse_order_text() 함수는 자연어 문장에서 다음과 같은 주문 정보를 자동으로 추출하는 함수입니다:
# 예) "김지연 노니 2개 카드로 주문 저장" →
# → 회원명: 김지연, 제품명: 노니, 수량: 2, 결제방법: 카드

# ✅ 자연어 문장 파싱
def parse_order_text(text):
    result = {}

    # 1. 회원명
    match = re.match(r"(\S+)(?:님)?", text)
    if match:
        result["회원명"] = match.group(1)

    # 2. 제품명 + 수량
    prod_match = re.search(r"([\w가-힣]+)[\s]*(\d+)\s*개", text)
    if prod_match:
        result["제품명"] = prod_match.group(1)
        result["수량"] = int(prod_match.group(2))
    else:
        result["제품명"] = "제품"
        result["수량"] = 1

    # 3. 결제방법
    if "카드" in text:
        result["결재방법"] = "카드"
    elif "현금" in text:
        result["결재방법"] = "현금"
    elif "계좌" in text:
        result["결재방법"] = "계좌이체"
    else:
        result["결재방법"] = "카드"

    # 4. 주소 or 배송지
    address_match = re.search(r"(?:주소|배송지)[:：]\s*(.+?)(\s|$)", text)
    if address_match:
        result["배송처"] = address_match.group(1).strip()
    else:
        result["배송처"] = ""

    # 5. 주문일자
    result["주문일자"] = process_order_date(text)

    return result

























# ✅ 최근 주문 확인 후 삭제 요청 유도
@app.route("/delete_order_request", methods=["POST"])
def delete_order_request():
    try:
        sheet = get_product_order_sheet()
        all_values = sheet.get_all_values()

        if not all_values or len(all_values) < 2:
            return jsonify({"message": "등록된 주문이 없습니다."}), 404

        headers, rows = all_values[0], all_values[1:]
        row_count = min(5, len(rows))  # 최대 5건

        # 최신 주문 상단 5건을 가져옴
        recent_orders = [(i + 2, row) for i, row in enumerate(rows[:row_count])]

        response = []
        for idx, (row_num, row_data) in enumerate(recent_orders, start=1):
            try:
                내용 = {
                    "번호": idx,
                    "행번호": row_num,
                    "회원명": row_data[headers.index("회원명")],
                    "제품명": row_data[headers.index("제품명")],
                    "가격": row_data[headers.index("제품가격")],
                    "PV": row_data[headers.index("PV")],
                    "주문일자": row_data[headers.index("주문일자")]
                }
                response.append(내용)
            except Exception:
                continue  # 누락된 필드는 건너뜀

        return jsonify({
            "message": f"📌 최근 주문 내역 {len(response)}건입니다. 삭제할 번호(1~{len(response)})를 선택해 주세요.",
            "주문목록": response
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    







# ✅ 주문 삭제 확인 API
@app.route("/delete_order_confirm", methods=["POST"])
def delete_order_confirm():
    try:
        data = request.get_json()
        번호들 = data.get("삭제번호", "").strip()

        if 번호들 in ["없음", "취소", ""]:
            return jsonify({"message": "삭제 요청이 취소되었습니다."}), 200

        # 숫자만 추출 → 중복 제거 및 정렬
        번호_리스트 = sorted(set(map(int, re.findall(r'\d+', 번호들))))

        sheet = get_product_order_sheet()
        all_values = sheet.get_all_values()

        if not all_values or len(all_values) < 2:
            return jsonify({"error": "삭제할 주문 데이터가 없습니다."}), 400

        headers, rows = all_values[0], all_values[1:]
        row_count = min(5, len(rows))
        recent_rows = [(i + 2) for i in range(row_count)]  # 실제 행 번호

        # 입력 유효성 검사
        if not 번호_리스트 or any(n < 1 or n > row_count for n in 번호_리스트):
            return jsonify({"error": f"삭제할 주문 번호는 1 ~ {row_count} 사이로 입력해 주세요."}), 400

        # 행 번호 역순으로 정렬 후 삭제
        삭제행목록 = [recent_rows[n - 1] for n in 번호_리스트]
        삭제행목록.sort(reverse=True)

        for row_num in 삭제행목록:
            sheet.delete_rows(row_num)

        return jsonify({
            "message": f"{', '.join(map(str, 번호_리스트))}번 주문이 삭제되었습니다.",
            "삭제행번호": 삭제행목록
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500













# ✅ 조사 제거 함수 (이게 꼭 필요!)
def remove_josa(text):
    return re.sub(r'(으로|로|은|는|이|가|을|를|한|인|에게|에)?$', '', text)


# ✅ 자연어 파서
def parse_natural_query(user_input):
    user_input = user_input.strip()

    # ✅ 계보도 방향 표현 인식: 공백 유무 모두 대응
    if "계보도" in user_input:
        # '계보도 강소희 우측 회원', '계보도 강소희우측 회원', '계보도가 강소희우측인 회원' 모두 처리
        pos_match = re.search(r"계보도.*?([가-힣]+)\s*(우측|좌측)", user_input)
        if not pos_match:
            pos_match = re.search(r"계보도.*?([가-힣]+)(우측|좌측)", user_input)
        if pos_match:
            기준회원 = pos_match.group(1).strip()
            방향 = pos_match.group(2)
            print("🎯 계보도 방향 파싱 →", "계보도", f"{기준회원} {방향}")
            return "계보도", f"{기준회원}{방향}"

    # ✅ 일반 키워드 매핑
    keywords = {
        "계보도": ["계보도"],
        "소개한분": ["소개한분"],
        "코드": ["코드"],
        "분류": ["분류"],
        "리더님": ["리더", "리더님"]
    }

    for field, triggers in keywords.items():
        for trigger in triggers:
            if trigger in user_input:
                match = re.search(rf"{trigger}\s*(?:은|는|이|가|을|를|이란|이라는|에|으로|로)?\s*(.*)", user_input)
                if match:
                    raw_keyword = match.group(1).strip()
                    cleaned = re.sub(r'(인|한|한\s+)?\s*회원$', '', raw_keyword)
                    cleaned = re.split(r'[,\.\n\s]', cleaned)[0].strip()

                    if cleaned.isdigit() and len(cleaned) == 8:
                        return "회원번호", cleaned
                    return field, cleaned
    return None, None








# ✅ 자연어 기반 회원 검색 API
@app.route("/members/search-nl", methods=["POST"])
def search_by_natural_language():
    data = request.get_json()
    query = data.get("query")
    if not query:
        return Response("query 파라미터가 필요합니다.", status=400)

    offset = int(data.get("offset", 0))  # ✅ 추가된 부분

    field, keyword = parse_natural_query(query)
    print("🔍 추출된 필드:", field)
    print("🔍 추출된 키워드:", keyword)

    if not field or not keyword:
        return Response("자연어에서 검색 필드와 키워드를 찾을 수 없습니다.", status=400)

    try:
        sheet = get_member_sheet()
        records = sheet.get_all_records()


        print("🧾 전체 키 목록:", records[0].keys())  # ← 여기!


        normalized_field = field.strip()
        normalized_keyword = keyword.strip().lower()



        if normalized_field == "계보도":
            normalized_keyword = normalized_keyword.replace(" ", "")





        # ✅ 디버깅 출력
        print("🧾 전체 키 목록:", records[0].keys() if records else "레코드 없음")
        for m in records:
            cell = str(m.get(normalized_field, "")).strip().lower()
            print(f"🔎 '{normalized_keyword}' == '{cell}' → {normalized_keyword == cell}")

        # ✅ 대소문자 구분 없이 정확히 일치
        filtered = [
            m for m in records
            if normalized_keyword == str(m.get(normalized_field, "")).strip().lower().replace(" ", "")
        ]


        # ✅ 이름순 정렬
        filtered.sort(key=lambda m: m.get("회원명", ""))




        lines = [
            f"{m.get('회원명', '')} (회원번호: {m.get('회원번호', '')}" +
            (f", 특수번호: {m.get('특수번호', '')}" if m.get('특수번호', '') else "") +
            (f", 연락처: {m.get('휴대폰번호', '')}" if m.get('휴대폰번호', '') else "") +
            (f", {remove_josa(str(m.get('코드', '')).strip())}" if m.get('코드', '') else "") +
            ")"
            for m in filtered[offset:offset+40]
        ]







        # ✅ 다음 있음 표시
        has_more = offset + 40 < len(filtered)
        if has_more:
            lines.append("--- 다음 있음 ---")

        response_text = "\n".join(lines) if lines else "조건에 맞는 회원이 없습니다."
        return Response(response_text, mimetype='text/plain')

    except Exception as e:
        return Response(f"[서버 오류] {str(e)}", status=500)

    


















































# =================================================================
# 제품 주문
# =================================================================
# ✅ 날짜 파싱
def parse_date(text):
    date_match = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})", text)
    if date_match:
        return date_match.group(1)
    return now_kst().strftime("%Y-%m-%d")

# ✅ 규칙 기반 자연어 파싱
def parse_order_text(text):
    result = {}

    match = re.match(r"(\S+)(?:님)?", text)
    if match:
        result["회원명"] = match.group(1)

    prod_match = re.search(r"([\w가-힣]+)[\s]*(\d+)\s*개", text)
    if prod_match:
        result["제품명"] = prod_match.group(1)
        result["수량"] = int(prod_match.group(2))
    else:
        result["제품명"] = "제품"
        result["수량"] = 1

    if "카드" in text:
        result["결재방법"] = "카드"
    elif "현금" in text:
        result["결재방법"] = "현금"
    elif "계좌" in text:
        result["결재방법"] = "계좌이체"
    else:
        result["결재방법"] = "카드"

    address_match = re.search(r"(?:주소|배송지)[:：]\s*(.+?)(\s|$)", text)
    if address_match:
        result["배송처"] = address_match.group(1).strip()
    else:
        result["배송처"] = ""

    result["주문일자"] = parse_date(text)

    return result





# ✅ 한국 시간
def now_kst():
    return datetime.now(timezone(timedelta(hours=9)))

# =================================================================
# 제품 주문
# =================================================================
# ✅ 제품주문 시트 저장
# ✅ memberslist API 호출 함수
def addOrders(payload):
    resp = requests.post(MEMBERSLIST_API_URL, json=payload)
    resp.raise_for_status()
    return resp.json()

# 🔹 GPT Vision 분석 함수
def extract_order_from_uploaded_image(image_bytes):
    """
    image_bytes: BytesIO 객체
    """
    image_base64 = base64.b64encode(image_bytes.getvalue()).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = (
        "이미지를 분석하여 JSON 형식으로 추출하세요. "
        "여러 개의 제품이 있을 경우 'orders' 배열에 모두 담으세요. "
        "질문하지 말고 추출된 orders 전체를 그대로 저장할 준비를 하세요. "
        "(이름, 휴대폰번호, 주소)는 소비자 정보임. "
        "회원명, 결재방법, 수령확인, 주문일자 무시. "
        "필드: 제품명, 제품가격, PV, 주문자_고객명, 주문자_휴대폰번호, 배송처"
    )


    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }}
                ]
            }
        ],
        "temperature": 0
    }

    response = requests.post(OPENAI_API_URL, headers=headers, json=payload)
    response.raise_for_status()

    result_text = response.json()["choices"][0]["message"]["content"]

    # 코드블록 제거
    clean_text = re.sub(r"```(?:json)?", "", result_text).strip()

    try:
        order_data = json.loads(clean_text)
        return order_data
    except json.JSONDecodeError:
        return {"raw_text": result_text}










# =========================================================
# 자동 분기 라우트 (iPad / PC)
# =========================================================
@app.route("/upload_order", methods=["POST"])
def upload_order_auto():
    user_agent = request.headers.get("User-Agent", "").lower()

    # PC / iPad 판별
    is_pc = ("windows" in user_agent) or ("macintosh" in user_agent)

    if is_pc:
        return upload_order_pc()  # PC 전용
    else:
        return upload_order_ipad()  # iPad 전용



# ✅ 업로드 라우트 (iPad 명령어 자동 감지)
@app.route("/upload_order_ipad", methods=["POST"])  
def upload_order_ipad():
    mode = request.form.get("mode") or request.args.get("mode")
    member_name = request.form.get("회원명")
    image_file = request.files.get("image")
    image_url = request.form.get("image_url")
    message_text = request.form.get("message", "").strip()

    # 🔹 iPad 명령어 자동 감지
    if not mode and "제품주문 저장" in message_text:
        mode = "api"
        possible_name = message_text.replace("제품주문 저장", "").strip()
        if possible_name:
            member_name = possible_name

    if not mode:
        mode = "api"

    if not member_name:
        return jsonify({"error": "회원명 필드 또는 message에서 회원명을 추출할 수 없습니다."}), 400

    try:
        # 이미지 가져오기
        if image_file:
            image_bytes = io.BytesIO(image_file.read())
        elif image_url:
            img_response = requests.get(image_url)
            if img_response.status_code != 200:
                return jsonify({"error": "이미지 다운로드 실패"}), 400
            image_bytes = io.BytesIO(img_response.content)
        else:
            return jsonify({"error": "image(파일) 또는 image_url이 필요합니다."}), 400

        # GPT Vision 분석
        order_data = extract_order_from_uploaded_image(image_bytes)

        # orders 배열 보정
        if isinstance(order_data, dict) and "orders" in order_data:
            orders_list = order_data["orders"]
        elif isinstance(order_data, dict):
            orders_list = [order_data]
        else:
            return jsonify({"error": "GPT 응답이 올바른 JSON 형식이 아닙니다.", "응답": order_data}), 500

        # 🔹 결재방법, 수령확인 무조건 공란 처리
        for order in orders_list:
            order["결재방법"] = ""
            order["수령확인"] = ""



        if mode == "api":
            save_result = addOrders({
                "회원명": member_name,
                "orders": orders_list
            })
            return jsonify({
                "mode": "api",
                "message": f"{member_name}님의 주문이 저장되었습니다. (memberslist API)",
                "추출된_JSON": orders_list,
                "저장_결과": save_result
            })

        elif mode == "sheet":
            # Google Sheets 직접 저장 로직 (get_worksheet 구현 필요)
            db_ws = get_worksheet("DB")
            records = db_ws.get_all_records()
            member_info = next((r for r in records if r.get("회원명") == member_name), None)
            if not member_info:
                return jsonify({"error": f"회원 '{member_name}'을(를) 찾을 수 없습니다."}), 404

            order_date = now_kst().strftime("%Y-%m-%d %H:%M:%S")
            orders_ws = get_worksheet("제품주문")
            for product in order_data.get("제품목록", []):
                orders_ws.append_row([
                    order_date,
                    member_name,
                    member_info.get("회원번호"),
                    member_info.get("휴대폰번호"),
                    product.get("제품명"),
                    product.get("제품가격"),
                    product.get("PV"),
                    product.get("주문자_고객명"),
                    product.get("주문자_휴대폰번호"),
                    product.get("배송처"),
                    "",
                    ""
                ])
            return jsonify({
                "mode": "sheet",
                "status": "success",
                "saved_rows": len(order_data.get("제품목록", []))
            })

        else:
            return jsonify({"error": "mode 값은 'api' 또는 'sheet'여야 합니다."}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    




# ================================================================================
# ✅ PC 전용 업로드 (회원명 + "제품주문 저장" + 이미지)
@app.route("/upload_order_pc", methods=["POST"])
def upload_order_pc():
    mode = request.form.get("mode") or request.args.get("mode")
    member_name = request.form.get("회원명")
    image_file = request.files.get("image")
    image_url = request.form.get("image_url")
    message_text = request.form.get("message", "").strip()

    # 🔹 PC 명령어 자동 감지
    if not mode and "제품주문 저장" in message_text:
        mode = "api"
        possible_name = message_text.replace("제품주문 저장", "").strip()
        if possible_name:
            member_name = possible_name

    if not mode:
        mode = "api"

    if not member_name:
        return jsonify({"error": "회원명 필드 또는 message에서 회원명을 추출할 수 없습니다."}), 400

    try:
        # 이미지 가져오기
        if image_file:
            image_bytes = io.BytesIO(image_file.read())
        elif image_url:
            img_response = requests.get(image_url)
            if img_response.status_code != 200:
                return jsonify({"error": "이미지 다운로드 실패"}), 400
            image_bytes = io.BytesIO(img_response.content)
        else:
            return jsonify({"error": "image(파일) 또는 image_url이 필요합니다."}), 400

        # GPT Vision 분석
        order_data = extract_order_from_uploaded_image(image_bytes)

        # orders 배열 보정
        if isinstance(order_data, dict) and "orders" in order_data:
            orders_list = order_data["orders"]
        elif isinstance(order_data, dict):
            orders_list = [order_data]
        else:
            return jsonify({"error": "GPT 응답이 올바른 JSON 형식이 아닙니다.", "응답": order_data}), 500

        if mode == "api":
            save_result = addOrders({
                "회원명": member_name,
                "orders": orders_list
            })
            return jsonify({
                "mode": "api",
                "message": f"{member_name}님의 주문이 저장되었습니다. (memberslist API)",
                "추출된_JSON": orders_list,
                "저장_결과": save_result
            })

        elif mode == "sheet":
            # Google Sheets 직접 저장 로직
            db_ws = get_worksheet("DB")
            records = db_ws.get_all_records()
            member_info = next((r for r in records if r.get("회원명") == member_name), None)
            if not member_info:
                return jsonify({"error": f"회원 '{member_name}'을(를) 찾을 수 없습니다."}), 404

            order_date = now_kst().strftime("%Y-%m-%d %H:%M:%S")
            orders_ws = get_worksheet("제품주문")
            for product in order_data.get("제품목록", []):
                orders_ws.append_row([
                    order_date,
                    member_name,
                    member_info.get("회원번호"),
                    member_info.get("휴대폰번호"),
                    product.get("제품명"),
                    product.get("제품가격"),
                    product.get("PV"),
                    product.get("주문자_고객명"),
                    product.get("주문자_휴대폰번호"),
                    product.get("배송처"),
                    "",
                    ""
                ])
            return jsonify({
                "mode": "sheet",
                "status": "success",
                "saved_rows": len(order_data.get("제품목록", []))
            })

        else:
            return jsonify({"error": "mode 값은 'api' 또는 'sheet'여야 합니다."}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500
















# ==========================================================================
# 자연어 입력으로 제품주문 저장
# memberslist API 저장
# GPT로 자연어 주문 파싱
def parse_order_from_text(text):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    prompt = f"""
다음 문장에서 주문 정보를 JSON 형식으로 추출하세요.
여러 개의 제품이 있을 경우 'orders' 배열에 모두 담으세요.
질문하지 말고 추출된 orders 전체를 그대로 저장할 준비를 하세요.
(이름, 휴대폰번호, 주소)는 소비자 정보임.
회원명, 결재방법, 수령확인, 주문일자 무시.
필드: 제품명, 제품가격, PV, 결재방법, 주문자_고객명, 주문자_휴대폰번호, 배송처.

입력 문장:
{text}

JSON 형식:
{{
    "orders": [
        {{
            "제품명": "...",
            "제품가격": ...,
            "PV": ...,
            "결재방법": "...",
            "주문자_고객명": "...",
            "주문자_휴대폰번호": "...",
            "배송처": "..."
        }}
    ]
}}
"""
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0
    }
    response = requests.post(OPENAI_API_URL, headers=headers, json=payload)
    response.raise_for_status()
    result_text = response.json()["choices"][0]["message"]["content"]

    # 코드블록 제거 (멀티라인 지원)
    clean_text = re.sub(r"```(?:json)?", "", result_text, flags=re.MULTILINE).strip()
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        return {"raw_text": result_text}

# 자연어 주문 저장 라우트 (PC용)
@app.route("/upload_order_text", methods=["POST"])
def upload_order_text():
    text = request.form.get("message") or (request.json.get("message") if request.is_json else None)
    if not text:
        return jsonify({"error": "message 필드가 필요합니다."}), 400

    # 회원명 추출 (제품주문 저장 앞부분)
    member_name_match = re.match(r"^(\S+)\s*제품주문\s*저장", text)
    if not member_name_match:
        return jsonify({"error": "회원명을 찾을 수 없습니다."}), 400
    member_name = member_name_match.group(1)

    # GPT로 파싱
    order_data = parse_order_from_text(text)
    if not order_data.get("orders"):
        return jsonify({"error": "주문 정보를 추출하지 못했습니다.", "응답": order_data}), 400

    try:
        # memberslist API 저장
        save_result = addOrders({
            "회원명": member_name,
            "orders": order_data["orders"]
        })
        return jsonify({
            "status": "success",
            "회원명": member_name,
            "추출된_JSON": order_data["orders"],
            "저장_결과": save_result
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500





































































# 파싱된 주문 데이터를 받아 Google Sheets의 제품주문 시트에 저장하는 함수 handle_order_save(data)입니다.

# 즉, parse_order_text() 같은 파서에서 추출된 dict 형태의 주문 정보를 받아
# → 1줄로 정리된 주문 행(row)을 만들어
# → 시트에 추가하거나 중복이면 무시하려는 목적입니다.

# ✅ 공통 주문 저장 함수

# ✅ 주문 저장 함수
def handle_order_save(data):
    sheet = get_worksheet("제품주문")
    if not sheet:
        raise Exception("제품주문 시트를 찾을 수 없습니다.")

    order_date = process_order_date(data.get("주문일자", ""))
    # ✅ 회원명 정제
    raw_name = data.get("회원명", "")
    name = re.sub(r"\s*등록$", "", raw_name).strip()
    row = [
        order_date,
        data.get("회원명", ""),
        data.get("회원번호", ""),
        data.get("휴대폰번호", ""),
        data.get("제품명", ""),
        float(data.get("제품가격", 0)),
        float(data.get("PV", 0)),
        data.get("결재방법", ""),
        data.get("주문자_고객명", ""),
        data.get("주문자_휴대폰번호", ""),
        data.get("배송처", ""),
        data.get("수령확인", "")
    ]

    values = sheet.get_all_values()
    if not values:
        headers = [
            "주문일자", "회원명", "회원번호", "휴대폰번호",
            "제품명", "제품가격", "PV", "결재방법",
            "주문자_고객명", "주문자_휴대폰번호", "배송처", "수령확인"
        ]
        sheet.append_row(headers)

    # 중복 방지 로직
    #for existing in values[1:]:
    #    if (existing[0] == order_date and
    #        existing[1] == data.get("회원명") and
    #        existing[4] == data.get("제품명")):
    #        print("⚠️ 이미 동일한 주문이 존재하여 저장하지 않음")
    #        return

    #sheet.insert_row(row, index=2)


def handle_product_order(text, member_name):
    try:
        parsed = parse_order_text(text)  # 자연어 문장 → 주문 dict 변환
        parsed["회원명"] = member_name
        handle_order_save(parsed)  # 실제 시트 저장
        return jsonify({"message": f"{member_name}님의 제품주문 저장이 완료되었습니다."})
    except Exception as e:
        return jsonify({"error": f"제품주문 처리 중 오류 발생: {str(e)}"}), 500













# ✅ 제품주문시 날짜 입력으로 등록처리 

# ✅ 주문일자 처리
def process_order_date(raw_date: str) -> str:
    try:
        if not raw_date or raw_date.strip() == "":
            return now_kst().strftime('%Y-%m-%d')

        raw_date = raw_date.strip()

        if "오늘" in raw_date:
            return now_kst().strftime('%Y-%m-%d')
        elif "어제" in raw_date:
            return (now_kst() - timedelta(days=1)).strftime('%Y-%m-%d')
        elif "내일" in raw_date:
            return (now_kst() + timedelta(days=1)).strftime('%Y-%m-%d')

        datetime.strptime(raw_date, "%Y-%m-%d")
        return raw_date
    except Exception:
        return now_kst().strftime('%Y-%m-%d')












# 아이패드에서 이미지 인식으로 추출한 주문 데이터를 JSON 형태로 받아,
# Google Sheets의 "제품주문" 시트에 저장하는 API입니다.

# ✅ 아이패드에서 이미지 입력으로 제품주문처리 이미지 json으로 처리

# 주문 저장 엔드포인트
@app.route("/add_orders", methods=["POST"])
def add_orders():  # ← 누락된 함수 선언 추가
    data = request.json
    회원명 = data.get("회원명")
    orders = data.get("orders", [])

    try:
        sheet_title = os.getenv("GOOGLE_SHEET_TITLE")  # ← 환경변수에서 시트명 로딩
        spreadsheet = client.open(sheet_title)
        sheet = spreadsheet.worksheet("제품주문")

        # ✅ DB 시트에서 회원번호, 휴대폰번호 추출
        db_sheet = spreadsheet.worksheet("DB")
        member_records = db_sheet.get_all_records()

        회원번호 = ""
        회원_휴대폰번호 = ""
        for record in member_records:
            if record.get("회원명") == 회원명:
                회원번호 = record.get("회원번호", "")
                회원_휴대폰번호 = record.get("휴대폰번호", "")
                break

        # ✅ 주문 내용 시트에 삽입
        if orders:
            row_index = 2  # 항상 2행부터 위로 삽입
            for order in orders:
                row = [
                    order.get("주문일자", datetime.now().strftime("%Y-%m-%d")),  # ✅ 주문일자 우선, 없으면 오늘
                    회원명,
                    회원번호,
                    회원_휴대폰번호,
                    order.get("제품명", ""),
                    order.get("제품가격", ""),
                    order.get("PV", ""),
                    order.get("결재방법", ""),
                    order.get("주문자_고객명", ""),
                    order.get("주문자_휴대폰번호", ""),
                    order.get("배송처", ""),
                    order.get("수령확인", "")
                ]
                sheet.insert_row(row, row_index)
                row_index += 1

        return jsonify({"status": "success", "message": "주문이 저장되었습니다."})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
























# 이미지에서 추출한 제품 주문 데이터를 JSON 형식으로 받아서, Google Sheets의 "제품주문" 시트에 한 줄씩 저장하는 API입니다.

# ✅ 컴퓨터에서 이미지 입력으로 제품주문처리


def append_row_to_sheet(sheet, row):
    sheet.append_row(row, value_input_option="USER_ENTERED")

@app.route('/save_order_from_json', methods=['POST'])

def save_order_from_json():
    try:
        data = request.get_json()
        sheet = get_worksheet("제품주문")

        if not isinstance(data, list):
            return jsonify({"error": "JSON은 리스트 형식이어야 합니다."}), 400

        for item in data:
            row = [
                "",  # 주문일자 무시
                "",  # 회원명 무시
                "",  # 회원번호 무시
                "",  # 휴대폰번호 무시
                item.get("제품명", ""),
                item.get("제품가격", ""),
                item.get("PV", ""),
                "",  # 결재방법 무시
                item.get("주문자_고객명", ""),
                item.get("주문자_휴대폰번호", ""),
                item.get("배송처", ""),
                "",  # 수령확인 무시
            ]
            append_row_to_sheet(sheet, row)

        return jsonify({"status": "success", "count": len(data)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route('/saveOrder', methods=['POST'])
@app.route('/save_Order', methods=['POST'])
def saveOrder():
    try:
        payload = request.get_json(force=True)
        resp = requests.post(MEMBERSLIST_API_URL, json=payload)
        resp.raise_for_status()
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500














# ✅ 음성으로 제품등록 

# ✅ 날짜 파싱
def parse_date(text):
    today = datetime.today()
    if "오늘" in text:
        return today.strftime("%Y-%m-%d")
    elif "어제" in text:
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        match = re.search(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2})", text)
        if match:
            return re.sub(r"[./]", "-", match.group(1))
    return today.strftime("%Y-%m-%d")



# parse_order_text() 함수는 자연어 문장에서 다음과 같은 주문 정보를 자동으로 추출하는 함수입니다:
# 예) "김지연 노니 2개 카드로 주문 저장" →
# → 회원명: 김지연, 제품명: 노니, 수량: 2, 결제방법: 카드

# ✅ 자연어 문장 파싱
def parse_order_text(text):
    result = {}

    # 1. 회원명
    match = re.match(r"(\S+)(?:님)?", text)
    if match:
        result["회원명"] = match.group(1)

    # 2. 제품명 + 수량
    prod_match = re.search(r"([\w가-힣]+)[\s]*(\d+)\s*개", text)
    if prod_match:
        result["제품명"] = prod_match.group(1)
        result["수량"] = int(prod_match.group(2))
    else:
        result["제품명"] = "제품"
        result["수량"] = 1

    # 3. 결제방법
    if "카드" in text:
        result["결재방법"] = "카드"
    elif "현금" in text:
        result["결재방법"] = "현금"
    elif "계좌" in text:
        result["결재방법"] = "계좌이체"
    else:
        result["결재방법"] = "카드"

    # 4. 주소 or 배송지
    address_match = re.search(r"(?:주소|배송지)[:：]\s*(.+?)(\s|$)", text)
    if address_match:
        result["배송처"] = address_match.group(1).strip()
    else:
        result["배송처"] = ""

    # 5. 주문일자
    result["주문일자"] = parse_date(text)

    return result













# 클라이언트로부터 주문 관련 자연어 문장을 받아서 분석(파싱)한 후, Google Sheets 같은 시트에 저장하는 역할
# POST 요청의 JSON body에서 "text" 필드 값을 받아와 user_input 변수에 저장
# 예: "김지연 노니 2개 카드 주문 저장" 같은 자연어 문장

# ✅ API 엔드포인트
@app.route("/parse_and_save_order", methods=["POST"])
def parse_and_save_order():
    try:
        user_input = request.json.get("text", "")
        parsed = parse_order_text(user_input)
        save_order_to_sheet(parsed)
        return jsonify({
            "status": "success",
            "message": f"{parsed['회원명']}님의 주문이 저장되었습니다.",
            "parsed": parsed
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500





# 잘 작동함







if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)


