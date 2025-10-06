# =================================================
# 표준 라이브러리
# =================================================
import os
import re
import json
import traceback
import unicodedata
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# =================================================
# 외부 라이브러리
# =================================================
import requests
import gspread
from flask import (
    Flask, request, jsonify, Response, g, session, send_from_directory
)
from flask_cors import CORS
from gspread.exceptions import WorksheetNotFound, APIError

# =================================================
# 프로젝트: config
# =================================================
from config import (
    MEMBERSLIST_API_URL,
    SHEET_KEY,
    GOOGLE_SHEET_TITLE,
)

# =================================================
# 프로젝트: utils
# =================================================
from utils import (
    # 날짜/시간
    now_kst, process_order_date, parse_dt,

    # 문자열 정리
    clean_tail_command, clean_value_expression, clean_content,
    remove_spaces, build_member_query,

    # 시트 접근
    get_sheet, get_worksheet, get_rows_from_sheet,
    get_member_sheet, get_product_order_sheet,
    get_counseling_sheet, get_personal_memo_sheet,
    get_activity_log_sheet, get_commission_sheet,
    safe_update_cell, delete_row, append_row,

    # 검색
    find_all_members_from_sheet, fallback_natural_search,
    find_member_in_text, is_match, match_condition,

    # 주문/텍스트 파싱
    extract_order_from_uploaded_image, parse_order_from_text,
)


from utils.sheets import get_order_sheet





# =================================================
# 프로젝트: parser
# =================================================
# ======================================================================================
# parse_intent
# ======================================================================================
# ======================================================================================
# field_map
# ======================================================================================
# ======================================================================================
# ✅ 필드 동의어 매핑
# ======================================================================================
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



# ======================================================================================
# intent 규칙 정의
# ======================================================================================

INTENT_RULES = {
    # 회원 관련
    ("회원", "검색"): "",
    ("회원", "조회"): "search_member",   # ✅ 조회도 검색과 동일 처리
    ("회원", "등록"): "register_member",
    ("회원", "추가"): "register_member",
    ("회원", "수정"): "update_member",

    ("회원", "삭제"): "delete_member",
    ("회원", "탈퇴"): "delete_member",
    ("코드", "검색"): "search_by_code_logic",

    # ✅ 회원 선택 관련 추가
    ("전체정보",): "member_select",
    ("상세정보",): "member_select",
    ("상세",): "member_select",
    ("종료",): "member_select",
    ("끝",): "member_select",


    # 메모/일지 관련
    ("상담일지", "저장"): "memo_save_auto_func",
    ("메모", "저장"): "memo_save_auto_func",
    ("개인일지", "저장"): "memo_save_auto_func",
    ("활동일지", "저장"): "memo_save_auto_func",

    ("일지", "저장"): "memo_add",
    ("상담일지", "추가"): "add_counseling",
    ("일지", "검색"): "memo_search",
    ("일지", "조회"): "memo_find",
    ("검색", "자연어"): "search_memo_from_text",
    ("일지", "자동"): "memo_find_auto",

    # 메모 검색
    ("개인일지", "검색"): "search_memo_func",
    ("상담일지", "검색"): "search_memo_func",
    ("활동일지", "검색"): "search_memo_func",
    ("전체메모", "검색"): "search_memo_func",
    ("메모", "검색"): "search_memo_func",

 
    ("상담일지",): "add_counseling",


    # 주문 관련
    ("주문", "자동"): "order_auto",
    ("주문", "업로드"): "order_upload",
    ("주문", "자연어"): "order_nl",
    ("주문", "저장"): "save_order_proxy",
    ("제품", "주문"): "handle_product_order",
    ("주문",): "handle_product_order",
    ("카드", "주문"): "handle_product_order",



    # 후원수당 관련
    ("수당", "찾기"): "commission_find",
    ("수당", "자동"): "commission_find_auto",
    ("수당", "자연어"): "search_commission_by_nl",

    ("회원", "저장"): "save_member",
}




def guess_intent(query: str) -> str:
    query = (query or "").strip()
    import re

    # ✅ "강소희 전체정보", "강소희 상세", "강소희 info"
    if re.fullmatch(r"[가-힣]{2,4}\s*(전체정보|상세|info)", query):
        return "member_select"

    # ✅ "전체정보", "상세", "info" 단독 입력
    if query in ["전체정보", "상세", "info"]:
        return "member_select"

    # ✅ 이름만 입력 (2~4글자 한글) → 회원 검색
    if re.fullmatch(r"[가-힣]{2,4}", query):
        return "search_member"

    if query.endswith("회원등록") or query.endswith("회원 등록"):
        return "register_member"

    
    # ex) "홍길동 주소 수정 대구시" 같은 구조에만 반응
    if re.search(r"[가-힣]{2,4}\s+.*(수정|변경|업데이트)", query) and "회원" in query:
        return "update_member"

    
    if "삭제" in query and ("회원" in query or re.match(r"^[가-힣]{2,4}\s+삭제", query)):
        parts = query.split()
        if len(parts) >= 3:
            return "delete_member_field_nl_func"
        elif len(parts) >= 2:
            return "delete_member"
        return "delete_member"

    


    # ✅ 메모 저장 intent
    if any(kw in query for kw in ["개인일지 저장", "상담일지 저장", "활동일지 저장", "메모 저장"]):
        return "memo_add"

    # ✅ 상담일지 추가 (특수 케이스)
    if "상담" in query and "추가" in query:
        return "add_counseling"

    # ✅ 메모 검색 intent
    if any(kw in query for kw in ["메모 검색", "상담일지 검색", "개인일지 검색", "활동일지 검색"]):
        return "memo_search"

    # ✅ 메모 검색 intent (검색 토큰이 전처리에서 지워진 경우까지 보강)
    if any(query.startswith(prefix) for prefix in ["개인일지", "상담일지", "활동일지"]) \
    and not query.endswith("저장"):
        return "memo_search"


    # 🔹 전체메모 검색 케이스 추가 (띄어쓰기 포함/미포함 대응)
    normalized = query.replace(" ", "")
    if normalized.startswith("전체메모") and "검색" in query:
        return "memo_search"

    # ✅ 기존 intent 규칙 검사 (INTENT_RULES 기반)
    for keywords, intent in INTENT_RULES.items():
        if all(kw in query for kw in keywords):
            return intent

    # fallback
    return "unknown"







# -------------------------------
# 전처리 함수
# -------------------------------

DIARY_TYPES = ["개인일지", "상담일지", "활동일지"]

def preprocess_user_input(user_input: str) -> dict:
    """
    사용자 입력 전처리
    - 회원명, 일지종류, 액션(검색/저장/수정) 추출
    - 불필요한 토큰 제거 후 query 재구성
    - 옵션(full_list 등) 감지
    """
    import re

    member_name = None
    diary_type = None
    action = None
    keyword = None
    options = {}

    # 1. 회원명 추출 (2~4자 한글 이름 감지)
    m = re.fullmatch(r"[가-힣]{2,4}", user_input.strip())
    if m:
        member_name = m.group(0)

    # 2. 일지 종류 추출
    for dtype in DIARY_TYPES:
        if dtype in user_input:
            diary_type = dtype
            break

    # 3. 동작(action) 추출
    if "검색" in user_input:
        action = "검색"
    elif "저장" in user_input:
        action = "저장"
    elif "수정" in user_input:
        action = "수정"

    # 4. 옵션 파싱 ("전체", "전체목록", 숫자 1 → 전체정보 요청)
    if ("전체목록" in user_input 
        or "전체" in user_input 
        or user_input.strip() == "1"):
        options["full_list"] = True

    # 5. 검색 키워드 추출
    exclude_tokens = filter(None, [member_name, diary_type, action, "전체목록", "전체"])
    keyword_tokens = [word for word in user_input.split() if word not in exclude_tokens]
    keyword = " ".join(keyword_tokens).strip()

    # 6. query 재구성
    query_parts = []
    if member_name:
        query_parts.append(member_name)
    if diary_type:
        query_parts.append(diary_type)
    if action:
        query_parts.append(action)
    if keyword:
        query_parts.append(keyword)

    final_query = " ".join(query_parts)

    return {
        "query": final_query,
        "options": options
    }





















































# ======================================================================================
# parser_member
# ======================================================================================
# ======================================================================================
# ✅ 값 추출 보조 함수
# ======================================================================================
def extract_value(raw_text: str) -> str:
    cleaned = raw_text.replace("로 정확히 수정해줘", "") \
                      .replace("정확히 수정해줘", "") \
                      .replace("수정해줘", "") \
                      .strip()
    return cleaned

def parse_field_value(field: str, raw_text: str) -> str:
    if field in ["주소", "메모"]:
        return raw_text.strip()
    return extract_value(raw_text)

def extract_phone(text: str) -> Optional[str]:
    match = re.search(r'01[016789]-?\d{3,4}-?\d{4}', text)
    if match:
        number = re.sub(r'[^0-9]', '', match.group())
        return f"{number[:3]}-{number[3:7]}-{number[7:]}"
    return None

def extract_member_number(text: str) -> Optional[str]:
    match = re.search(r'\b\d{7,8}\b', text)
    return match.group() if match else None

def extract_password(text: str) -> Optional[str]:
    match = re.search(r"특수번호(?:를|는)?\s*([^\s\"']{6,20})", text)
    return match.group(1) if match else None

def extract_referrer(text: str) -> Optional[str]:
    match = re.search(r"(소개한분|소개자|추천인)[은는을이]?\s*([가-힣]{2,10})", text)
    if match:
        이름 = match.group(2)
        return 이름[:-1] if 이름.endswith("로") else 이름
    return None

# ======================================================================================
# ✅ 등록 파서
# ======================================================================================

from typing import Optional, Tuple

def parse_registration(text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    문장에서 (회원명, 회원번호, 휴대폰번호)만 추출
    나머지 필드(계보도, 주소 등)는 무시
    """
    text = text.replace("\n", " ").replace("\r", " ").replace("\xa0", " ").strip()
    name = number = phone = ""

    # ✅ 휴대폰번호 추출
    phone_match = re.search(r"010[-]?\d{4}[-]?\d{4}", text)
    if phone_match:
        phone = phone_match.group(0)

    # ✅ 회원명 + 회원번호 추출
    match = re.search(r"(?:회원등록\s*)?([가-힣]{2,10})\s*회원번호\s*(\d+)", text)
    if match:
        name, number = match.group(1), re.sub(r"[^\d]", "", match.group(2))
    else:
        match = re.search(r"([가-힣]{2,10})\s+(\d{6,})", text)
        if match and "회원등록" in text:
            name, number = match.group(1), re.sub(r"[^\d]", "", match.group(2))
        else:
            match = re.search(r"^([가-힣]{2,10})\s*회원등록$", text)
            if match:
                name = match.group(1)

    # ✅ 회원명만 있는 경우
    if not name:
        korean_words = re.findall(r"[가-힣]{2,}", text)
        if korean_words:
            name = korean_words[0]

    return name or None, number or None, phone or None

from utils import clean_tail_command, clean_value_expression




# ======================================================================================
# ✅ 수정 파서
# ======================================================================================
def infer_field_from_value(value: str) -> str | None:
    """
    입력된 값이 어떤 필드에 해당하는지 추론
    예:
      - "010-1234-5678" → "휴대폰번호"
      - "12345678" → "회원번호"
      - "서울시 ..." → "주소"
      - "좌측" / "우측" → "계보도"
    """
    if not value:
        return None

    # 휴대폰번호
    if re.match(r"^01[016789]-?\d{3,4}-?\d{4}$", value):
        return "휴대폰번호"

    # 회원번호 (010 아닌 순수 숫자)
    if re.match(r"^\d{4,10}$", value):
        return "회원번호"

    # 주소 (간단히 '시', '도', '구', '동' 포함 여부로 판정)
    if any(kw in value for kw in ["시", "도", "구", "동", "읍", "면", "리"]):
        return "주소"

    # 계보도
    if value in ["좌측", "우측"]:
        return "계보도"

    return None






def parse_request_and_update(text: str) -> Optional[Dict[str, str]]:
    """
    ✅ 자연어 요청문에서 회원정보 수정용 (필드 → 값) 딕셔너리 추출
    - "홍길동 휴대폰번호 010-1111-2222 주소 서울 강남구"
    - "장미 회원번호 12345 특수번호 9999 수정"

    반환 예시:
    { "휴대폰번호": "010-1111-2222", "주소": "서울 강남구" }
    """
    if not text:
        return None

    # 1) 조사/꼬리 명령어 제거
    s = clean_tail_command(text)

    updates = {}

    # 2) 필드 후보 매핑 검사
    for key, aliases in field_map.items():
        for alias in aliases:
            pattern = rf"{alias}\s*([^\s,]+)"
            match = re.search(pattern, s)
            if match:
                raw_value = match.group(1).strip(" ,.")
                value = clean_value_expression(raw_value)
                updates[key] = value
                # 계속해서 다른 필드도 찾기 (break 안 함)
    return updates if updates else None



# ============================================================================================
# 입력된 한국어 문장에서 **필드(계보도/소개한분/코드/분류/리더님 등)**와 값을 추출
# ============================================================================================
# =============================================================================
# ✅ Intent 추론 / 간단 파서
# =============================================================================

# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
def parse_natural_query(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    자연어에서 (필드, 키워드) 추출
    - '회원조회 123456' → ("회원번호", "123456")
    - '이태수 조회' → ("회원명", "이태수")
    - '회원명 강소희' → ("회원명", "강소희")
    - '회원번호 12345' → ("회원번호", "12345")
    - '강소희' → ("회원명", "강소희")
    - '계보도 장천수 우측' → ("계보도", "장천수우측")
    """
    if not text:
        return None, None
    s = text.strip()

    # 1) '회원조회'
    if "회원조회" in s:
        keyword = s.replace("회원조회", "").strip()
        if not keyword:
            return None, None
        if re.fullmatch(r"\d+", keyword):
            return "회원번호", keyword
        return "회원명", keyword

    # 2) '회원명 XXX'
    m = re.match(r"회원명\s+([가-힣a-zA-Z0-9]+)", s)
    if m:
        return "회원명", m.group(1).strip()

    # 3) '회원번호 XXX'
    m = re.match(r"회원번호\s+(\d+)", s)
    if m:
        return "회원번호", m.group(1).strip()

    # 4) 일반 조회/검색/찾아
    if any(k in s for k in ["조회", "검색", "찾아"]):
        m = re.match(r"^(\S+)\s*(조회|검색|찾아)", s)
        if m:
            keyword = m.group(1).strip()
            if re.fullmatch(r"\d+", keyword):
                return "회원번호", keyword
            return "회원명", keyword

    # 5) 계보도/소개한분/코드 등 특정 필드
    m = re.search(r"계보도.*?([가-힣]+)\s*(우측|좌측)", s)
    if m:
        return "계보도", f"{m.group(1)}{m.group(2)}"

    mapping = {
        "계보도": "계보도",
        "소개한분": "소개한분",
        "코드": "코드",
        "분류": "분류",
        "리더님": "리더님",
        "회원번호": "회원번호",
    }
    for field in mapping:
        if field in s:
            mm = re.search(
                rf"{field}\s*(?:은|는|이|가|을|를|이란|이라는|에|으로|로)?\s*(.*)", s
            )
            if mm:
                kw = re.split(r"[,\s\n.]", mm.group(1).strip())[0]
                return field, kw

    # 6) 단어 하나만 입력 → 회원명으로 간주
    if re.fullmatch(r"[가-힣a-zA-Z]+", s):
        return "회원명", s

    return None, None




def parse_korean_phone(text: str) -> str | None:
    """
    한국 휴대폰 번호(010-xxxx-xxxx 형식 등)를 텍스트에서 추출
    """
    pattern = re.compile(r"(01[016789])[-.\s]?(\d{3,4})[-.\s]?(\d{4})")

    match = pattern.search(text)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None



def parse_member_number(text: str) -> str | None:
    """
    회원번호(숫자만)를 텍스트에서 추출
    - 휴대폰 번호(010~)와 구분해서 처리
    """
    # 휴대폰 번호 패턴 제외 후 숫자만 추출
    phone_pattern = re.compile(r"01[016789]\d{7,8}")
    if phone_pattern.search(text):
        return None

    num_pattern = re.compile(r"\b\d{4,10}\b")  # 4~10자리 숫자
    match = num_pattern.search(text)
    if match:
        return match.group(0)
    return None




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






def parse_deletion_request(text: str) -> Dict[str, Optional[List[str]]]:
    """
    삭제 요청 문장에서 회원명과 삭제할 필드 추출
    예:
      - "이태수 주소 삭제" → {"member": "이태수", "fields": ["주소"]}
      - "홍길동 주소, 휴대폰번호 삭제" → {"member": "홍길동", "fields": ["주소", "휴대폰번호"]}
    """
    text = (text or "").strip()
    result: Dict[str, Optional[List[str]]] = {"member": None, "fields": []}

    if not text:
        return result

    tokens = text.split()
    if not tokens:
        return result

    # 첫 단어 = 회원명
    result["member"] = tokens[0]



    # 삭제 키워드
    deletion_keywords = ["삭제", "지움", "제거", "없애줘", "빼줘"]

    # 문장에서 후보 필드 찾기
    for key, mapped in field_map.items():
        if key in text:
            result["fields"].append(mapped)

    # 중복 제거
    result["fields"] = list(dict.fromkeys(result["fields"]))

    return result


# 🔄 호환 레이어 (Tuple 스타일도 필요할 경우)
def parse_deletion_request_compat(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    구버전 호환용: 단일 (회원명, 필드) 튜플 반환
    여러 필드가 들어오면 첫 번째만 반환
    """
    parsed = parse_deletion_request(text)
    member = parsed.get("member")
    fields = parsed.get("fields") or []
    field = fields[0] if fields else None
    return member, field


# 조건 매핑 테이블
CONDITION_PATTERNS = {
    "코드": r"코드\s*([A-Za-z]+)",   # 알파벳 코드 (대소문자 허용)
    "지역": r"(서울|부산|대구|인천|광주|대전|울산|세종)",
    "직업": r"(교사|의사|간호사|학생|자영업|회사원)",
    "성별": r"(남성|여성|남자|여자)",
    "연령대": r"(\d{2})대"            # 예: 20대, 30대
}

def parse_conditions(query: str):
    """
    전처리된 문자열을 조건 딕셔너리로 변환합니다.
    대소문자 구분 없이 매칭하며, 코드 값은 항상 대문자로 통일합니다.
    """
    conditions = {}
    for field, pattern in CONDITION_PATTERNS.items():
        match = re.search(pattern, query, flags=re.IGNORECASE)  # 대소문자 무시
        if match:
            value = match.group(1)
            if field == "코드":
                value = value.upper()  # 코드값은 무조건 대문자로 변환
            conditions[field] = value
    return conditions
















# ======================================================================================
# service_member
# ======================================================================================
# ==============================
# 회원 등록 (Create)
# ==============================
def register_member(name: str, number: str, phone: str) -> bool:
    """
    DB 시트에 새로운 회원을 등록
    예: register_member("홍길동", "123456", "010-1234-5678")
    """
    sheet = get_member_sheet()
    headers = sheet.row_values(1)

    data = {
        "회원명": name,
        "회원번호": number,
        "휴대폰번호": phone,
    }

    # header 순서에 맞춰서 값 넣기
    row = [data.get(h, "") for h in headers]
    sheet.append_row(row, value_input_option="USER_ENTERED")
    return True


# ==============================
# 회원 조회 (Read)
# ==============================
def find_member(name: str):
    """
    DB 시트에서 회원명으로 회원을 조회
    여러 건일 수 있으므로 list 반환
    예: [{"회원명": "홍길동", "회원번호": "123456", "휴대폰번호": "010-1234-5678"}]
    """
    sheet = get_member_sheet()
    rows = sheet.get_all_records()

    result = []
    for row in rows:
        if str(row.get("회원명", "")).strip() == str(name).strip():
            result.append(row)
    return result


# ==============================
# 회원 수정 (Update)
# ==============================
def update_member(name: str, updates: dict) -> bool:
    """
    특정 회원의 여러 필드 값을 수정
    예: update_member("홍길동", {"주소": "부산", "휴대폰번호": "010-0000-0000"})
    """
    sheet = get_member_sheet()
    headers = sheet.row_values(1)
    rows = sheet.get_all_records()

    updated = False
    for i, row in enumerate(rows, start=2):  # 2행부터 데이터 시작
        if str(row.get("회원명", "")).strip() == str(name).strip():
            for field, value in updates.items():
                if field in headers:
                    col_idx = headers.index(field) + 1
                    safe_update_cell(sheet, i, col_idx, value)
                    updated = True
            break
    return updated


# ==============================
# 회원 삭제 (Delete)
# ==============================
def delete_member(name: str) -> bool:
    """
    DB 시트에서 특정 회원 전체 행 삭제
    예: delete_member("홍길동")
    """
    sheet = get_member_sheet()
    rows = sheet.get_all_records()

    for i, row in enumerate(rows, start=2):  # 2행부터 데이터 시작
        if str(row.get("회원명", "")).strip() == str(name).strip():
            sheet.delete_rows(i)
            return True
    return False






import unicodedata
from utils import get_rows_from_sheet

def normalize_text(s) -> str:
    if s is None:
        return ""
    return unicodedata.normalize("NFC", str(s).strip())



def find_member_internal(name: str = "", number: str = "", code: str = "", phone: str = "", special: str = ""):
    """
    DB 시트에서 회원 검색
    """
    rows = get_rows_from_sheet("DB")
    results = []

    # 검색 조건 정규화
    name = normalize_text(name)
    number = normalize_text(number)
    code = normalize_text(code)
    phone = normalize_text(phone)
    special = normalize_text(special)

    for row in rows:
        row_name = normalize_text(row.get("회원명", ""))
        row_number = normalize_text(row.get("회원번호", ""))
        row_code = normalize_text(row.get("코드", ""))
        row_phone = normalize_text(row.get("휴대폰번호", ""))
        row_special = normalize_text(row.get("특수번호", ""))

        if (
            (name and row_name == name) or
            (number and row_number == number) or
            (code and row_code == code) or
            (phone and row_phone == phone) or
            (special and row_special == special)
        ):
            results.append(row)

    return results








def clean_member_data(data: dict) -> dict:
    """
    회원 데이터 전처리 함수 (기본 구현)
    - 문자열이면 strip() 처리
    - None 은 "" 로 변환
    - 불필요한 공백 제거
    """
    if not data:
        return {}

    cleaned = {}
    for k, v in data.items():
        if isinstance(v, str):
            cleaned[k] = v.strip()
        elif v is None:
            cleaned[k] = ""
        else:
            cleaned[k] = v
    return cleaned







def parse_registration_internal(name: str, number: str = "", phone: str = ""):
    sheet = get_member_sheet()
    headers = sheet.row_values(1)
    rows = sheet.get_all_records()

    # ✅ 기존 회원 여부 확인
    for row in rows:
        # ⚠️ 반드시 str()로 감싸야 int → 문자열 변환
        row_name = str(row.get("회원명") or "").strip()
        row_number = str(row.get("회원번호") or "").strip()

        if name == row_name and number and number == row_number:
            return {
                "status": "exists",
                "message": f"{name} ({number})님은 이미 등록된 회원입니다.",
                "data": row
            }

        if number and number == row_number and name != row_name:
            return {
                "status": "error",
                "message": f"⚠️ 회원번호 {number}는 이미 '{row_name}'님에게 등록되어 있습니다."
            }

    # ✅ 신규 등록
    new_row = [""] * len(headers)
    if "회원명" in headers:
        new_row[headers.index("회원명")] = name
    if "회원번호" in headers and number:
        new_row[headers.index("회원번호")] = number
    if "휴대폰번호" in headers and phone:
        new_row[headers.index("휴대폰번호")] = phone

    sheet.insert_row(new_row, 2)
    return {
        "status": "created",
        "message": f"{name} 회원 신규 등록 완료",
        "data": {
            "회원명": name,
            "회원번호": number,
            "휴대폰번호": phone
        }
    }









def delete_member_internal(name: str):
    """
    회원명 기준으로 DB 시트에서 해당 회원 전체 행 삭제
    삭제 전에 "백업" 시트에 해당 회원 정보 저장
    """
    if not name:
        return {"error": "회원명이 필요합니다."}, 400

    sheet = get_member_sheet()
    rows = sheet.get_all_records()
    headers = sheet.row_values(1)

    for i, row in enumerate(rows, start=2):  # 헤더 제외
        if row.get("회원명", "").strip() == name:
            # ✅ 백업 시트 가져오기
            backup_sheet = get_worksheet("백업")

            if not backup_sheet:
                return {"error": "백업 시트를 찾을 수 없습니다. '백업' 시트를 먼저 생성해주세요."}, 500

            # ✅ 백업 저장
            backup_row = [row.get(h, "") for h in headers]
            backup_sheet.insert_row(backup_row, 2)

            # ✅ 원본 삭제
            delete_row(sheet, i)

            return {"message": f"{name}님의 회원 정보가 '백업' 시트에 저장된 후 삭제되었습니다."}, 200

    return {"error": f"{name} 회원을 찾을 수 없습니다."}, 404








def delete_member_field_nl_internal(text: str, fields: list = None):
    """
    회원 필드 삭제 내부 로직 (자연어 기반)
    - '회원명', '회원번호'는 삭제 불가
    - '회원명 + 삭제'는 전체 삭제 방지
    """
    sheet = get_member_sheet()
    rows = sheet.get_all_records()
    headers = sheet.row_values(1)

    # ✅ 회원명 추출
    name = None
    for row in rows:
        if str(row.get("회원명", "")) in text:
            name = row.get("회원명")
            break
    if not name:
        return {"error": "회원명을 찾을 수 없습니다."}, 404

    # ✅ 전체 삭제 방지
    if text.strip().startswith(name) and text.strip().endswith("삭제"):
        return {"error": "⚠️ 회원 전체 삭제는 별도 API(/delete_member)를 사용하세요."}, 400

    # ✅ 삭제 키워드 체크
    delete_keywords = ["삭제", "삭제해줘", "비워", "비워줘", "초기화", "초기화줘", "없애", "없애줘", "지워", "지워줘"]
    parts = split_to_parts(text)
    has_delete_kw = any(remove_spaces(dk) in [remove_spaces(p) for p in parts] for dk in delete_keywords)
    if not has_delete_kw:
        return {"error": "삭제 명령이 포함되어야 합니다."}, 400

    # ✅ 필드 추출
    matched_fields = []
    for alias, canonical in field_map.items():
        if remove_spaces(alias) in [remove_spaces(p) for p in parts]:
            if canonical in headers and canonical not in matched_fields:
                matched_fields.append(canonical)

    if fields:
        for f in fields:
            if f in headers and f not in matched_fields:
                matched_fields.append(f)

    if not matched_fields:
        return {"error": "삭제할 필드를 찾을 수 없습니다."}, 400

    # ✅ 보호 필드 차단
    protected_fields = {"회원명", "회원번호"}
    if any(f in protected_fields for f in matched_fields):
        return {"error": "⚠️ 회원명, 회원번호는 삭제 불가 필드입니다. 수정 API를 사용하세요."}, 400

    # ✅ 대상 행 찾기
    target_row, row_index = None, None
    for i, row in enumerate(rows, start=2):
        if row.get("회원명") == name:
            target_row, row_index = row, i
            break
    if not target_row:
        return {"error": f"{name} 회원을 찾을 수 없습니다."}, 404

    # ✅ 필드 값 삭제
    for field in matched_fields:
        col_index = headers.index(field) + 1
        sheet.update_cell(row_index, col_index, "")

    return {
        "message": f"{name}님의 {', '.join(matched_fields)} 필드가 삭제되었습니다.",
        "deleted_fields": matched_fields
    }, 200




def process_member_query(user_input: str):
    # 1️⃣ 자연어 → 정제된 쿼리
    processed = build_member_query(user_input)
    search_key = processed["query"]

    # 2️⃣ 쿼리 → 조건 딕셔너리
    conditions = parse_conditions(search_key)

    # 3️⃣ Google Sheets 조회
    sheet = get_member_sheet()
    records = sheet.get_all_records()
    results = []

    for row in records:
        match = True
        for field, value in conditions.items():
            cell_value = str(row.get(field, "")).strip()
            if field == "코드":
                cell_value = cell_value.upper()  # 코드값 대문자 통일
            if cell_value != value:
                match = False
                break
        if match:
            results.append(row)

    return {
        "original": user_input,
        "processed": search_key,
        "conditions": conditions,
        "results": results
    }
























# ======================================================================================
# parser_memo
# ======================================================================================
# ======================================================================================
# ✅ 메모 요청 파서
# ======================================================================================
def parse_request_line(text: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    자연어 문장에서 메모 저장 요청 파싱
    예: '이태수 상담일지 저장 오늘은 비가 옵니다'
    반환: (회원명, 시트명, 액션, 내용)
    """
    if not text or not text.strip():
        return None, None, None, None

    s = text.strip()
    m = re.match(
        r"^\s*(\S+)\s*(상담\s*일지|개인\s*일지|활동\s*일지)\s*(저장|기록|입력)\s*(.*)$",
        s,
    )
    if m:
        member, sheet_raw, action, content = m.groups()
        sheet = sheet_raw.replace(" ", "")
        return member, sheet, action, content

    # fallback: 단순 분리
    parts = s.split(maxsplit=3)
    if len(parts) < 3:
        return None, None, None, None

    member, sheet, action = parts[0], parts[1].replace(" ", ""), parts[2]
    content = parts[3] if len(parts) > 3 else ""
    return member, sheet, action, content


# ======================================================================================
# ✅ 메모 파서 + 저장
# ======================================================================================
def parse_memo(text: str) -> dict:
    text = (text or "").strip()
    diary_types = ["상담일지", "개인일지", "활동일지"]

    result = {"회원명": None, "일지종류": None, "내용": None, "keywords": []}

    # ✅ 전체메모 검색 (띄어쓰기 허용)
    normalized = text.replace(" ", "")

    if normalized.startswith("전체메모") and "검색" in text:
        keyword = text.split("검색", 1)[1].strip()
        result.update({
            "회원명": "전체",  
            "일지종류": "전체",
            # 🔽 기존: "홍길동 제품" → ["홍길동 제품"]
            # "홍길동 제품" → ["홍길동", "제품"] 로 분리되도록 수정
            "keywords": keyword.split() if keyword else []
        })
        return result

    


    # ✅ 일반 저장/검색
    for dt in diary_types:
        if dt in text:
            before, after = text.split(dt, 1)
            result["회원명"] = before.strip()
            result["일지종류"] = dt


            if "저장" in after:
                result["내용"] = after.strip()   # ✅ '저장' 토큰 제거하지 않음
         
            elif "검색" in after:
                keyword = after.replace("검색", "").strip()
                result["keywords"] = keyword.split() if keyword else []



            return result

    return result














# ======================================================================================
# service_memo
# ======================================================================================
# ======================================================================================
# ✅ 메모 저장
# ======================================================================================
def save_memo(sheet_name: str, member_name: str, content: str) -> bool:
    """
    상담일지 / 개인일지 / 활동일지 저장
    """
    if not member_name or not content:
        raise ValueError("회원명과 내용은 필수 입력 항목입니다.")

    if sheet_name == "상담일지":
        sheet = get_counseling_sheet()
    elif sheet_name == "개인일지":
        sheet = get_personal_memo_sheet()
    elif sheet_name == "활동일지":
        sheet = get_activity_log_sheet()
    else:
        raise ValueError(f"지원하지 않는 일지 종류: {sheet_name}")

    ts = now_kst().strftime("%Y-%m-%d %H:%M")
    sheet.insert_row([ts, member_name.strip(), content.strip()], index=2)
    return True




# ======================================================================================
# ✅ 기본 검색
# ======================================================================================
def find_memo(keyword: str, sheet_name: str = "상담일지") -> list:
    """
    메모(상담일지/개인일지/활동일지)에서 키워드 검색
    """
    try:
        sheet = get_worksheet(sheet_name)
        if not sheet:
            print(f"[ERROR] ❌ 시트를 가져올 수 없습니다: {sheet_name}")
            return []

        all_records = sheet.get_all_records()
        results = []
        for row in all_records:
            row_text = " ".join(str(v) for v in row.values())
            if keyword in row_text:
                results.append(row)

        print(f"[INFO] ✅ '{sheet_name}' 시트에서 '{keyword}' 검색 결과 {len(results)}건 발견")
        return results
    except Exception as e:
        print(f"[ERROR] find_memo 오류: {e}")
        return []


# ======================================================================================
# ✅ 고급 검색 (날짜 범위 / 여러 키워드)
# ======================================================================================
def search_in_sheet(sheet_name, keywords, search_mode="any",
                    start_date=None, end_date=None, limit=20):
    sheet = get_worksheet(sheet_name)
    rows = sheet.get_all_values()
    if not rows or len(rows[0]) < 3:
        return [], False

    records = rows[1:]
    results = []
    for row in records:
        if len(row) < 3:
            continue

        작성일자, 회원명, 내용 = (row[0] or "").strip(), (row[1] or "").strip(), (row[2] or "").strip()
        작성일_dt = parse_dt(작성일자)
        if 작성일_dt is None:
            continue

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







def normalize_korean(text: str) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFC", text)   # 유니코드 정규화
    t = re.sub(r"\s+", " ", t)               # 연속 공백 정리
    return t.strip().lower()


def keyword_match(content_lower: str, clean_keywords: list, search_mode="any") -> bool:
    if not clean_keywords:
        return False

    normalized_content = normalize_korean(content_lower)
    results = []

    for k in clean_keywords:
        k_norm = normalize_korean(k)
        found = k_norm in normalized_content
        results.append(found)
        print(f"[DEBUG] keyword_match | keyword={k_norm} | "
              f"in_content={found} | content={normalized_content[:50]}...")

    if search_mode == "동시검색":
        return all(results)
    return any(results)





# ======================================================================================
# ✅ 통합 검색 (Core)
# ======================================================================================
























# ======================================================================================
# parse_order
# ======================================================================================

# ===============================================
# ✅ 규칙 기반 자연어 파서
# ===============================================
def parse_order_text(text: str) -> Dict[str, Any]:
    """
    자연어 주문 문장을 intent + query 구조로 변환
    예: "이수민 주문 노니 2개 카드 결제 서울 주소 오늘"
    """
    text = (text or "").strip()
    query: Dict[str, Any] = {}

    # ✅ 회원명
    member = find_member_in_text(text)
    query["회원명"] = member if member else None

    # ✅ 제품명 + 수량 (예: 노니 2개, 홍삼 3박스, 치약 1병)
    prod_match = re.search(r"([\w가-힣]+)\s*(\d+)\s*(개|박스|병|포)?", text)
    if prod_match:
        query["제품명"] = prod_match.group(1)
        query["수량"] = int(prod_match.group(2))
    else:
        query["제품명"] = "제품"
        query["수량"] = 1

    # ✅ 결제방법
    if "카드" in text:
        query["결제방법"] = "카드"
    elif "현금" in text:
        query["결제방법"] = "현금"
    elif "계좌" in text or "이체" in text:
        query["결제방법"] = "계좌이체"
    else:
        query["결제방법"] = "카드"

    # ✅ 배송처
    # "주소: 서울", "배송지: 부산", "서울 주소" 같은 패턴 지원
    address_match = re.search(r"(?:주소|배송지)[:：]?\s*([가-힣0-9\s]+)", text)
    query["배송처"] = address_match.group(1).strip() if address_match else ""

    # ✅ 주문일자 (오늘/내일/어제/2025-09-11)
    query["주문일자"] = process_order_date(text)

    return {
        "intent": "order_auto",
        "query": query
    }


# ===============================================
# ✅ GPT 응답 후처리: 안전하게 주문 리스트 변환
# ===============================================
def ensure_orders_list(parsed: Any) -> List[Dict[str, Any]]:
    """
    Vision/GPT 응답(parsed)을 안전하게 '주문 리스트(list of dict)'로 변환
    """
    if not parsed:
        return []

    # 문자열(JSON)인 경우
    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except Exception:
            return []

    # dict인 경우
    if isinstance(parsed, dict):
        if "orders" in parsed and isinstance(parsed["orders"], list):
            return parsed["orders"]
        if all(isinstance(v, (str, int, float, type(None))) for v in parsed.values()):
            return [parsed]
        return []

    # list인 경우
    if isinstance(parsed, list):
        if all(isinstance(item, dict) for item in parsed):
            return parsed
        return []

    return []


# ────────────────────────────────────────────────
# 규칙 기반 주문 파서
# ────────────────────────────────────────────────
def parse_order_text_rule(text: str) -> dict:
    """
    특정 규칙에 따라 주문 정보 추출
    (정규식 기반)
    """
    if not text:
        return {}

    text = clean_tail_command(text)

    result = {}
    # 숫자만 있는 경우 → 회원번호로 인식
    if re.fullmatch(r"\d{6,}", text):
        result["회원번호"] = text

    # '주문' 키워드 있는 경우 → 주문 처리로 분류
    if "주문" in text:
        result["intent"] = "order"

    return result

















# ======================================================================================
# service_order
# ======================================================================================










# ===============================================
# ✅ 주문 시트 저장
# ===============================================
# -----------------------------
# 주문 저장 함수
# -----------------------------
def handle_order_save(data: dict):
    sheet = get_worksheet("제품주문")
    if not sheet:
        return {"http_status": 500, "status": "error", "message": "제품주문 시트를 찾을 수 없습니다."}

    # ✅ 주문일자 변환
    order_date = process_order_date(data.get("주문일자", ""))
    row = [
        order_date, data.get("회원명", ""), data.get("회원번호", ""), data.get("휴대폰번호", ""),
        data.get("제품명", ""), float(data.get("제품가격", 0)), float(data.get("PV", 0)),
        data.get("결재방법", ""), data.get("주문자_고객명", ""), data.get("주문자_휴대폰번호", ""),
        data.get("배송처", ""), data.get("수령확인", "")
    ]

    values = sheet.get_all_values()

    # ✅ 헤더 없으면 생성
    if not values:
        headers = [
            "주문일자", "회원명", "회원번호", "휴대폰번호",
            "제품명", "제품가격", "PV", "결재방법",
            "주문자_고객명", "주문자_휴대폰번호", "배송처", "수령확인"
        ]
        sheet.append_row(headers)
        values = [headers]

    # ✅ 항상 맨 위(2행)에 삽입
    sheet.insert_row(row, index=2)

    # ✅ 최신 주문(2행) 조회
    latest = sheet.row_values(2)
    headers = values[0]
    latest_order = dict(zip(headers, latest))

    return {
        "http_status": 200,
        "status": "ok",
        "message": "✅ 주문이 새로 저장되었습니다.",
        "latest_order": latest_order
    }





# ===============================================
# ✅ 제품 주문 처리
# ===============================================
def handle_product_order(text: str, member_name: str):
    """
    자연어 문장을 파싱 후 제품 주문을 저장합니다.
    """
    try:
        from parser import parse_order_text
        parsed = parse_order_text(text)
        parsed["회원명"] = member_name
        handle_order_save(parsed)
        return jsonify({"message": f"{member_name}님의 제품주문 저장이 완료되었습니다."})
    except Exception as e:
        return jsonify({"error": f"제품주문 처리 중 오류 발생: {str(e)}"}), 500




# ===============================================
# ✅ 주문 시트 직접 저장
# ===============================================
def save_order_to_sheet(order: dict) -> bool:
    """
    단일 주문 데이터를 '제품주문' 시트에 직접 저장합니다.
    """
    try:
        sheet = get_order_sheet()
        headers = sheet.row_values(1)
        row_data = [order.get(h, "") for h in headers]
        append_row(sheet, row_data)
        return True
    except Exception as e:
        print(f"[ERROR] 주문 저장 중 오류: {e}")
        return False


# ===============================================
# ✅ 주문 조회
# ===============================================
def find_order(member_name: str = "", product: str = "") -> list[dict]:
    """
    주문 시트에서 회원명 또는 제품명으로 조회합니다.
    """
    sheet = get_order_sheet()
    db = sheet.get_all_values()
    if not db or len(db) < 2:
        return []
    headers, rows = db[0], db[1:]
    matched = []
    for row in rows:
        row_dict = dict(zip(headers, row))
        if member_name and row_dict.get("회원명") == member_name.strip():
            matched.append(row_dict)
        elif product and row_dict.get("제품명") == product.strip():
            matched.append(row_dict)
    return matched


# ===============================================
# ✅ 주문 등록
# ===============================================
def register_order(order_data: dict) -> bool:
    """
    주문 데이터를 직접 등록합니다.
    """
    sheet = get_order_sheet()
    headers = sheet.row_values(1)
    row = {h: "" for h in headers}
    for k, v in order_data.items():
        if k in headers:
            row[k] = str(v)
    values = [row.get(h, "") for h in headers]
    sheet.append_row(values)
    return True


# ===============================================
# ✅ 주문 수정
# ===============================================
def update_order(member_name: str, updates: dict) -> bool:
    """
    특정 회원의 주문 정보를 수정합니다.
    """
    sheet = get_order_sheet()
    headers = sheet.row_values(1)
    values = sheet.get_all_values()
    member_col = headers.index("회원명") + 1
    target_row = None
    for i, row in enumerate(values[1:], start=2):
        if len(row) >= member_col and row[member_col - 1] == member_name.strip():
            target_row = i
            break
    if not target_row:
        raise ValueError(f"'{member_name}' 회원의 주문을 찾을 수 없습니다.")
    for field, value in updates.items():
        if field not in headers:
            continue
        col = headers.index(field) + 1
        safe_update_cell(sheet, target_row, col, value, clear_first=True)
    return True


# ===============================================
# ✅ 주문 삭제
# ===============================================
def delete_order(member_name: str) -> bool:
    """
    특정 회원의 주문 레코드를 삭제합니다.
    """
    sheet = get_order_sheet()
    headers = sheet.row_values(1)
    values = sheet.get_all_values()
    member_col = headers.index("회원명") + 1
    target_row = None
    for i, row in enumerate(values[1:], start=2):
        if len(row) >= member_col and row[member_col - 1] == member_name.strip():
            target_row = i
            break
    if not target_row:
        raise ValueError(f"'{member_name}' 회원의 주문을 찾을 수 없습니다.")
    sheet.delete_rows(target_row)
    return True


# ===============================================
# ✅ 주문 삭제 (행 번호 기준)
# ===============================================
def delete_order_by_row(row: int):
    """
    행 번호로 주문 레코드를 삭제합니다.
    """
    delete_row("제품주문", row)


# ===============================================
# ✅ 주문 데이터 정리
# ===============================================
def clean_order_data(order: dict) -> dict:
    """
    주문 dict 데이터를 전처리(clean)합니다.
    """
    if not isinstance(order, dict):
        return {}
    cleaned = {}
    for k, v in order.items():
        if v is None:
            continue
        if isinstance(v, str):
            v = v.strip()
        cleaned[k.strip()] = v
    return cleaned























# ======================================================================================
# parser_commission
# ======================================================================================
# ======================================================================================
# ✅ 날짜 처리 파서
# ======================================================================================
def process_date(raw: Optional[str]) -> str:
    """
    '오늘/어제/내일', YYYY-MM-DD, 2025.8.7 / 2025/08/07 등 → YYYY-MM-DD
    """
    from datetime import timedelta
    try:
        if not raw:
            return now_kst().strftime("%Y-%m-%d")
        s = raw.strip()
        if "오늘" in s:
            return now_kst().strftime("%Y-%m-%d")
        if "어제" in s:
            return (now_kst() - timedelta(days=1)).strftime("%Y-%m-%d")
        if "내일" in s:
            return (now_kst() + timedelta(days=1)).strftime("%Y-%m-%d")
        m = re.search(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})", s)
        if m:
            y, mth, d = m.groups()
            return f"{int(y):04d}-{int(mth):02d}-{int(d):02d}"
    except Exception:
        pass
    return now_kst().strftime("%Y-%m-%d")


# ======================================================================================
# ✅ 후원수당 데이터 정리
# ======================================================================================
def clean_commission_data(data: dict) -> dict:
    """
    후원수당 데이터 정리 함수
    (예: 공백 제거, 숫자 변환 등)
    """
    cleaned = {}
    for k, v in data.items():
        if isinstance(v, str):
            cleaned[k] = v.strip()
        else:
            cleaned[k] = v
    return cleaned


# ======================================================================================
# ✅ 후원수당 파서 + 저장
# ======================================================================================
def parse_commission(text: str) -> Dict[str, Any]:
    """
    자연어 문장에서 후원수당 정보를 추출하고 시트에 저장
    예: "홍길동 2025-08-07 좌 10000 우 20000"
    """
    result = {
        "회원명": None,
        "기준일자": process_date("오늘"),
        "합계_좌": 0,
        "합계_우": 0,
    }

    if not text:
        return {"status": "fail", "reason": "입력 문장이 비어있습니다."}

    # 회원명 추출 (첫 단어)
    tokens = text.split()
    if tokens:
        result["회원명"] = tokens[0]

    # 날짜 추출
    date_match = re.search(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2})", text)
    if date_match:
        result["기준일자"] = process_date(date_match.group(1))

    # 좌/우 점수 추출
    left = re.search(r"(?:좌|왼쪽)\s*(\d+)", text)
    right = re.search(r"(?:우|오른쪽)\s*(\d+)", text)
    if left:
        result["합계_좌"] = int(left.group(1))
    if right:
        result["합계_우"] = int(right.group(1))

    # ✅ 시트에 저장
    ws = get_worksheet("후원수당")
    headers = ws.row_values(1)

    row = [result.get(h, "") for h in headers]
    ws.append_row(row, value_input_option="USER_ENTERED")

    return {"status": "success", "data": result}













# ======================================================================================
# service_commission
# ======================================================================================



SHEET_NAME = "후원수당"
COLUMNS = ["지급일자", "회원명", "후원수당", "비고"]


# ======================================================================================
# ✅ 내부 유틸
# ======================================================================================
def _get_headers(ws) -> List[str]:
    return [h.strip() for h in ws.row_values(1)]

def _ensure_headers(ws):
    headers = _get_headers(ws)
    if not headers:
        ws.append_row(COLUMNS)
        return COLUMNS
    return headers

def _row_to_obj(row: List[str], headers: List[str]) -> Dict[str, Any]:
    obj = {}
    for i, h in enumerate(headers):
        obj[h] = row[i] if i < len(row) else ""
    return obj


# ======================================================================================
# ✅ 후원수당 조회
# ======================================================================================
def find_commission(data: dict):
    sheet = get_commission_sheet()
    회원명 = data.get("회원명")

    if not 회원명:
        return {"error": "회원명이 없습니다."}

    all_rows = sheet.get_all_records()
    results = [row for row in all_rows if str(row.get("회원명", "")).strip() == 회원명]

    return results


# ======================================================================================
# ✅ 후원수당 등록
# ======================================================================================
def register_commission(data: dict) -> bool:
    """
    후원수당 시트에 새로운 데이터를 추가합니다.
    """
    try:
        ws = get_worksheet(SHEET_NAME)
        if not ws:
            return False

        headers = _ensure_headers(ws)

        # 데이터 정리
        data = clean_commission_data(data)

        row_data = [data.get(h, "") for h in headers]
        ws.append_row(row_data, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        print(f"[ERROR] register_commission: {e}")
        return False


# ======================================================================================
# ✅ 후원수당 수정
# ======================================================================================
def update_commission(member: str, date: str, updates: Dict[str, Any]) -> None:
    ws = get_worksheet(SHEET_NAME)
    headers = _ensure_headers(ws)
    vals = ws.get_all_values()

    try:
        idx_date = headers.index("지급일자")
        idx_member = headers.index("회원명")
    except ValueError:
        raise ValueError("후원수당 시트에 '지급일자' 또는 '회원명' 헤더가 없습니다.")

    target_row = None
    for i, r in enumerate(vals[1:], start=2):
        if len(r) > max(idx_date, idx_member) and r[idx_date].strip() == date and r[idx_member].strip() == member:
            target_row = i
            break

    if not target_row:
        raise ValueError(f"'{member}'의 {date} 지급 내역을 찾을 수 없습니다.")

    for field, value in updates.items():
        if field not in headers:
            continue
        col = headers.index(field) + 1
        safe_update_cell(ws, target_row, col, value, clear_first=True)


# ======================================================================================
# ✅ 후원수당 삭제
# ======================================================================================
def delete_commission(회원명: str, 기준일자: str = None) -> dict:
    sheet = get_commission_sheet()
    all_values = sheet.get_all_values()
    headers = all_values[0]
    rows = all_values[1:]

    target_indexes = []
    for i, row in enumerate(rows, start=2):
        row_dict = dict(zip(headers, row))
        if row_dict.get("회원명") == 회원명:
            if 기준일자 is None or row_dict.get("지급일자") == 기준일자:
                target_indexes.append(i)

    if not target_indexes:
        return {"message": "삭제할 데이터가 없습니다."}

    for idx in reversed(target_indexes):
        sheet.delete_rows(idx)

    return {"message": f"{len(target_indexes)}건 삭제 완료"}







