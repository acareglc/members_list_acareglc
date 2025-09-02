import re

def remove_josa(s: str) -> str:
    """단어 끝의 조사(이/가/은/는/을/를/과/와/의/으로/로) 제거"""
    return re.sub(r'(이|가|은|는|을|를|과|와|의|으로|로)$', '', s.strip())


def remove_spaces(s: str) -> str:
    """문자열 내 모든 공백 제거"""
    return re.sub(r'\s+', '', s)


def split_to_parts(s: str) -> list[str]:
    """문자열을 공백 단위로 분리하여 리스트 반환"""
    return re.split(r'\s+', s.strip())


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
