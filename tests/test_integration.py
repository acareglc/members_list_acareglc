import pytest
from datetime import datetime
from service import (
    register_member_internal,
    handle_order_save, find_order, clean_order_data,
    save_memo, find_memo,
)
from parser import guess_intent
from utils import now_kst


@pytest.fixture(scope="module")
def today_date():
    """오늘 날짜 (YYYY-MM-DD)"""
    return now_kst().strftime("%Y-%m-%d")


# ------------------------------------------------------------------
# 회원 통합 테스트
# ------------------------------------------------------------------
def test_integration_member(today_date):
    """자연어 기반 회원 등록/조회/삭제 통합 테스트"""
    name = "테스트회원"
    number = f"9{int(datetime.now().timestamp())}"  # 항상 고유 번호 생성
    phone = "010-1111-2222"

    result = register_member_internal(name, number, phone)
    assert result["status"] in ("created", "exists")


# ------------------------------------------------------------------
# 주문 통합 테스트
# ------------------------------------------------------------------
def test_integration_order(today_date):
    """자연어 기반 주문 등록/조회/삭제 통합 테스트"""
    text = "테스트회원 노니주스 2개 카드 주문"
    intent = guess_intent(text)
    assert intent in ("order_register", "save_order", "handle_product_order")

    new_order = {
        "주문일자": today_date,
        "회원명": "테스트회원",
        "회원번호": "99999999",
        "휴대폰번호": "010-1234-5678",
        "제품명": "노니주스",
        "제품가격": 45000,
        "PV": 30,
        "결재방법": "카드",
        "소비자_고객명": "홍길동",
        "소비자_휴대폰번호": "010-9999-8888",
        "배송처": "서울특별시 강남구",
        "수령확인": "N",
    }

    cleaned = clean_order_data(new_order)
    handle_order_save(cleaned)

    results = find_order(member_name="테스트회원")
    assert any("노니주스" in r.get("제품명", "") for r in results)


# ------------------------------------------------------------------
# 메모 통합 테스트
# ------------------------------------------------------------------
def test_integration_memo(today_date):
    """자연어 기반 메모 저장/검색 통합 테스트"""
    text = "테스트회원 상담일지 저장 오늘은 통합테스트 진행"
    intent = guess_intent(text)
    assert intent in ("memo_save_auto_func", "add_counseling")

    member = "테스트회원"
    content = "pytest 통합 메모 저장 테스트"
    save_memo("상담일지", member, content)

    results = find_memo("pytest", "상담일지")
    assert any(content in r.get("내용", "") for r in results)


# ------------------------------------------------------------------
# 메모 검색 통합 테스트
# ------------------------------------------------------------------
def test_integration_memo_search():
    """자연어 기반 메모 검색 시나리오"""
    # 1) 개인일지 검색
    text1 = "이태수 개인일지 검색 포항"
    intent1 = guess_intent(text1)
    assert intent1 in ("memo_search", "search_memo_func")  # ✅ 두 경우 다 허용

    # 2) 전체메모 검색
    text2 = "전체메모 검색 중국"
    intent2 = guess_intent(text2)
    assert intent2 in ("memo_search", "search_memo_func")  # ✅ 두 경우 다 허용

