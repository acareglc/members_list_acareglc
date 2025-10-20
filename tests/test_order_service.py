import pytest
from service import (
    handle_order_save,
    find_order,
    update_order,
    delete_order,
    clean_order_data,
)

# 🟢 주문 저장 → 조회 → 수정 → 삭제까지 테스트
def test_order_lifecycle():
    # 1. 저장
    new_order = {
        "주문일자": "2025-09-17",
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

    # 2. 조회
    results = find_order(member_name="테스트회원")
    assert any(r["제품명"] == "노니주스" for r in results)

    # 3. 수정
    updated_value = "부산광역시 해운대구"
    update_order("테스트회원", {"배송처": updated_value})

    results = find_order(member_name="테스트회원")
    assert any(r["배송처"] == updated_value for r in results)

    # 4. 삭제
    assert delete_order("테스트회원") is True

    results = find_order(member_name="테스트회원")
    assert not results
