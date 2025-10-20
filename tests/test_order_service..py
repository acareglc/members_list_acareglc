import pytest
from parser import parse_order_text, ensure_orders_list   # ✅ parser/__init__.py 에서 직접 import
from service.service import service_order                 # ✅ service.py 안에 정의된 service_order 함수 사용


def test_parse_order_text_basic():
    text = "이태수 노니 2개 카드 주문 저장"
    result = parse_order_text(text)

    assert isinstance(result, dict)
    assert result.get("회원명") == "이태수"
    assert "노니" in result.get("제품명", "")
    assert result.get("수량") == 2
    assert result.get("결제방법") == "카드"


def test_service_order_append(client=None):
    """
    실제 service_order 함수가 주문을 시트에 저장하는지 검증
    (⚠️ 테스트 시에는 반드시 테스트용 .env.test + 테스트용 시트 사용)
    """
    order_data = {
        "주문일자": "2025-09-17",
        "회원명": "이태수",
        "제품명": "홍삼",
        "제품가격": 35000,
        "PV": 20,
        "소비자_고객명": "홍길동",
        "소비자_휴대폰번호": "010-1111-2222",
        "배송처": "서울시 강남구"
    }

    result = service_order(order_data)

    assert isinstance(result, dict)
    assert result.get("status") in ("success", "error")







from service import handle_order_save, find_order, delete_order
from service import clean_order_data
from tests.conftest import assert_contains, assert_not_contains

def test_order_lifecycle(today_date):
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

    # 1. 저장
    cleaned = clean_order_data(new_order)
    handle_order_save(cleaned)

    # 2. 조회
    results = find_order(member_name="테스트회원")
    assert_contains(results, "회원명", "테스트회원")

    # 3. 삭제
    delete_order("테스트회원", "노니주스")
    results_after = find_order(member_name="테스트회원")
    assert_not_contains(results_after, "제품명", "노니주스")



