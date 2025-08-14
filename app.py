import os
import json
import re
import pandas as pd
import gspread
import pytz
import uuid
import openai
from flask import Flask, request, jsonify
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from gspread.utils import rowcol_to_a1
from datetime import datetime
from collections import Counter
from oauth2client.service_account import ServiceAccountCredentials

import requests
import time

from flask import  Response




# 적용합니다
# 작용
###




def some_function():
    print("작업 시작")
    time.sleep(1)
    print("작업 완료")



# ✅ 환경 변수 로드


if os.getenv("RENDER") is None:  # 로컬에서 실행 중일 때만
    from dotenv import load_dotenv
    dotenv_path = os.path.abspath('.env')
    if not os.path.exists(dotenv_path):
        raise FileNotFoundError(f".env 파일이 존재하지 않습니다: {dotenv_path}")
    load_dotenv(dotenv_path)

# 공통 처리
GOOGLE_SHEET_KEY = os.getenv("GOOGLE_SHEET_KEY")
GOOGLE_SHEET_TITLE = os.getenv("GOOGLE_SHEET_TITLE")  # ✅ 시트명 불러오기

# 한국 시간 가져오는 함수
def now_kst():
    return datetime.now(pytz.timezone("Asia/Seoul"))



# ✅ 확인용 출력 (선택)
print("✅ GOOGLE_SHEET_TITLE:", os.getenv("GOOGLE_SHEET_TITLE"))
print("✅ GOOGLE_SHEET_KEY 존재 여부:", "Yes" if os.getenv("GOOGLE_SHEET_KEY") else "No")


app = Flask(__name__)

if not os.getenv("GOOGLE_SHEET_KEY"):
    raise EnvironmentError("환경변수 GOOGLE_SHEET_KEY가 설정되지 않았습니다.")
if not os.getenv("GOOGLE_SHEET_TITLE"):  # ✅ 시트 이름도 환경변수에서 불러옴
    raise EnvironmentError("환경변수 GOOGLE_SHEET_TITLE이 설정되지 않았습니다.")


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
    필드패턴 = r"(회원명|휴대폰번호|회원번호|비밀번호|가입일자|생년월일|통신사|친밀도|근무처|계보도|소개한분|주소|메모|코드|카드사|카드주인|카드번호|유효기간|비번|카드생년월일|분류|회원단계|연령/성별|직업|가족관계|니즈|애용제품|콘텐츠|습관챌린지|비즈니스시스템|GLC프로젝트|리더님)"
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
    return get_worksheet("개인메모")

def get_search_memo_by_tags_sheet():
    return get_worksheet("개인메모")

def get_dailyrecord_sheet():
    return get_worksheet("활동일지")

def get_product_order_sheet():
    return get_worksheet("제품주문")    

def get_image_sheet():
    return get_worksheet("사진저장")

def get_backup_sheet():
    return get_worksheet("백업")


# ✅ 환경 변수 로드 및 GPT API 키 설정
openai.api_key = os.getenv("OPENAI_API_KEY")

# ✅ Google Sheets 인증
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)









# ✅ Google Sheets 연동 함수
def get_worksheet(sheet_name):
    try:
        sheet = client.open(GOOGLE_SHEET_TITLE)
        return sheet.worksheet(sheet_name)
    except Exception as e:
        print(f"[시트 접근 오류] {e}")
        return None




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
    "비밀번호": "비밀번호",
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



























def safe_update_cell(sheet, row, col, value, max_retries=3, delay=2):
    for attempt in range(1, max_retries + 1):
        try:


            sheet.update_cell(row, col, value)
            return True
        except gspread.exceptions.APIError as e:
            if "429" in str(e):
                print(f"[⏳ 재시도 {attempt}] 429 오류 → {delay}초 대기")
                time.sleep(delay)
                delay *= 2
            else:
                raise
    print("[❌ 실패] 최대 재시도 초과")
    return False










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
        # 수정
        updated_member, 수정된필드 = parse_request_and_update(요청문, member)
        print("[🧪 디버그] 수정된 필드:", 수정된필드)








        수정결과 = []
        for key, value in updated_member.items():
            if key.endswith("_기록"):
                continue
            if key.strip().lower() in headers:
                col = headers.index(key.strip().lower()) + 1
                print(f"[⬆️ 저장 시도] row={row_index}, col={col}, value={value}")


                success = safe_update_cell(sheet, row_index, col, value)
                if success:
                    수정결과.append({"필드": key, "값": value})

        return jsonify({"status": "success", "회원명": name, "수정": 수정결과}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500







# ========================================================================================
# ================================
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
    "비밀번호": "비밀번호",
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
        "휴대폰번호": "휴대폰번호", "회원번호": "회원번호", "비밀번호": "비밀번호",
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









import re

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
    # 비밀번호 패턴: 영문/숫자/특수문자 포함, 6~20자
    match = re.search(r"비밀번호(?:를|는)?\s*([^\s\"']{6,20})", text)
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
        return "비밀번호"  # ✅ 비밀번호 후보로 인식
    


    return None








# ✅ 회원 수정
# ✅ 자연어 요청문에서 필드와 값 추출, 회원 dict 수정


# ✅ 회원 수정 API
def parse_request_and_update(data: str, member: dict) -> tuple:
    수정된필드 = {}



    # ✅ 다중 필드 전체 순회용
    필드맵 = {
        "주소": "주소", "휴대폰번호": "휴대폰번호", "회원번호": "회원번호", "비밀번호": "비밀번호",
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
                필드 = 필드맵[키워드]
                member[필드] = 값
                member[f"{필드}_기록"] = f"(기록됨: {값})"
                수정된필드[필드] = 값









    # ✅ 각 필드 블록 파싱
    for idx, (start, 키) in enumerate(positions):
        끝 = positions[idx + 1][0] if idx + 1 < len(positions) else len(data)
        block = data[start:끝]
        match = re.search(rf"{키}\s*(?:를|은|는|이|가|:|：)?\s*(.+)", block)
        if match:

            값 = match.group(1).strip()



            # ✅ 공통 꼬리 명령어 제거 대상 필드
            if 키 in {"주소", "메모", "휴대폰번호", "회원번호", "비밀번호", "가입일자", "생년월일",
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




            elif 키 == "비밀번호":
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
                    phone_match = re.search(r"010[-]?\d{3,4}[-]?\d{4}", value)
                    value = phone_match.group(0) if phone_match else ""

                수정된필드[inferred_field] = value
                member[inferred_field] = value
                member[f"{inferred_field}_기록"] = f"(기록됨: {value})"

        # ✅ 추가: 여러 값이 있을 경우 각각 형식 기반 추론
        for token in tokens:
            # 휴대폰번호 형태
            if re.match(r"010[-]?\d{3,4}[-]?\d{4}", token):
                phone = extract_phone(token)
                member["휴대폰번호"] = phone
                member["휴대폰번호_기록"] = f"(기록됨: {phone})"
                수정된필드["휴대폰번호"] = phone

            # 숫자 6~8자리: 회원번호 추정
            elif re.match(r"^\d{6,8}$", token):
                member_no = extract_member_number(token) or token
                member["회원번호"] = member_no
                member["회원번호_기록"] = f"(기록됨: {member_no})"
                수정된필드["회원번호"] = member_no

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
                        sheet.update_cell(i + 2, headers.index(key) + 1, value)
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

    sheet.update_cell(row_index, col_index, address)
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


































# ✅ 회원 삭제 API (안전 확인 포함)
# ✅ 회원 삭제 API
@app.route('/delete_member', methods=['POST'])
def delete_member():
    try:
        name = request.get_json().get("회원명")
        if not name:
            return jsonify({"error": "회원명을 입력해야 합니다."}), 400

        # DB 시트
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
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500










def extract_nouns(text):
    return re.findall(r'[가-힣]{2,}', text)

def generate_tags(text):
    nouns = extract_nouns(text)
    top_keywords = [word for word, _ in Counter(nouns).most_common(5)]
    return top_keywords



API_URL = os.getenv("COUNSELING_API_URL")

HEADERS = {"Content-Type": "application/json"}

def determine_mode(content: str) -> str:
    if "상담일지" in content:
        return "1"  # 상담일지 (공유)
    elif "개인메모" in content:
        return "개인"
    elif "활동일지" in content:
        return "3"
    else:
        return "1"  # 기본값










@app.route('/save_note', methods=['POST'])
def save_note():
    data = request.json
    요청문 = data.get("요청문", "")
    mode = determine_mode(요청문)

    payload = {
        "요청문": 요청문,
        "mode": mode,
        "allow_unregistered": True
    }

    response = requests.post(API_URL, json=payload, headers=HEADERS)
    if response.ok:
        return jsonify({"status": "success", "message": "저장 완료"})
    else:
        return jsonify({"status": "error", "message": response.text})
        























# save_to_sheet(sheet_name, member_name, content)로 호출되며,
# Google Sheets의 특정 시트에 상담일지 / 개인메모 / 활동일지 등을 저장하는 공통 함수입니다.

# ✅ 시트 저장 함수 (Google Sheets 연동 및 중복 확인)
def save_to_sheet(sheet_name, member_name, content):
    try:
        sheet = get_worksheet(sheet_name)
        if sheet is None:
            print(f"[오류] '{sheet_name}' 시트를 찾을 수 없습니다.")
            return False

        existing = sheet.get_all_values()
        contents = [row[2] if len(row) > 2 else "" for row in existing]  # 내용은 3열 기준
        if content in contents:
            print(f"[중복] 이미 같은 내용이 '{sheet_name}'에 존재합니다.")
            return False

        now = datetime.now(pytz.timezone("Asia/Seoul"))
        time_str = now.strftime("%Y-%m-%d %H:%M")

        clean_name = re.sub(r"[^\w가-힣]", "", member_name.strip())
        clean_content = content.strip()
        sheet.insert_row([time_str.strip(), clean_name, clean_content], index=2)


        print(f"[저장완료] '{sheet_name}' 시트에 저장 완료")
        return True

    except Exception as e:
        print(f"[시트 저장 오류: {sheet_name}] {e}")
        return False


















def clean_request_text(text):
    return ' '.join(text.replace("회원", "").split())


@app.route('/add_counseling', methods=['POST'])
def add_counseling():
    try:
        data = request.get_json()
        text = data.get("요청문", "").replace(".", "").strip()

        # ✅ 키워드 정규화
        replacements = {
            "개인 메모": "개인메모", "상담 일지": "상담일지",
            "활동 일지": "활동일지", "회원 메모": "회원메모",
            "제품 주문": "제품주문", "회원 주소": "회원주소"
        }
        for k, v in replacements.items():
            text = text.replace(k, v)

        sheet_keywords = ["상담일지", "개인메모", "활동일지", "직접입력", "회원메모", "제품주문", "회원주소"]
        action_keywords = ["저장", "기록", "입력"]



        if "전체메모" in text and "검색" in text:
            return search_all_memo_by_text_from_natural()




        # ✅ 🔽 검색 요청 분기 추가
        if "개인메모" in text and "검색" in text:
            return search_memo_by_text_from_natural(text)



        if "상담일지" in text and "검색" in text:
            return search_counseling_by_text_from_natural(text)
        


        if "활동일지" in text and "검색" in text:
            return search_activity_by_text_from_natural(text)





        # ✅ 유효성 검사
        if not any(kw in text for kw in sheet_keywords) or not any(kw in text for kw in action_keywords):
            return jsonify({
                "message": "저장하려면 '상담일지', '개인메모', '활동일지', '회원메모', '제품주문', '회원주소' 중 하나와 '저장', '기록', '입력' 같은 동작어를 포함해 주세요."
            })



        # ✅ 회원명 추출 (ex: "이태수 상담일지 저장...")
        
        match = re.search(r"([가-힣]{2,4})\s*(상담일지|개인메모|활동일지|직접입력|회원메모|제품주문|회원주소)", text)



        if not match:
            return jsonify({"message": "회원명을 인식할 수 없습니다."})
        member_name = match.group(1)

        # ✅ 시트 키워드 추출
        matched_sheet = next((kw for kw in sheet_keywords if kw in text), None)
        if not matched_sheet:
            return jsonify({"message": "저장할 시트를 인식할 수 없습니다."})
        

        # ✅ 불필요한 키워드 제거
        for kw in [member_name] + sheet_keywords + action_keywords:
            text = text.replace(kw, "")
        text = text.strip()
        text = re.sub(r'^[:：]\s*', '', text)



        # ✅ 제품주문 처리 분기
        if matched_sheet == "제품주문":
            return handle_product_order(text, member_name)















        # ✅ DB 시트 필드 업데이트 함수
        def update_member_field(field_name, value, member_name):
            sheet = get_member_sheet()
            db = sheet.get_all_records()
            headers = [h.strip().lower() for h in sheet.row_values(1)]
            matching_rows = [i for i, row in enumerate(db) if row.get("회원명") == member_name]
            if not matching_rows:
                return jsonify({"message": f"'{member_name}' 회원을 찾을 수 없습니다."})

            row_index = matching_rows[0] + 2
            if field_name.lower() in headers:
                col_index = headers.index(field_name.lower()) + 1
                success = safe_update_cell(sheet, row_index, col_index, value)
                if success:
                    return jsonify({"message": f"{member_name}님의 {field_name}이(가) DB 시트에 저장되었습니다."})
                else:
                    return jsonify({"message": f"'{member_name}' {field_name} 저장 실패 (safe_update_cell 실패)."})
            else:
                return jsonify({"message": f"'{field_name}' 필드가 시트에 존재하지 않습니다."})




        if matched_sheet == "회원메모":
            member_name = extract_member_name(text)
            return update_member_field("메모", text, member_name)


        if matched_sheet == "회원주소":
            return update_member_field("주소", text)





        # ✅ 상담일지, 개인메모, 활동일지 시트 저장
        if matched_sheet in ["상담일지", "개인메모", "활동일지"]:
            if save_to_sheet(matched_sheet, member_name, text):
                return jsonify({"message": f"{member_name}님의 {matched_sheet} 저장이 완료되었습니다."})
            else:
                return jsonify({"message": f"같은 내용이 이미 '{matched_sheet}' 시트에 저장되어 있습니다."})

        return jsonify({"message": "처리할 수 없는 시트입니다."})




    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    




    





            
    
    
    






# ===========================================================================
# 상담일지 시트에서 단어 기반으로 유사한 메모를 검색하는 기능을 수행합니다.
@app.route("/search_counseling_by_text_from_natural", methods=["POST"])
def search_counseling_by_text_from_natural():
    try:
        data = request.get_json()
        keywords = data.get("keywords", [])
        limit = int(data.get("limit", 20))
        sort_order = data.get("sort", "desc")
        match_mode = data.get("match_mode", "any")

        print("▶ 상담일지 검색 조건:", keywords, match_mode)

        if not keywords or not isinstance(keywords, list):
            return jsonify({"error": "keywords는 비어 있지 않은 리스트여야 합니다."}), 400

        sheet = get_counseling_sheet()
        values = sheet.get_all_values()[1:]
        results = []

        for row in values:
            if len(row) < 3:
                continue
            date_str, member, content = row[0], row[1], row[2]

            combined_text = f"{member} {content}"
            if match_mode == "all" and not all(kw.lower() in combined_text.lower() for kw in keywords):
                continue
            if match_mode == "any" and not any(kw.lower() in combined_text.lower() for kw in keywords):
                continue

            try:
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            except ValueError:
                continue

            results.append({
                "날짜": date_str,
                "회원명": member,
                "내용": content,
                "날짜_obj": parsed_date
            })

        results.sort(key=lambda x: x["날짜_obj"], reverse=(sort_order == "desc"))

        for r in results:
            del r["날짜_obj"]

        return jsonify({
            "검색조건": {
                "키워드": keywords,
                "매칭방식": match_mode,
                "정렬": sort_order
            },
            "검색결과": results[:limit]
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ✅ 자연어 텍스트에서 키워드 추출 및 매칭 방식 자동 판단
def run_counseling_search_from_natural_text(text):
    ignore_words = ["상담일지", "검색", "에서", "해줘", "해", "줘"]
    words = [kw for kw in text.split() if kw not in ignore_words]

    if not words:
        return jsonify({"error": "검색어가 없습니다."}), 400

    match_mode = "all" if "동시" in words else "any"
    keywords = [kw for kw in words if kw != "동시"]

    with app.test_request_context(json={
        "keywords": keywords,
        "limit": 20,
        "sort": "desc",
        "match_mode": match_mode
    }):
        return search_counseling_by_text_from_natural()


























# ===========================================================================
# 개인 메모 시트에서 단어 기반으로 유사한 메모를 검색하는 기능을 수행합니다.
@app.route("/search_memo_by_text", methods=["POST"])
def search_memo_by_text():
    try:
        data = request.get_json()

        all_keywords = data.get("keywords", [])
        limit = int(data.get("limit", 20))
        sort_order = data.get("sort", "desc")
        match_mode = data.get("match_mode", "any")

        # 🔹 검색 조건 로깅
        print("===== 📌 검색 조건 =====")
        print(f"검색 키워드: {all_keywords if all_keywords else '없음'}")
        print(f"매칭 방식: {match_mode}")
        print("========================")

        sheet = get_mymemo_sheet()
        values = sheet.get_all_values()[1:]
        results = []

        for row in values:
            if len(row) < 3:
                continue

            date_str, member, content = row[0], row[1], row[2]
            combined_text = f"{member} {content}"

            if not match_condition(combined_text, all_keywords, match_mode):
                continue

            try:
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            except ValueError:
                continue

            results.append({
                "날짜": date_str,
                "회원명": member,
                "내용": content,
                "날짜_obj": parsed_date
            })

        results.sort(key=lambda x: x["날짜_obj"], reverse=(sort_order == "desc"))
        for r in results:
            del r["날짜_obj"]

        response = {
            "검색조건": {
                "검색어": all_keywords,
                "매칭방식": match_mode,
                "정렬": sort_order,
                "결과_최대개수": limit
            },
            "검색결과": results[:limit]
        }

        return jsonify(response), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ✅ 자연어 텍스트에서 키워드 추출 및 매칭 방식 자동 판단
def run_memo_search_from_natural_text(text):
    ignore_words = ["개인메모", "검색", "에서", "해줘", "해", "줘"]
    words = [kw for kw in text.split() if kw not in ignore_words]

    if not words:
        return jsonify({"error": "검색어가 없습니다."}), 400

    match_mode = "all" if "동시" in words else "any"
    keywords = [kw for kw in words if kw != "동시"]

    with app.test_request_context(json={
        "keywords": keywords,
        "limit": 20,
        "sort": "desc",
        "match_mode": match_mode
    }):
        return search_memo_by_text()


# ✅ 키워드 포함 여부 판별 함수
def match_condition(text, keywords, mode):
    if not keywords:
        return True
    text = text.lower()
    keywords = [kw.lower() for kw in keywords]
    if mode == "all":
        return all(kw in text for kw in keywords)
    return any(kw in text for kw in keywords)




























# ===========================================================================
# 활동일지 시트에서 단어 기반으로 유사한 메모를 검색하는 기능을 수행합니다.
@app.route("/search_activity_by_text_from_natural", methods=["POST"])
def search_activity_by_text_from_natural():
    try:
        data = request.get_json()
        keywords = data.get("keywords", [])
        limit = int(data.get("limit", 20))
        sort_order = data.get("sort", "desc")
        match_mode = data.get("match_mode", "any")

        print("▶ 활동일지 검색 조건:", keywords, match_mode)

        if not keywords or not isinstance(keywords, list):
            return jsonify({"error": "keywords는 비어 있지 않은 리스트여야 합니다."}), 400

        sheet = get_dailyrecord_sheet()
        values = sheet.get_all_values()[1:]
        results = []

        for row in values:
            if len(row) < 3:
                continue
            date_str, member, content = row[0], row[1], row[2]

            combined_text = f"{member} {content}"
            if match_mode == "all" and not all(kw.lower() in combined_text.lower() for kw in keywords):
                continue
            if match_mode == "any" and not any(kw.lower() in combined_text.lower() for kw in keywords):
                continue

            try:
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            except ValueError:
                continue

            results.append({
                "날짜": date_str,
                "회원명": member,
                "내용": content,
                "날짜_obj": parsed_date
            })

        results.sort(key=lambda x: x["날짜_obj"], reverse=(sort_order == "desc"))

        for r in results:
            del r["날짜_obj"]

        return jsonify({
            "검색조건": {
                "키워드": keywords,
                "매칭방식": match_mode,
                "정렬": sort_order
            },
            "검색결과": results[:limit]
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ✅ 자연어 텍스트에서 키워드 추출 및 매칭 방식 자동 판단
def run_activity_search_from_natural_text(text):
    ignore_words = ["활동일지", "검색", "에서", "해줘", "해", "줘"]
    words = [kw for kw in text.split() if kw not in ignore_words]

    if not words:
        return jsonify({"error": "검색어가 없습니다."}), 400

    match_mode = "all" if "동시" in words else "any"
    keywords = [kw for kw in words if kw != "동시"]

    with app.test_request_context(json={
        "keywords": keywords,
        "limit": 20,
        "sort": "desc",
        "match_mode": match_mode
    }):
        return search_activity_by_text_from_natural()



















# ===========================================================================
# 전체메모 에서 단어 기반으로 유사한 메모를 검색하는 기능을 수행합니다.
@app.route("/search_all_memo_by_text_from_natural", methods=["POST"])
def search_all_memo_by_text_from_natural():
    try:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"error": "JSON 데이터가 유효하지 않거나 없습니다."}), 400

        raw_text = data.get("text", "")
        if not raw_text.strip() and "keywords" in data:
            raw_text = " ".join(data["keywords"])

        if not raw_text.strip():
            return jsonify({"error": "검색어가 없습니다."}), 400

        return run_all_memo_search_from_natural_text(raw_text)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ✅ 자연어 기반 전체메모 검색 함수 (분리된 내부 처리용)
def run_all_memo_search_from_natural_text(text):
    ignore_words = ["전체메모", "검색", "에서", "해줘", "해", "줘", "동시"]
    words = [kw for kw in text.split() if kw not in ignore_words]
    has_dongsi = "동시" in text.split()
    match_mode = "all" if has_dongsi else "any"
    keywords = words

    if not keywords:
        return jsonify({"error": "검색어가 없습니다."}), 400

    payload = {
        "keywords": keywords,
        "limit": 20,
        "sort": "desc",
        "match_mode": match_mode
    }

    with app.test_client() as client:
        개인메모 = client.post("/search_memo_by_text", json=payload)
        활동일지 = client.post("/search_activity_by_text_from_natural", json=payload)
        상담일지 = client.post("/search_counseling_by_text_from_natural", json=payload)

    def extract_results(response):
        try:
            json_data = response.get_json()
            if json_data and "검색결과" in json_data:
                return json_data["검색결과"]
        except Exception:
            pass
        return []

    result_lines = []

    for label, res in [("개인메모", 개인메모), ("활동일지", 활동일지), ("상담일지", 상담일지)]:
        result_lines.append(f"=== {label} ===")
        for r in extract_results(res):
            result_lines.append(f"{r['날짜']} {r['회원명']} {r['내용']}")
        result_lines.append("")

    response_text = "\n".join(result_lines)
    return response_text, 200, {"Content-Type": "text/plain; charset=utf-8"}


    


    























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

def get_worksheet(sheet_name):
    sheet_title = os.getenv("GOOGLE_SHEET_TITLE")  # env에서 불러옴
    spreadsheet = client.open(sheet_title)
    worksheet = spreadsheet.worksheet(sheet_name)
    return worksheet


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










# parse_order_text()로부터 추출된 주문 정보를 받아, Google Sheets의 "제품주문" 시트에 한 줄로 저장하는 함수입니다.

# ✅ 주문 저장
def save_order_to_sheet(parsed):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
    sheet_title = os.getenv("GOOGLE_SHEET_TITLE")
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    client = gspread.authorize(creds)

    ss = client.open(sheet_title)
    db_sheet = ss.worksheet("DB")
    order_sheet = ss.worksheet("제품주문")

    # 회원 정보 조회
    members = db_sheet.get_all_records()
    회원명 = parsed["회원명"]
    회원번호 = ""
    회원_휴대폰 = ""
    for m in members:
        if m.get("회원명") == 회원명:
            회원번호 = m.get("회원번호", "")
            회원_휴대폰 = m.get("휴대폰번호", "")
            break

    for _ in range(parsed.get("수량", 1)):
        row = [
            parsed.get("주문일자"),
            회원명,
            회원번호,
            회원_휴대폰,
            parsed.get("제품명"),
            "0",  # 제품가격
            "0",  # PV
            parsed.get("결재방법"),
            회원명,
            회원_휴대폰,
            parsed.get("배송처"),
            "0"
        ]
        order_sheet.insert_row(row, 2, value_input_option="USER_ENTERED")









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
            (f", 비밀번호: {m.get('비밀번호', '')}" if m.get('비밀번호', '') else "") +
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

    





# 실행
# 샐행이 되는지 테스트




@app.route("/debug_sheet", methods=["GET"])
def debug_sheet():
    sheet = get_mymemo_sheet()
    values = sheet.get_all_values()
    return jsonify(values), 200








# 서버 실행
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)




