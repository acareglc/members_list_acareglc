import pytest
import json
from parser.order_parser import parse_order_text, ensure_orders_list


def test_parse_order_text_basic():
    text = "이태수 노니 2개 카드 주문"
    result = parse_order_text(text)
    assert result["회원명"] == "이태수"
    assert result["제품명"] == "노니"
    assert result["수량"] == 2
    assert result["결제방법"] == "카드"


def test_parse_order_text_default_values():
    text = "홍길동 제품주문"
    result = parse_order_text(text)
    assert result["회원명"] == "홍길동"
    assert result["제품명"] == "제품"
    assert result["수량"] == 1
    assert result["결제방법"] == "카드"


def test_ensure_orders_list_from_dict():
    parsed = {"제품명": "노니", "수량": 2, "결제방법": "카드"}
    result = ensure_orders_list(parsed)
    assert isinstance(result, list)
    assert result[0]["제품명"] == "노니"


def test_ensure_orders_list_from_orders_key():
    parsed = {"orders": [
        {"제품명": "노니", "수량": 1},
        {"제품명": "홍삼", "수량": 2}
    ]}
    result = ensure_orders_list(parsed)
    assert len(result) == 2
    assert result[1]["제품명"] == "홍삼"


def test_ensure_orders_list_from_json_string():
    parsed = json.dumps({"제품명": "노니", "수량": 3, "결제방법": "계좌이체"})
    result = ensure_orders_list(parsed)
    assert result[0]["결제방법"] == "계좌이체"


def test_ensure_orders_list_invalid_input():
    parsed = 12345
    result = ensure_orders_list(parsed)
    assert result == []
