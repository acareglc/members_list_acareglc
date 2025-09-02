import pytest
import utils.sheets as sheets
from service import order_service


def test_register_order(dummy_sheet, monkeypatch):
    """제품 주문 등록 테스트"""

    # ✅ order_service 내부에서 get_order_sheet() 호출 시 dummy_sheet 반환하도록 패치
    monkeypatch.setattr(sheets, "get_order_sheet", lambda: dummy_sheet)

    # ✅ 헤더 세팅
    dummy_sheet.headers = ["회원명", "회원번호", "휴대폰번호", "제품명", "제품가격", "PV"]
    dummy_sheet.rows = []

    # ✅ 주문 등록
    order = {
        "회원명": "홍길동",
        "회원번호": "123456",
        "휴대폰번호": "010-1111-2222",
        "제품명": "헤모힘",
        "제품가격": "100000",
        "PV": "100"
    }
    ok = order_service.register_order(order)
    assert ok is True

    # ✅ 시트에 저장된 값 검증
    records = dummy_sheet.get_all_records()
    assert len(records) == 1
    assert records[0]["회원명"] == "홍길동"
    assert records[0]["제품명"] == "헤모힘"
    assert records[0]["제품가격"] == "100000"
    assert records[0]["PV"] == "100"



def test_parse_order_text_without_member(monkeypatch):
    """회원명이 없는 경우 → None 반환"""
    text = "노니 2개 카드 주문"

    # find_member_in_text이 항상 None을 반환하도록 패치
    monkeypatch.setattr("parser.order_parser.find_member_in_text", lambda t: None)

    result = parse_order_text(text)
    assert result["회원명"] is None
    assert result["제품명"] == "노니"
    assert result["수량"] == 2
    assert result["결제방법"] == "카드"


