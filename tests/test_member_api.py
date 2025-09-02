import pytest
from app import app
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
def client():
    return app.test_client()


@pytest.fixture
def dummy_sheet(monkeypatch):
    sheet = DummySheet()
    monkeypatch.setattr(member_service, "get_member_sheet", lambda: sheet)
    monkeypatch.setattr(
        member_service,
        "safe_update_cell",
        lambda ws, r, c, v, clear_first=True: ws.update_cell(r, c, v),
    )
    return sheet


# ==============================
# API CRUD 통합 테스트
# ==============================
def test_member_api_crud(client, dummy_sheet):
    # 1) 회원 등록
    resp = client.post(
        "/save_member",
        json={"회원명": "홍길동", "회원번호": "123456", "휴대폰번호": "010-1234-5678"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "success"

    # 2) 회원 조회
    resp = client.post("/find_member", json={"회원명": "홍길동"})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data[0]["회원번호"] == "123456"

    # 3) 회원 수정
    resp = client.post(
        "/update_member",
        json={"회원명": "홍길동", "수정": {"주소": "부산"}},
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "success"

    # 수정 확인
    resp = client.post("/find_member", json={"회원명": "홍길동"})
    assert resp.get_json()[0]["주소"] == "부산"

    # 4) 회원 삭제
    resp = client.post("/delete_member", json={"회원명": "홍길동"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "success"

    # 삭제 확인
    resp = client.post("/find_member", json={"회원명": "홍길동"})
    assert resp.get_json() == []
