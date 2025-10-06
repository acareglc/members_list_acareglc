# =====================================================
# 표준 라이브러리
# =====================================================
import os
import re
import io
import time
import json
import base64
import calendar
import logging
import inspect
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from flask import request, g
from utils.sheets import get_worksheet

# =====================================================
# 외부 라이브러리
# =====================================================
import pytz
import requests
from flask import request, Response, jsonify

# =====================================================
# 내부 모듈
# =====================================================
from utils.sheets import (
    get_gsheet_data,
    get_member_sheet,
    get_rows_from_sheet,
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL")


def get_member_fields() -> list:
    """
    DB 시트의 회원 필드 목록 반환
    - 회원 정보 수정/등록 시 허용되는 필드 정의
    """
    return [
        "회원명", "회원번호", "휴대폰번호", "특수번호", "가입일자", "생년월일", "통신사", "친밀도",
        "근무처", "계보도", "소개한분", "주소", "메모", "코드", "카드사", "카드주인", "카드번호",
        "유효기간", "비번", "카드생년월일", "분류", "회원단계", "연령/성별", "직업", "가족관계",
        "니즈", "애용제품", "콘텐츠", "습관챌린지", "비즈니스시스템", "GLC프로젝트", "리더님", "특수번호"
    ]



# ======================================================================================
# common
# ======================================================================================

# ======================================================================================
# ✅ 디버그용 유틸
# ======================================================================================
def simulate_delay(seconds: int = 1):
    """작업 시작/완료를 출력하며 지정된 시간만큼 대기 (디버그용)"""
    print("작업 시작")
    time.sleep(seconds)
    print("작업 완료")



# ======================================================================================
# ✅ 날짜/시간 유틸
# ======================================================================================
def now_kst() -> datetime:
    """한국시간(KST) 기준 현재 시각 반환"""
    return datetime.now(timezone(timedelta(hours=9)))


def process_order_date(raw_date: str) -> str:
    """
    주문 저장 시 날짜 입력 처리
    - "오늘", "어제", "내일" → 실제 날짜
    - YYYY-MM-DD / YYYY.MM.DD / YYYY/MM/DD → YYYY-MM-DD
    - 실패 시 오늘 날짜 반환
    """
    try:
        if not raw_date or raw_date.strip() == "":
            return now_kst().strftime('%Y-%m-%d')

        text = raw_date.strip()
        today = now_kst()

        if "오늘" in text:
            return today.strftime('%Y-%m-%d')
        elif "어제" in text:
            return (today - timedelta(days=1)).strftime('%Y-%m-%d')
        elif "내일" in text:
            return (today + timedelta(days=1)).strftime('%Y-%m-%d')

        # YYYY-MM-DD
        try:
            dt = datetime.strptime(text, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

        # YYYY.MM.DD / YYYY/MM/DD → YYYY-MM-DD
        match = re.search(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})", text)
        if match:
            y, m, d = match.groups()
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    except Exception as e:
        print(f"[날짜 파싱 오류] {e}")

    return now_kst().strftime('%Y-%m-%d')


# ======================================================================================
# ✅ 문자열 보조 유틸
# ======================================================================================
def remove_josa(s: str) -> str:
    """단어 끝의 조사(이/가/은/는/을/를/과/와/의/으로/로) 제거"""
    return re.sub(r'(이|가|은|는|을|를|과|와|의|으로|로)$', '', s.strip())


def remove_spaces(s: str) -> str:
    """문자열 내 모든 공백 제거"""
    return re.sub(r'\s+', '', s)


def split_to_parts(s: str) -> list[str]:
    """문자열을 공백 단위로 분리하여 리스트 반환"""
    return re.split(r'\s+', s.strip())


def parse_dt(s: str):
    """
    문자열을 datetime 객체로 변환
    지원 포맷: YYYY-MM-DD HH:MM, YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
    실패하면 None 반환
    """
    if not s:
        return None
    s = s.strip()
    for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"]:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None













# ======================================================================================
# text_cleaner
# ======================================================================================
# ======================================================================================
# ✅ 꼬리 명령어 정제
# ======================================================================================
def clean_tail_command(text: str) -> str:
    """
    요청문 끝에 붙은 불필요한 꼬리 명령어 제거
    - 조사("로", "으로")와 함께 붙은 경우도 제거
    - 흔한 명령형 꼬리 ("수정해줘", "변경", "바꿔줘", "해주세요" 등) 처리
    """
    if not text:
        return text
    s = text.strip()

    tail_phrases = [
        "정확히 수정해줘", "수정해줘", "변경해줘", "바꿔줘",
        "수정", "변경", "바꿔", "삭제",
        "저장해줘", "기록", "입력", "해주세요", "해줘", "남겨"
    ]
    for phrase in tail_phrases:
        pattern = rf"(?:\s*(?:으로|로))?\s*{re.escape(phrase)}\s*[^\w가-힣]*$"
        s = re.sub(pattern, "", s)
    return s.strip()


# ======================================================================================
# ✅ 값 정제 (조사/불필요 기호 제거)
# ======================================================================================
def clean_value_expression(text: str) -> str:
    """
    값에 붙은 조사/불필요한 문자/꼬리 명령어 제거
    - "서울로" → "서울"
    - "010-1111-2222번" → "010-1111-2222"
    - "12345," → "12345"
    - "주소 서울 수정해 줘" → "주소 서울"
    """
    if not text:
        return text
    s = text.strip()

    # 1) 일반적인 조사 제거
    s = re.sub(r"(으로|로|으로의|로의|으로부터|로부터|은|는|이|가|을|를|와|과|에서|에)$", "", s)

    # 2) 자주 나오는 꼬리 명령어 제거
    particles = ['값을', '수정해 줘', '수정해줘', '변경해 줘', '변경해줘', '삭제해 줘', '삭제해줘']
    for p in particles:
        pattern = rf'({p})\s*$'
        s = re.sub(pattern, '', s)

    # 3) 불필요한 기호 제거
    s = s.strip(" ,.")

    return s


# ======================================================================================
# ✅ 본문 정제 (회원명/불필요 단어 제거)
# ======================================================================================


def clean_content(text: str, member_name: str = None) -> str:
    """
    메모/요청문에서 불필요한 기호, 회원명 등을 제거한 정제 문자열 반환
    """
    if not text:
        return ""

    # 불필요한 앞뒤 기호 제거
    s = text.strip(" \t:：,，.'\"“”‘’")

    # 회원명 + 선택적 '님' + 기호 제거 (예: "이태수.", "이태수 .", "이태수님," → "")
    if member_name:
        pattern = rf"{re.escape(member_name)}\s*(님)?\s*[:：,，.]*"
        s = re.sub(pattern, "", s)

    return s.strip()




# utils/text_cleaner.py

def build_member_query(user_input: str) -> dict:
    """
    자연어 입력을 API용 JSON 쿼리로 변환합니다.
    불필요한 조사/단어를 제거하여 핵심 키워드만 남깁니다.
    예: "코드가 A인 회원" -> { "query": "코드 A 회원" }
    """
    replacements = [
        ("가 ", " "), ("이 ", " "), ("은 ", " "), ("는 ", " "),
        ("인 ", " "), ("중 ", " "), ("명단", ""), ("사람", "회원"),
    ]
    query = user_input
    for old, new in replacements:
        query = query.replace(old, new)

    query = " ".join(query.split())  # 불필요한 공백 제거
    return {"query": query}




def normalize_code_query(text: str) -> str:
    """
    코드 검색용 query 정규화
    - 코드a, 코드 A, 코드: b, 코드 :C, 코드aa → 코드A, 코드B, 코드C, 코드AA
    """
    if not text:
        return ""
    match = re.search(r"코드\s*[:：]?\s*([a-zA-Z]+)", text, re.IGNORECASE)
    if match:
        return f"코드{match.group(1).upper()}"
    return text.strip()





# utils/text_cleaner.py

def clean_member_query(text: str) -> str:
    """
    회원 관련 요청문에서 불필요한 액션 단어 제거
    (조회/검색/등록/삭제/탈퇴/추가 등)
    
    ❗주의: '수정', '변경', '업데이트' 등은 intent 분석에 필요하므로 제거하지 않음
    """
    if not isinstance(text, str):
        return ""

    original = text.strip()
    cleaned = original

    # ✅ '수정', '변경', '업데이트' 등은 제거 대상에서 제외
    tokens_to_remove = [
        "회원검색", "회원 검색", 
        "탈퇴",
        "회원추가", "회원 추가", "추가"
    ]

    removed_tokens = []
    for token in tokens_to_remove:
        if token in cleaned:
            cleaned = cleaned.replace(token, "").strip()
            removed_tokens.append(token)

    # ✅ 디버그 로그 출력
    if removed_tokens:
        print(f"[clean_member_query] 원문: '{original}'")
        print(f"[clean_member_query] 제거된 토큰: {removed_tokens}")
        print(f"[clean_member_query] 최종 query: '{cleaned}'")

    return cleaned




def clean_memo_query(text: str, intent: str = None) -> str:
    """
    메모 관련 요청문에서 불필요한 액션 단어 제거
    intent에 따라 제거 규칙 다르게 적용
    """
    original = text
    if not intent:
        if "저장" in text:
            intent = "memo_save"
        elif "검색" in text or "조회" in text:
            intent = "memo_search"


    if intent == "memo_save":
        # 저장은 남겨둠 (삭제/조회/검색만 제거)
        tokens_to_remove = ["삭제", "조회", "검색"]
    elif intent == "memo_search":
        # 검색/조회만 제거
        tokens_to_remove = ["삭제", "조회"]
    else:
        # 일반적인 경우
        tokens_to_remove = ["저장", "삭제", "조회", "검색"]

    removed_tokens = []
    for t in tokens_to_remove:
        if t in text:
            removed_tokens.append(t)
            text = text.replace(t, "")

    if removed_tokens:
        print(f"[clean_memo_query] 원문: '{original}'")
        print(f"[clean_memo_query] 제거된 토큰: {removed_tokens}")
        print(f"[clean_memo_query] 최종 query: '{text.strip()}'")

    return text.strip()









def clean_order_query(text: str) -> str:
    """
    주문 관련 요청문에서 불필요한 액션 단어 제거
    (저장, 등록 같은 관리용 키워드는 제거, 제품명·수량·결제방식·주소는 유지)
    """
    if not isinstance(text, str):
        return ""
    cleaned = text.strip()
    tokens_to_remove = [
        "주문저장", "제품주문저장", "제품주문 등록", "제품주문",
        "주문 저장", "제품 저장",
        "주문 등록", "제품 등록",
        "주문", "저장", "등록"
    ]
    for token in tokens_to_remove:
        cleaned = cleaned.replace(token, "").strip()
    return cleaned










# ======================================================================================
# utils_string
# ======================================================================================


def is_match(content, keywords, member_name=None, search_mode="any"):
    """
    키워드 매칭 함수
    - content: 메모 내용
    - keywords: 검색할 키워드 리스트
    - member_name: 선택적 회원명 (필터)
    - search_mode: "any" → 하나라도 포함 / "동시검색" → 모두 포함
    """
    if not keywords:
        return True
    if search_mode == "any":
        return any(kw in content for kw in keywords)
    return all(kw in content for kw in keywords)


def match_condition(text: str, keywords: list[str], mode: str = "any") -> bool:
    """
    주어진 text에 대해 키워드 매칭 검사
    - mode="any": 하나라도 포함되면 True
    - mode="all": 전부 포함되어야 True
    """
    if not text or not keywords:
        return False
    if mode == "all":
        return all(k in text for k in keywords)
    return any(k in text for k in keywords)
















# ======================================================================================
# utils_search
# ======================================================================================

# ---------------------------------------------------------
# 로거 설정 (중복 방지 포함)
# ---------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:  # ✅ 중복 방지
    handler = logging.StreamHandler()  # 콘솔 출력
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

from utils.sheets import get_member_sheet





# ---------------------------------------------------------
# 1. 쿼리 정규화
# ---------------------------------------------------------
# 🔹 1. 입력 쿼리 정규화 함수
def normalize_query(query: str) -> str:
    # 1) 영문 → 대문자로 통일
    query = query.upper()
    
    # 2) 특수문자 제거 (한글/영문/숫자/공백만 남김)
    query = re.sub(r"[^가-힣A-Z0-9\s]", " ", query)

    # 3) 한글과 영문/숫자가 붙어 있으면 강제 분리
    query = re.sub(r"([가-힣])([A-Z0-9])", r"\1 \2", query)
    query = re.sub(r"([A-Z0-9])([가-힣])", r"\1 \2", query)

    # 4) 중복 공백 제거
    query = re.sub(r"\s+", " ", query).strip()

    return query



# =====================================================================
# ✅ fallback 자연어 검색
# =====================================================================
def fallback_natural_search(query: str) -> Dict[str, str]:
    query = query.strip()

    # 삭제, 등록 등 앞 단어 제거
    # 예: "회원삭제 이판사" → "이판사"
    query = re.sub(r"^(회원)?(삭제|제거|등록|추가|조회|검색)\s*", "", query)

    if re.fullmatch(r"\d{3}-\d{3,4}-\d{4}", query):
        return {"휴대폰번호": query}

    if re.fullmatch(r"\d{5,}", query):
        return {"회원번호": query}

    return {"회원명": query}



# ---------------------------------------------------------
# 1. 범용 검색 엔진 (옵션 지원)
# ---------------------------------------------------------
def search_members(data, search_params, options=None):
    """
    회원 검색 유틸
    - data: Worksheet 객체 또는 list(dict)
    - search_params: {"회원명": "이태수", "가입일__gte": "2024-01-01"} 등
    - options: {"match_mode": {"회원명": "partial", "코드": "exact", ...}}
        - default: 코드/회원번호 = exact, 나머지 = partial
    - 특수 규칙:
        "코드a" 또는 "코드 a" → 무조건 코드 필드에서 A 검색
    """

    # ✅ Worksheet 객체일 경우 자동 변환
    if hasattr(data, "get_all_records"):
        rows = data.get_all_records()
    else:
        rows = data

    results = []

    # ✅ 검색 모드 기본값
    default_match_mode = {
        "코드": "exact",
        "회원번호": "exact"
    }
    if options and "match_mode" in options:
        match_mode = {**default_match_mode, **options["match_mode"]}
    else:
        match_mode = default_match_mode

    # ✅ 특수 처리: search_params 에서 "query" 키워드가 들어왔을 때
    if "query" in search_params:
        query = search_params["query"].strip().lower()

        # "코드a" 또는 "코드 a" → 코드=A 검색
        if query in ["코드a", "코드 a"]:
            search_params = {"코드": "A"}

        # "코드 + 알파벳" 패턴 자동 처리
        elif query.startswith("코드"):
            code_value = query.replace("코드", "").strip().upper()
            if code_value:
                search_params = {"코드": code_value}
            else:
                search_params = {}

        else:
            # query 가 "회원명" 검색어로 들어왔다고 가정
            search_params = {"회원명": query}

    # ✅ 실제 검색 수행
    for row in rows:
        match = True
        for key, value in search_params.items():
            if not key:   # ✅ key가 None이면 스킵
                continue            

            field = key.split("__")[0]
            field_value = str(row.get(field, "")).strip()  # ✅ 공백 제거
            mode = match_mode.get(field, "partial")  # 기본은 부분 일치

            # 날짜 비교 (__gte, __lte)
            if "__gte" in key or "__lte" in key:
                try:
                    field_date = datetime.strptime(field_value, "%Y-%m-%d")
                    search_date = datetime.strptime(value, "%Y-%m-%d")
                except ValueError:
                    match = False
                    break

                if "__gte" in key and field_date < search_date:
                    match = False
                    break
                if "__lte" in key and field_date > search_date:
                    match = False
                    break
                
            else:
                fv = field_value.lower()
                vv = value.strip().lower()

                if mode == "exact":
                    if fv != vv:
                        match = False
                        break
                elif mode == "partial":
                    if vv not in fv:
                        match = False
                        break
                else:  # 잘못된 옵션 → exact 처리
                    if fv != vv:
                        match = False
                        break

        if match:
            results.append(row)

    return results



# =====================================================================
# ✅ 시트 데이터 검색
# =====================================================================
def find_all_members_from_sheet(sheet_name: str, field: str, value: str) -> List[Dict]:
    results = []
    rows = get_rows_from_sheet(sheet_name)

    for row in rows:
        if str(row.get(field, "")).strip().upper() == value.upper():
            results.append(row)

    return results




# ---------------------------------------------------------
# 2. 자연어 → 조건 변환
# ---------------------------------------------------------
def parse_natural_query(query: str):
    conditions = {}
    today = datetime.today()

    if re.fullmatch(r"[가-힣]{2,4}", query):
        conditions["회원명"] = query
    if re.fullmatch(r"\d{3}-\d{3,4}-\d{4}", query):
        conditions["휴대폰번호"] = query
    if re.fullmatch(r"\d{5,}", query):
        conditions["회원번호"] = query

    if "오늘" in query:
        conditions["가입일"] = today.strftime("%Y-%m-%d")
    if "어제" in query:
        yesterday = today - timedelta(days=1)
        conditions["가입일"] = yesterday.strftime("%Y-%m-%d")
    if "이번 달" in query:
        first_day = today.replace(day=1)
        last_day = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        conditions["가입일__gte"] = first_day.strftime("%Y-%m-%d")
        conditions["가입일__lte"] = last_day.strftime("%Y-%m-%d")
    if "지난 달" in query:
        last_month = today.month - 1 or 12
        year = today.year if today.month > 1 else today.year - 1
        first_day = datetime(year, last_month, 1)
        last_day = datetime(year, last_month, calendar.monthrange(year, last_month)[1])
        conditions["가입일__gte"] = first_day.strftime("%Y-%m-%d")
        conditions["가입일__lte"] = last_day.strftime("%Y-%m-%d")
    if "올해" in query:
        first_day = datetime(today.year, 1, 1)
        last_day = datetime(today.year, 12, 31)
        conditions["가입일__gte"] = first_day.strftime("%Y-%m-%d")
        conditions["가입일__lte"] = last_day.strftime("%Y-%m-%d")

    match = re.search(r"최근\s*(\d+)\s*일", query)
    if match:
        days = int(match.group(1))
        start_date = today - timedelta(days=days)
        conditions["가입일__gte"] = start_date.strftime("%Y-%m-%d")
        conditions["가입일__lte"] = today.strftime("%Y-%m-%d")

    match = re.search(r"최근\s*(\d+)\s*개월", query)
    if match:
        months = int(match.group(1))
        year = today.year
        month = today.month - months
        while month <= 0:
            month += 12
            year -= 1
        start_date = datetime(year, month, 1)
        conditions["가입일__gte"] = start_date.strftime("%Y-%m-%d")
        conditions["가입일__lte"] = today.strftime("%Y-%m-%d")

    match = re.search(r"최근\s*(\d+)\s*년", query)
    if match:
        years = int(match.group(1))
        start_date = today.replace(year=today.year - years)
        conditions["가입일__gte"] = start_date.strftime("%Y-%m-%d")
        conditions["가입일__lte"] = today.strftime("%Y-%m-%d")

    date_pattern = r"(\d{4}-\d{2}-\d{2})"
    match = re.search(r"(가입일|생년월일).*" + date_pattern + r".*이후", query)
    if match:
        field, date_val = match.group(1), match.group(2)
        conditions[f"{field}__gte"] = date_val
    match = re.search(r"(가입일|생년월일).*" + date_pattern + r".*이전", query)
    if match:
        field, date_val = match.group(1), match.group(2)
        conditions[f"{field}__lte"] = date_val
    match = re.search(r"(가입일|생년월일).*" + date_pattern, query)
    if match and not any(k.startswith(match.group(1)) for k in conditions):
        field, date_val = match.group(1), match.group(2)
        conditions[field] = date_val

    return {k: v for k, v in conditions.items() if k}



# =====================================================================
# ✅ 자연어 검색 (특수 규칙 + fallback)
# =====================================================================
def searchMemberByNaturalText(query: str):
    """
    자연어 기반 회원 검색
    - '코드a' 또는 '코드 a' 입력 시 → DB 시트 코드 필드에서 A 검색
    - '코드 b', '코드 c' 등도 동일 적용
    - 그 외 → fallback 자연어 검색 실행
    """

    query = query.strip().lower()
    logger.info(f"searchMemberByNaturalText called with query='{query}'")

    # ✅ "코드a" 또는 "코드 a"
    if query in ["코드a", "코드 a"]:
        logger.info("→ 특수 규칙 매칭: 코드=A")
        return find_all_members_from_sheet("DB", field="코드", value="A")

    # ✅ "코드 + 알파벳" 패턴
    if query.startswith("코드"):
        code_value = query.replace("코드", "").strip().upper()
        if code_value:
            logger.info(f"→ 코드 패턴 매칭: 코드={code_value}")
            return find_all_members_from_sheet("DB", field="코드", value=code_value)

    # ✅ fallback 경로
    conditions = fallback_natural_search(query)
    logger.info(f"→ fallback 경로 실행, conditions={conditions}")
    return search_members(get_gsheet_data(), conditions)



# ---------------------------------------------------------
# 3. 검색 실행 (구글시트 데이터 필터링)
# ---------------------------------------------------------
def search_member(query: str) -> Dict:
    members_data = get_gsheet_data()
    normalized = normalize_query(query)
    conditions = parse_natural_query(normalized)

    results = []
    for row in members_data:
        match = True
        for key, value in conditions.items():
            field = key.replace("__gte", "").replace("__lte", "")
            field_value = row.get(field, "")

            # ✅ 날짜 비교
            if "__gte" in key or "__lte" in key:
                try:
                    field_date = datetime.strptime(str(field_value), "%Y-%m-%d")
                    search_date = datetime.strptime(value, "%Y-%m-%d")
                except ValueError:
                    match = False
                    break

                if "__gte" in key and field_date < search_date:
                    match = False
                    break
                if "__lte" in key and field_date > search_date:
                    match = False
                    break

            else:
                # ✅ 일반 비교 (대소문자 무시, 코드/회원번호는 exact)
                fv = str(field_value).strip().lower()
                vv = value.strip().lower()
                if field in ["코드", "회원번호"]:
                    if fv != vv:
                        match = False
                        break
                else:
                    if vv not in fv:  # 부분 일치 허용
                        match = False
                        break

        if match:
            results.append(row)

    return {
        "original": query,
        "normalized": normalized,
        "conditions": conditions,
        "results": results
    }



# ==============================
# 회원명 텍스트 탐색 (보정용)
# ==============================
def find_member_in_text(text: str) -> str | None:
    """
    입력 문장에서 DB 시트의 회원명을 탐색하여 반환
    - 여러 명이 매칭되면 긴 이름 우선 반환
    - 없으면 None
    """
    if not text:
        return None

    sheet = get_member_sheet()
    member_names = sheet.col_values(1)[1:]  # 첫 행은 헤더 제외

    # 긴 이름부터 매칭되도록 정렬 (예: '김철수' > '김')
    member_names = sorted([n.strip() for n in member_names if n], key=len, reverse=True)

    for name in member_names:
        if name in text:
            return name
    return None


















# ======================================================================================
# utils_memo
# ======================================================================================

# 📌 예시 데이터 (실제 환경에서는 API 결과로 대체)
def get_memo_results(query):
    return [
        {"날짜": "2025-08-27", "내용": "오늘 오후에 비가 온다 했는데 비는 오지 않고 날은 무덥습니다", "회원명": "이태수", "종류": "개인일지"},
        {"날짜": "2025-08-26", "내용": "오늘은 포항으로 후원을 가고 있습니다. 하늘에 구름이 많고 오후에는 비가 온다고 합니다", "회원명": "이태수", "종류": "개인일지"},
        {"날짜": "2025-08-10", "내용": "오늘은 비가 오지 않네요", "회원명": "이판사", "종류": "개인일지"},
        {"날짜": "2025-08-04", "내용": "이경훈을 상담했습니다. 비도 많이 옵니다", "회원명": "이태수", "종류": "상담일지"},
        {"날짜": "2025-08-26", "내용": "오늘 하늘에 구름이 많이 꼈고 저녁에 비가 온다고 하는데 확실하지 않습니다", "회원명": "이태수", "종류": "활동일지"},
    ]


# 📌 결과 포맷터 (개인일지 / 상담일지 / 활동일지 블록 구분)
def format_memo_results(results):
    """
    검색된 메모 결과를 정리해서 문자열 블록과 카테고리별 리스트로 반환
    - 날짜는 YYYY-MM-DD 형식으로 출력
    - 정렬은 하루 단위 최신순
    - 출력 순서: 활동일지 → 상담일지 → 개인일지
    - 출력 형식: · (YYYY-MM-DD, 회원명) 내용
    """
    # ✅ 하루 단위 최신순 정렬
    try:
        results.sort(
            key=lambda r: datetime.strptime(str(r.get("날짜", "1900-01-01")).split()[0], "%Y-%m-%d"),
            reverse=True
        )
    except Exception:
        pass

    personal, counsel, activity = [], [], []

    for r in results:
        date = str(r.get("날짜") or "").split()[0]
        content = r.get("내용") or ""
        member = r.get("회원명") or ""
        mode = r.get("일지종류") or r.get("종류")

        if date and member:
            line = f"· ({date}, {member}) {content}"
        elif date:
            line = f"· ({date}) {content}"
        elif member:
            line = f"· ({member}) {content}"
        else:
            line = f"· {content}"

        if mode == "개인일지":
            personal.append(line)
        elif mode == "상담일지":
            counsel.append(line)
        elif mode == "활동일지":
            activity.append(line)

    output_text = "🔎 검색 결과\n\n"
    if activity:
        output_text += "🗂 활동일지\n" + "\n".join(activity) + "\n\n"
    if counsel:
        output_text += "📂 상담일지\n" + "\n".join(counsel) + "\n\n"
    if personal:
        output_text += "📒 개인일지\n" + "\n".join(personal) + "\n\n"

    # ✅ 항상 text 포함할 변수 생성
    human_readable_text = output_text.strip()

    return {
        "text": human_readable_text,   # 최상위 전체 블록
        "lists": {
            "활동일지": activity,
            "상담일지": counsel,
            "개인일지": personal,
            "text": human_readable_text  # ✅ lists 안에도 text 포함
        }
    }








def filter_results_by_member(results, member_name):
    """
    검색 결과(results) 중 특정 회원명(member_name)만 필터링
    """
    if not member_name:
        return results
    return [r for r in results if r.get("회원명") == member_name]








# 로거 설정
logger = logging.getLogger("utils_memo")
logger.setLevel(logging.DEBUG)
if not logger.handlers:  # 중복 등록 방지
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)



def handle_search_memo(data: dict):
    """
    searchMemo와 searchMemoFromText 자동 분기 처리 + 로깅 (동기 버전)
    - 자연어 입력 → call_searchMemoFromText 후 keywords 등 JSON 구조로 맞춤
    - keywords 없는 경우 → 자연어로 변환 후 동일 처리
    - keywords 있는 경우 → searchMemo 직접 호출
    """
    # 1) 자연어 요청 (text 필드가 있는 경우)
    if "text" in data:
        query = data["text"].strip()
        logger.info(f"[FromText-Direct] text 필드 감지 → searchMemoFromText 실행 | query='{query}'")

        res = call_searchMemoFromText({"text": query})

        # ✅ keywords 보정
        if isinstance(res, dict):
            if "검색어" in res and isinstance(res["검색어"], str):
                res["keywords"] = res["검색어"].strip().split()
            elif "keywords" not in res:
                res["keywords"] = []

            # ✅ 일지종류 & 회원명 보정
            res["일지종류"] = res.get("일지종류", "전체")
            res["회원명"] = res.get("회원명", "전체")

        return res

    # 2) keywords가 없는 경우 → 자연어 변환
    if not data.get("keywords"):
        mode = data.get("mode", "전체")
        search_mode_text = "동시" if data.get("search_mode") == "동시검색" else ""
        date_text = ""
        if data.get("start_date") and data.get("end_date"):
            date_text = f"{data['start_date']}부터 {data['end_date']}까지"

        query = f"{mode}일지 검색 {search_mode_text} {date_text}".strip()
        logger.info(f"[FromText-Converted] keywords 없음 → query 변환 후 searchMemoFromText 실행 | query='{query}'")

        res = call_searchMemoFromText({"text": query})

        # ✅ keywords 보정
        if isinstance(res, dict):
            if "검색어" in res and isinstance(res["검색어"], str):
                res["keywords"] = res["검색어"].strip().split()
            elif "keywords" not in res:
                res["keywords"] = []

            # ✅ 일지종류 & 회원명 보정
            res["일지종류"] = res.get("일지종류", "전체")
            res["회원명"] = res.get("회원명", "전체")

        return res

    # 3) 정상 content 기반 요청 → searchMemo 실행
    logger.info(f"[Content-Mode] keywords 감지 → searchMemo 실행 | keywords={data.get('keywords')}, mode={data.get('mode')}")
    return call_searchMemo(data)














# ======================================================================================
# plugin_client
# ======================================================================================

# ✅ 환경변수에서 API URL 읽기
MEMBERSLIST_API_URL = os.getenv("MEMBERSLIST_API_URL")

if not MEMBERSLIST_API_URL:
    raise RuntimeError("❌ 환경변수 MEMBERSLIST_API_URL 이 설정되지 않았습니다. .env 파일을 확인하세요.")


def call_searchMemo(payload: dict):
    """
    searchMemo API 호출 (키워드 기반 검색)
    """
    url = f"{MEMBERSLIST_API_URL.rstrip('/')}/search_memo"
    try:
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        return r.json().get("results", [])
    except requests.RequestException as e:
        raise RuntimeError(f"❌ call_searchMemo 요청 실패: {e}")


def call_searchMemoFromText(payload: dict):
    """
    searchMemoFromText API 호출 (자연어 검색)
    """
    url = f"{MEMBERSLIST_API_URL.rstrip('/')}/search_memo"
    try:
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        return r.json().get("results", [])
    except requests.RequestException as e:
        raise RuntimeError(f"❌ call_searchMemoFromText 요청 실패: {e}")

















# ======================================================================================
# parser_query_member
# ======================================================================================

# --------------------------------------------------
# 📌 입력값 → 필드 자동 판별
# --------------------------------------------------
def infer_member_field(value: str) -> str:
    """
    입력값으로부터 필드명을 추론
    - 010 시작 → 휴대폰번호
    - 숫자만 → 회원번호
    - 그 외 → 회원명
    """
    if not value:
        return "회원명"

    v = value.strip()

    # 휴대폰번호
    if re.match(r"^01[016789]-?\d{3,4}-?\d{4}$", v):
        return "휴대폰번호"

    # 회원번호 (숫자 4~10자리)
    if re.match(r"^\d{4,10}$", v):
        return "회원번호"

    # 기본은 회원명
    return "회원명"


# --------------------------------------------------
# 📌 자연어 → 조건 추출
# --------------------------------------------------
def parse_natural_query_multi(text: str):
    """
    자연어에서 여러 (필드, 키워드) 추출
    - "코드 a 계보도 장천수" → [("코드","A"),("계보도","장천수")]
    - "회원명 이태수" → [("회원명","이태수")]
    - "이태수" → [("회원명","이태수")]
    - "회원번호 22366" → [("회원번호","22366")]
    - "22366" → [("회원번호","22366")]
    - "휴대폰번호 010-1234-5678" → [("휴대폰번호","010-1234-5678")]
    - "010-1234-5678" → [("휴대폰번호","010-1234-5678")]
    """
    if not text:
        return []

    valid_fields = [
        "회원명", "회원번호", "휴대폰번호", "특수번호", "코드", "계보도", "분류",
        "가입일자", "생년월일", "통신사", "친밀도", "근무처", "소개한분",
        "카드사", "카드주인", "카드번호", "유효기간", "카드생년월일",
        "회원단계", "연령/성별", "직업", "가족관계",
        "니즈", "애용제품", "콘텐츠", "습관챌린지",
        "비즈니스시스템", "GLC프로젝트", "리더님"
    ]

    tokens = text.strip().split()
    results = []
    i = 0
    while i < len(tokens):
        token = tokens[i]

        # ✅ case1: 명시적 필드 + 값
        if token in valid_fields and i + 1 < len(tokens):
            keyword = tokens[i + 1]

            # 코드 값은 항상 대문자로 통일
            if token == "코드":
                keyword = keyword.upper()

            results.append((token, keyword))
            i += 2
            continue

        # ✅ case2: 단일 값만 들어온 경우
        if len(tokens) == 1:
            # 휴대폰번호 판별
            if token.startswith("010"):
                results.append(("휴대폰번호", token))
            # 숫자 → 회원번호
            elif token.isdigit():
                results.append(("회원번호", token))
            # 한글 이름 추정
            elif 2 <= len(token) <= 10 and all("가" <= ch <= "힣" for ch in token):
                results.append(("회원명", token))
            else:
                # fallback → infer_member_field 사용
                field = infer_member_field(token)
                results.append((field, token))
            i += 1
            continue

        i += 1

    return results


























def run_intent_func(func, query=None, options=None, **extra_kwargs):
    """
    함수 시그니처를 검사해 안전하게 실행하는 공통 유틸
    - 인자 없음  → func()
    - 인자 1개   → func(query)
    - 인자 2개   → func(query, options)
    - *args/**kwargs 있으면 → query, options 전달 + extra_kwargs 병합
    """
    sig = inspect.signature(func)
    params = sig.parameters

    # 가변 인자 지원 여부 확인
    has_var_positional = any(
        p.kind == inspect.Parameter.VAR_POSITIONAL for p in params.values()
    )
    has_var_keyword = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
    )

    param_count = len(params)

    if param_count == 0:
        return func()
    elif param_count == 1 and not has_var_positional and not has_var_keyword:
        return func(query)
    elif param_count >= 2 and not (has_var_positional or has_var_keyword):
        return func(query, options)
    else:
        # *args / **kwargs 지원 함수라면 → 최대한 풍부하게 전달
        return func(query, options, **extra_kwargs)










# --------------------------------------------------
# GPT Vision: 이미지 → 주문 JSON
# --------------------------------------------------
# ===============================================
# ✅ GPT Vision 기반 이미지 파서
# ===============================================
def extract_order_from_uploaded_image(image_bytes):
    """
    주문서 이미지에서 JSON 구조의 주문 데이터를 추출합니다.
    """
    import os
    print("📌 [DEBUG] extract_order_from_uploaded_image 함수 호출됨")  # ✅ 디버깅 로그 추가

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_API_URL = os.getenv("OPENAI_API_URL")

    print(f"📌 [DEBUG] OPENAI_API_KEY 설정됨? {bool(OPENAI_API_KEY)}")
    print(f"📌 [DEBUG] OPENAI_API_URL: {OPENAI_API_URL}")

    if not OPENAI_API_KEY or not OPENAI_API_URL:
        return {
            "error": "❌ OPENAI_API_KEY 또는 OPENAI_API_URL 환경변수가 설정되지 않았습니다."
        }

    image_base64 = base64.b64encode(image_bytes.getvalue()).decode("utf-8")
    print(f"📌 [DEBUG] base64 변환 완료, 길이={len(image_base64)}")

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

    try:
        print(f"📌 [DEBUG] OpenAI API 호출 시작 → {OPENAI_API_URL}")
        response = requests.post(OPENAI_API_URL, headers=headers, json=payload)
        print(f"📌 [DEBUG] 응답 코드: {response.status_code}")
        response.raise_for_status()
        result_text = response.json()["choices"][0]["message"]["content"]
        print(f"📌 [DEBUG] 응답 내용: {result_text[:200]}...")  # 앞 200자만 출력
    except Exception as e:
        print(f"❌ [DEBUG] OpenAI API 호출 실패: {str(e)}")
        return {"error": f"OpenAI API 호출 실패: {str(e)}"}

    # ✅ 코드블록 제거
    clean_text = re.sub(r"```(?:json)?(.*?)```", r"\1", result_text, flags=re.DOTALL).strip()
    print(f"📌 [DEBUG] 코드블록 제거 후 텍스트: {clean_text[:200]}...")

    try:
        order_data = json.loads(clean_text)
        if not isinstance(order_data, dict) or "orders" not in order_data:
            print("❌ [DEBUG] orders 필드 없음")
            return {"error": "orders 필드가 없습니다", "raw_text": result_text}
        print("✅ [DEBUG] JSON 파싱 성공")
        return order_data
    except json.JSONDecodeError:
        print("❌ [DEBUG] JSON 파싱 실패")
        return {"error": "JSON 파싱 실패", "raw_text": result_text}




# --------------------------------------------------
# GPT Chat: 자연어 → 주문 JSON
# --------------------------------------------------
def parse_order_from_text(text: str):
    """자연어 주문 문장을 OpenAI Chat API에 보내 JSON 추출"""
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "자연어 주문 문장을 JSON으로 변환해 주세요."},
            {"role": "user", "content": text}
        ],
        "temperature": 0.0
    }

    resp = requests.post(OPENAI_API_URL, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()








def normalize_request_data():
    """
    요청 데이터를 표준화:
    - str → {"query": str}
    - dict → 그대로
    - 그 외 → {}
    g.query 에 저장 후 반환
    """
    raw = getattr(g, "query", None) or request.get_json(silent=True)

    if isinstance(raw, str):
        data = {"query": raw}
    elif isinstance(raw, dict):
        data = raw
    else:
        data = {}

    g.query = data
    return data






# utils/utils.py
def get_openai_api_key():
    from app import OPENAI_API_KEY
    return OPENAI_API_KEY
