import pytest
from service import member_service


# ==============================
# DummySheet (테스트용 가짜 시트)
# ==============================
class DummySheet:
    def __init__(self):
        self.headers = ["회원명", "회원번호", "휴대폰번호"]
        self.rows = []

    def row_values(self, row):
        if row == 1:
            return self.headers
        return self.rows[row - 2] if row - 2 < len(self.rows) else []

    def col_values(self, col):
        if col == 1:  # 회원명 컬럼
            return [self.headers[0]] + [row[0] for row in self.rows]
        return []

    def get_all_records(self):
        return [dict(zip(self.headers, row)) for row in self.rows]

    def append_row(self, row, value_input_option=None):
        self.rows.append(row)


# ==============================
# Fixture
# ==============================
@pytest.fixture
def dummy_sheet():
    sheet = DummySheet()
    sheet.append_row(["홍길동", "123456", "010-1111-2222"])
    sheet.append_row(["이태수", "789012", "010-2222-3333"])
    sheet.append_row(["김철수", "345678", "010-3333-4444"])
    return sheet


@pytest.fixture(autouse=True)
def patch_get_member_sheet(monkeypatch, dummy_sheet):
    monkeypatch.setattr(member_service, "get_member_sheet", lambda: dummy_sheet)
    return dummy_sheet


# ==============================
# Tests
# ==============================
def test_find_member_in_text_exact_match():
    text = "홍길동 노니 2개 카드 주문"
    member = member_service.find_member_in_text(text)
    assert member == "홍길동"


def test_find_member_in_text_partial_name():
    text = "김철수님 홍삼 주문"
    member = member_service.find_member_in_text(text)
    assert member == "김철수"


def test_find_member_in_text_none_found():
    text = "노니 2개 카드 주문"
    member = member_service.find_member_in_text(text)
    assert member is None


def test_find_member_in_text_longer_name_priority(dummy_sheet, monkeypatch):
    """
    '김'과 '김철수'가 모두 후보일 때 → 긴 이름 '김철수' 우선
    """
    dummy_sheet.append_row(["김", "999999", "010-0000-0000"])
    monkeypatch.setattr(member_service, "get_member_sheet", lambda: dummy_sheet)

    text = "김철수 노니 주문"
    member = member_service.find_member_in_text(text)
    assert member == "김철수"

