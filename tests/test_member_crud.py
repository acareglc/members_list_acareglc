import pytest
from service import member_service


# ==============================
# DummySheet (테스트용 가짜 시트)
# ==============================
class DummySheet:
    def __init__(self):
        self.headers = ["회원명", "회원번호", "휴대폰번호", "주소"]
        self.rows = []

    def row_values(self, row):
        if row == 1:
            return self.headers
        return self.rows[row - 2] if row - 2 < len(self.rows) else []

    def get_all_records(self):
        return [dict(zip(self.headers, row)) for row in self.rows]

    def append_row(self, row, value_input_option=None):
        self.rows.append(row)

    def update_cell(self, r, c, v):
        self.rows[r - 2][c - 1] = v

    def delete_rows(self, r):
        if 0 <= r - 2 < len(self.rows):
            self.rows.pop(r - 2)


# ==============================
# Fixtures
# ==============================
@pytest.fixture
def dummy_sheet():
    return DummySheet()


@pytest.fixture(autouse=True)
def patch_get_member_sheet(monkeypatch, dummy_sheet):
    """service.member_service 내부에서 항상 dummy_sheet를 사용하도록 패치"""
    monkeypatch.setattr(member_service, "get_member_sheet", lambda: dummy_sheet)
    monkeypatch.setattr(
        member_service, "safe_update_cell",
        lambda ws, r, c, v, clear_first=True: ws.update_cell(r, c, v)
    )
    return dummy_sheet


# ==============================
# CRUD 통합 테스트
# ==============================
def test_member_crud(dummy_sheet):
    # 1) 회원 등록
    ok = member_service.register_member("홍길동", "123456", "010-1234-5678")
    assert ok is True
    records = dummy_sheet.get_all_records()
    assert len(records) == 1
    assert records[0]["회원명"] == "홍길동"

    # 2) 회원 조회
    result = member_service.find_member("홍길동")
    assert isinstance(result, list)
    assert result[0]["회원번호"] == "123456"

    # 3) 회원 수정
    ok = member_service.update_member("홍길동", {"주소": "부산"})
    assert ok is True
    records = dummy_sheet.get_all_records()
    assert records[0]["주소"] == "부산"

    # 4) 회원 삭제
    ok = member_service.delete_member("홍길동")
    assert ok is True
    assert dummy_sheet.get_all_records() == []


