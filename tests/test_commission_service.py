import pytest
from service import commission_service


# ==============================
# DummySheet (후원수당 시트 시뮬레이션)
# ==============================
class DummySheet:
    def __init__(self):
        self.headers = ["지급일자", "회원명", "후원수당", "비고"]
        self.rows = []

    def row_values(self, row):
        if row == 1:
            return self.headers
        return self.rows[row - 2] if row - 2 < len(self.rows) else []

    def get_all_records(self):
        return [dict(zip(self.headers, row)) for row in self.rows]

    def get_all_values(self):
        return [self.headers] + self.rows

    def append_row(self, row, value_input_option=None):
        self.rows.append(row)

    def delete_rows(self, idx):
        if 2 <= idx <= len(self.rows) + 1:
            self.rows.pop(idx - 2)


# ==============================
# Fixtures
# ==============================
@pytest.fixture
def dummy_sheet():
    return DummySheet()


@pytest.fixture(autouse=True)
def patch_sheets(monkeypatch, dummy_sheet):
    # get_commission_sheet / get_worksheet → dummy_sheet 반환
    monkeypatch.setattr("service.commission_service.get_commission_sheet", lambda: dummy_sheet)
    monkeypatch.setattr("service.commission_service.get_worksheet", lambda name: dummy_sheet)

    # safe_update_cell을 DummySheet.rows에 직접 반영
    def fake_safe_update_cell(ws, r, c, v, clear_first=True):
        row_idx = r - 2   # header 제외, 데이터는 2행부터 시작
        col_idx = c - 1
        if 0 <= row_idx < len(ws.rows) and 0 <= col_idx < len(ws.headers):
            ws.rows[row_idx][col_idx] = v
        return True

    monkeypatch.setattr("service.commission_service.safe_update_cell", fake_safe_update_cell)
    return dummy_sheet



# ==============================
# Tests
# ==============================
def test_register_and_find_commission(dummy_sheet):
    data = {"지급일자": "2025-08-31", "회원명": "홍길동", "후원수당": "10000", "비고": "테스트"}
    ok = commission_service.register_commission(data)
    assert ok is True

    results = commission_service.find_commission({"회원명": "홍길동"})
    assert len(results) == 1
    assert results[0]["회원명"] == "홍길동"
    assert results[0]["후원수당"] == "10000"


def test_update_commission(dummy_sheet):
    # 초기 데이터
    dummy_sheet.append_row(["2025-08-31", "홍길동", "10000", "테스트"])

    # 수정 실행
    commission_service.update_commission("홍길동", "2025-08-31", {"후원수당": "20000"})

    records = dummy_sheet.get_all_records()
    assert records[0]["후원수당"] == "20000"


def test_delete_commission(dummy_sheet):
    # 초기 데이터 2건
    dummy_sheet.append_row(["2025-08-30", "홍길동", "5000", "비고1"])
    dummy_sheet.append_row(["2025-08-31", "홍길동", "10000", "비고2"])
    dummy_sheet.append_row(["2025-08-31", "이태수", "8000", "비고3"])

    result = commission_service.delete_commission("홍길동", 기준일자="2025-08-31")
    assert "삭제 완료" in result["message"]

    records = dummy_sheet.get_all_records()
    # 홍길동 2025-08-31 데이터는 삭제됨
    assert all(not (r["회원명"] == "홍길동" and r["지급일자"] == "2025-08-31") for r in records)
    # 다른 회원 데이터는 남아 있음
    assert any(r["회원명"] == "이태수" for r in records)
