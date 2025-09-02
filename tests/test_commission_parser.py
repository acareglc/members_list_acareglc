import pytest
from parser.commission_parser import parse_commission
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
    monkeypatch.setattr("service.commission_service.get_commission_sheet", lambda: dummy_sheet)
    monkeypatch.setattr("service.commission_service.get_worksheet", lambda name: dummy_sheet)
    monkeypatch.setattr("parser.commission_parser.get_worksheet", lambda name: dummy_sheet)

    def fake_safe_update_cell(ws, r, c, v, clear_first=True):
        row_idx = r - 2
        col_idx = c - 1
        if 0 <= row_idx < len(ws.rows) and 0 <= col_idx < len(ws.headers):
            ws.rows[row_idx][col_idx] = v
        return True

    monkeypatch.setattr("service.commission_service.safe_update_cell", fake_safe_update_cell)
    return dummy_sheet


# ==============================
# Tests
# ==============================
def test_parse_and_register_commission(dummy_sheet):
    text = "홍길동 2025-08-31 좌 10000 우 20000"
    result = parse_commission(text)

    assert result["status"] == "success"
    assert result["data"]["회원명"] == "홍길동"
    assert result["data"]["합계_좌"] == 10000
    assert result["data"]["합계_우"] == 20000

    # ✅ 시트에 데이터가 실제로 들어갔는지 확인
    records = dummy_sheet.get_all_records()
    assert len(records) == 1
    assert records[0]["회원명"] == "홍길동"


def test_find_commission_after_parse(dummy_sheet):
    # 먼저 파싱 + 저장
    parse_commission("홍길동 2025-08-31 좌 5000 우 7000")

    results = commission_service.find_commission({"회원명": "홍길동"})
    assert len(results) == 1
    assert results[0]["회원명"] == "홍길동"
    assert results[0]["후원수당"] in ["", None] or results[0]["후원수당"] == ""  # 기본 구조 확인
