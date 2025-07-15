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

from utils.sheets import get_order_sheet, get_member_info

import requests
import time
from utils.sheets import get_order_sheet, get_member_info

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







def clean_value_expression(text: str) -> str:
    particles = ['로', '으로', '은', '는', '을', '를', '수정해 줘']
    for p in particles:
        text = re.sub(rf'(\S+){p}(\W)', r'\1\2', text)
        text = re.sub(rf'(\S+)\s+{p}(\W)', r'\1\2', text)
    return text








# ======================================================================================


@app.route("/update_member", methods=["POST"])
def update_member():
    try:
        data = request.get_json(force=True)
        요청문 = data.get("요청문", "").strip()

        요청문 = clean_value_expression(요청문)  # ✅ 추가

        if not 요청문:
            return jsonify({"error": "요청문이 비어 있습니다."}), 400

        sheet = get_member_sheet()
        db = sheet.get_all_records()
        headers = [h.strip().lower() for h in sheet.row_values(1)]


     
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









        수정결과 = []
        for key, value in updated_member.items():
            if key.endswith("_기록"):
                continue
            if key.strip().lower() in headers:
                col = headers.index(key.strip().lower()) + 1
                success = safe_update_cell(sheet, row_index, col, value)
                if success:
                    수정결과.append({"필드": key, "값": value})

        return jsonify({"status": "success", "회원명": name, "수정": 수정결과}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500




# ========================================================================================




# ✅ 회원 수정
# ✅ 자연어 요청문에서 필드와 값 추출, 회원 dict 수정


# ✅ 회원 수정 API
def parse_request_and_update(data: str, member: dict) -> tuple:
    수정된필드 = {}

    # 허용된 필드만 제한
    field_map = {
        "회원명": "회원명",
        "휴대폰번호": "휴대폰번호",
        "회원번호": "회원번호",
        "계보도": "계보도",
        "비밀번호": "비밀번호"  # ✅ 필요시 추가
    }
        
    

    # ✅ "계보도 다음 문구" 무조건 필드로 처리
    계보도_패턴 = re.search(r"계보도[를은는]?\s*([가-힣]{2,})(?:\s*(좌측|우측|라인|왼쪽|오른쪽))?", data)
    if 계보도_패턴:
        이름 = 계보도_패턴.group(1)
        방향 = 계보도_패턴.group(2)

        if 방향:
            value = f"{이름} {방향}"
        else:
            value = 이름  # 방향이 없을 경우, 이름만 기록

        member["계보도"] = value
        member["계보도_기록"] = f"(기록됨: {value})"
        수정된필드["계보도"] = value



    계보도_이름 = 계보도_패턴.group(1) if 계보도_패턴 else None



    # 요청문에 명시된 키워드가 있는지 확인
    used_keywords = [k for k in field_map if k in data]

    # 키워드 기반 추출 우선
    if used_keywords:
        keywords_pattern = '|'.join(used_keywords)

        for keyword in used_keywords:
            field = field_map[keyword]
            pattern = rf"{keyword}(?:를|은|는|이|:|：)?\s*(?P<value>.+?)(?=\s+(?:{keywords_pattern})(?:를|은|는|이|:|：)?|\s*$)"
            matches = re.finditer(pattern, data)

            for match in matches:
                value_raw = match.group("value").strip()
                value_raw = re.sub(r'\s+', ' ', value_raw)
                # 더 강력한 후처리: 계보도 등에서 꼬리 명령어 제거
                value = re.sub(r"(으로|로)?\s*(다시)?\s*(수정|변경|해줘|해|바꿔줘|바꿔|바꿈)?[^\w가-힣]*$", "", value_raw).strip()



                if field == "회원명":
                    # 계보도 이름이 회원명으로 잘못 인식되는 것 방지
                    if 계보도_이름 and 계보도_이름 in value:
                        continue




                elif field == "회원번호":
                        match = re.search(r"\b회원번호\s*[:\-]?\s*(\d{4,8})\b", data)


                        if match:
                            value = match.group(1)
                        else:
                            continue  # 명시적으로 건너뜀



                elif field == "휴대폰번호":
                    match = re.search(r"\b010[-]?\d{3,4}[-]?\d{4}\b", data)
                    value = match.group(0) if match else ""




                elif field == "비밀번호":
                    value = value.strip().rstrip(",")  # <-- ✅ 쉼표 제거






                elif field == "계보도":
                    # ✅ '강소희우측' → '강소희 우측' 형태로 정리
                    lineage_match = re.match(r"([가-힣]{2,})\s*(좌측|우측|라인|왼쪽|오른쪽)", value)
                    if lineage_match:
                        value = f"{lineage_match.group(1)} {lineage_match.group(2)}"
                    else:
                        # ✅ '강소희 수정해 줘' 같은 경우 → '강소희'로 정리
                        name_only = re.match(r"([가-힣]{2,})", value)
                        if name_only:
                            value = name_only.group(1)
                        else:
                            value = re.sub(r"\s+", " ", value)















    else:
        # 키워드가 없을 경우 추론
        tokens = data.strip().split()
        if len(tokens) >= 2:
            name_candidate = tokens[0]
            value_candidate = ' '.join(tokens[1:]).replace("수정", "").strip()

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

    return member, 수정된필드

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







# ==========================================================================================================




# ✅ 명령어에서 회원명, 회원번호 추출
# ✅ 회원 등록 명령 파싱 함수
# ✅ 통합 파싱 함수 (개선된 정규식 + 안정성 보강)
def parse_registration(text):
    text = text.replace("\n", " ").replace("\r", " ").replace("\xa0", " ").strip()
    print(f"[🔍DEBUG] 전처리된 입력 text: '{text}'")

    name = number = phone = lineage = ""

    # ✅ 휴대폰번호 추출 (01012345678, 010-1234-5678 등 허용)
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
        # ✅ 이름 + 번호 + '회원등록' 포함 시 추출
        match = re.search(r"([가-힣]{2,10})\s+(\d{6,})", text)
        if match and "회원등록" in text:
            name = match.group(1).strip()
            number = re.sub(r"[^\d]", "", match.group(2)).strip()



            print(f"[✅DEBUG] 번호 포함 등록 형식 → name: '{name}', number: '{number}'")
        else:
            # ✅ 이름만 + '회원등록'
            match = re.search(r"^([가-힣]{2,10})\s*회원등록$", text)
            if match:
                name = match.group(1).strip()
                print(f"[✅DEBUG] 이름만 포함된 등록 형식 → name: '{name}'")

    # ✅ fallback 이름
    if not name and korean_words:
        name = korean_words[0]
        print(f"[ℹ️DEBUG] fallback 적용 → name: {name}")

    # ✅ fallback 회원번호
    if not number:
        print("[ℹ️DEBUG] 회원번호 없이 등록됨")
        number = ""





    # ✅ 계보도 추정 - 정규식 기반 우선 추출
    lineage_match = re.search(r"계보도.*?'(.+?)'", text)
    if lineage_match:
        lineage = lineage_match.group(1).strip()
        print(f"[🎯DEBUG] 정규식으로 계보도 추출됨: {lineage}")
    else:

        # ✅ 계보도 추정
        위치어 = ["좌측", "우측", "라인", "왼쪽", "오른쪽"]
        불필요_계보도 = ["회원등록", "회원", "등록"]
        필터링된 = [w for w in korean_words if w not in 불필요_계보도]


    if name:
        필터링된 = [w for w in 필터링된 if w not in name]

    if len(필터링된) >= 2 and 필터링된[-1] in 위치어:
        lineage = f"{필터링된[-2]} {필터링된[-1]}"
    elif 필터링된:
        lineage = 필터링된[-1]

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
                    "계보도": lineage
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
            "계보도": lineage
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
    for keyword in field_map:
        # 유연한 한글 + 숫자 + 기호 값 처리
        pattern = rf"{keyword}\s*[:：]?\s*([^\s]+)"
        for match in re.finditer(pattern, data):
            value_raw = match.group(1)
            value = re.sub(r"(으로|로|에|를|은|는)$", "", value_raw)
            field = field_map[keyword]
            member[field] = value
            member[f"{field}_기록"] = f"(기록됨: {value})"
    return member



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

        sheet.insert_row([time_str, member_name, content], index=2)
        print(f"[저장완료] '{sheet_name}' 시트에 저장 완료")
        return True

    except Exception as e:
        print(f"[시트 저장 오류: {sheet_name}] {e}")
        return False














# ✅ /add_counseling 처리 API (자연어 입력 기반 저장 + mode 분기)
@app.route('/add_counseling', methods=['POST'])
def add_counseling():
    try:
        data = request.get_json()
        text = data.get("요청문", "")

        # ✅ 시트 키워드 정규화 처리
        text = text.replace("개인 메모", "개인메모")
        text = text.replace("상담 일지", "상담일지")
        text = text.replace("활동 일지", "활동일지")
        text = text.replace("회원 메모", "회원메모")

        sheet_keywords = ["상담일지", "개인메모", "활동일지", "직접입력", "회원메모"]
        action_keywords = ["저장", "기록", "입력"]

        text = text.replace(".", "").strip()




        if not any(kw in text for kw in sheet_keywords) or not any(kw in text for kw in action_keywords):
            return jsonify({"message": "저장하려면 '상담일지', '개인메모', '활동일지', '회원메모' 중 하나와 '저장', '기록', '입력' 같은 동작어를 함께 포함해 주세요."})

        match = re.search(r'([가-힣]{2,3})\s*(상담일지|개인메모|활동일지|직접입력|회원메모)', text)
        if not match:
            return jsonify({"message": "회원명을 인식할 수 없습니다."})
        member_name = match.group(1)
        matched_sheet = match.group(2)

        # ✅ 키워드 제거 및 본문 정리
        for kw in sheet_keywords + action_keywords:
            text = text.replace(f"{member_name}{kw}", "")
            text = text.replace(f"{member_name} {kw}", "")
            text = text.replace(kw, "")
        text = text.strip()
        text = re.sub(r'^[:：]\s*', '', text)








        # ✅ 회원메모는 DB 시트의 메모 필드에 저장
        if matched_sheet == "회원메모":
            sheet = get_member_sheet()
            db = sheet.get_all_records()
            headers = [h.strip().lower() for h in sheet.row_values(1)]

            matching_rows = [i for i, row in enumerate(db) if row.get("회원명") == member_name]
            if not matching_rows:
                return jsonify({"message": f"'{member_name}' 회원을 찾을 수 없습니다."})

            row_index = matching_rows[0] + 2

            if "메모".lower() in headers:
                col_index = headers.index("메모".lower()) + 1
                success = safe_update_cell(sheet, row_index, col_index, text)
                print("메모 업데이트 시도:", row_index, col_index, text, "성공 여부:", success)

                if success:
                    return jsonify({"message": f"{member_name}님의 메모가 DB 시트에 저장되었습니다."})
                else:
                    return jsonify({"message": f"'{member_name}' 메모 저장 실패 (safe_update_cell 실패)."})
            else:
                return jsonify({"message": "'메모' 필드가 시트에 존재하지 않습니다."})










        if matched_sheet not in ["상담일지", "개인메모", "활동일지"]:
            return jsonify({"message": "저장할 시트를 인식할 수 없습니다."})

        if save_to_sheet(matched_sheet, member_name, text):
            return jsonify({"message": f"{member_name}님의 {matched_sheet} 저장이 완료되었습니다."})
        else:
            return jsonify({"message": f"같은 내용이 이미 '{matched_sheet}' 시트에 저장되어 있습니다."})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



    

            
    
    
    




    












@app.route("/search_memo_by_tags", methods=["POST"])
def search_memo_by_tags():
    try:
        data = request.get_json()
        input_tags = data.get("tags", [])
        limit = int(data.get("limit", 10))
        sort_by = data.get("sort_by", "date").lower()
        min_match = int(data.get("min_match", 1))

        if not input_tags:
            return jsonify({"error": "태그 리스트가 비어 있습니다."}), 400
        if sort_by not in ["date", "tag"]:
            return jsonify({"error": "sort_by는 'date' 또는 'tag'만 가능합니다."}), 400

        sheet = get_mymemo_sheet()
        values = sheet.get_all_values()[1:]  # 헤더 제외
        results = []

        for row in values:
            if len(row) < 3:
                continue
            member, date_str, content = row[0], row[1], row[2]

            try:
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            except ValueError:
                continue  # 날짜 형식 오류시 건너뜀

            memo_tags = extract_nouns(content)
            similarity = len(set(input_tags) & set(memo_tags))
            if similarity >= min_match:
                results.append({
                    "회원명": member,
                    "날짜": date_str,
                    "내용": content,
                    "일치_태그수": similarity,
                    "날짜_obj": parsed_date
                })

        # 정렬 조건 적용
        if sort_by == "tag":
            results.sort(key=lambda x: (x["일치_태그수"], x["날짜_obj"]), reverse=True)
        else:  # 기본: 날짜순
            results.sort(key=lambda x: (x["날짜_obj"], x["일치_태그수"]), reverse=True)

        # 날짜 객체 제거
        for r in results:
            del r["날짜_obj"]

        return jsonify({"검색결과": results[:limit]}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500











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









# 있어여



# 서버 실행
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)




