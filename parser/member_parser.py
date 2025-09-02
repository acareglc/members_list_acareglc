import re
from typing import Dict, Optional, Tuple, List

from parser.field_map import field_map
from utils import clean_tail_command, clean_value_expression



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
import re
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
    - "장미 회원번호 12345 비밀번호 9999 수정"

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

    # 필드 맵핑 정의
    field_map = {
        "주소": "주소",
        "휴대폰": "휴대폰번호",
        "휴대폰번호": "휴대폰번호",
        "전화번호": "휴대폰번호",
        "비밀번호": "비밀번호",
        "비번": "비밀번호",
        "카드번호": "카드번호",
        "특수번호": "특수번호",
    }

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



