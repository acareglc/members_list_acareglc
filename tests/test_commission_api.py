import pytest
from app import app

# ==============================
# Flask Test Client
# ==============================
@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ==============================
# Tests
# ==============================
def test_register_commission_api(client, monkeypatch):
    """
    /register_commission API 테스트
    """
    class DummySheet:
        def __init__(self):
            self.headers = ["지급일자", "회원명", "후원수당", "비고"]
            self.rows = []
        def row_values(self, row):
            return self.headers if row == 1 else []
        def append_row(self, row, value_input_option=None):
            self.rows.append(row)
        def get_all_records(self):
            return [dict(zip(self.headers, r)) for r in self.rows]

    dummy_sheet = DummySheet()
    monkeypatch.setattr("service.commission_service.get_worksheet", lambda name: dummy_sheet)
    monkeypatch.setattr("service.commission_service.get_commission_sheet", lambda: dummy_sheet)

    payload = {"지급일자": "2025-08-31", "회원명": "홍길동", "후원수당": "10000", "비고": "테스트"}
    resp = client.post("/register_commission", json=payload)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("status") == "success"


def test_find_commission_api(client, monkeypatch):
    """
    /find_commission API 테스트
    """
    class DummySheet:
        def __init__(self):
            self.headers = ["지급일자", "회원명", "후원수당", "비고"]
            self.rows = [["2025-08-31", "홍길동", "10000", "테스트"]]
        def get_all_records(self):
            return [dict(zip(self.headers, self.rows[0]))]

    dummy_sheet = DummySheet()
    monkeypatch.setattr("service.commission_service.get_commission_sheet", lambda: dummy_sheet)

    payload = {"회원명": "홍길동"}
    resp = client.post("/find_commission", json=payload)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("status") == "success"
    assert isinstance(data.get("results"), list)
    assert data["results"][0]["회원명"] == "홍길동"
    assert data["results"][0]["후원수당"] == "10000"


def test_update_commission_api(client, monkeypatch):
    """
    /update_commission API 테스트
    """
    class DummySheet:
        def __init__(self):
            self.headers = ["지급일자", "회원명", "후원수당", "비고"]
            self.rows = [["2025-08-31", "홍길동", "10000", "테스트"]]
        def row_values(self, row):
            return self.headers if row == 1 else []
        def get_all_values(self):
            return [self.headers] + self.rows

    dummy_sheet = DummySheet()
    monkeypatch.setattr("service.commission_service.get_worksheet", lambda name: dummy_sheet)
    monkeypatch.setattr("service.commission_service.safe_update_cell", lambda ws, r, c, v, clear_first=True: True)

    payload = {
        "회원명": "홍길동",
        "지급일자": "2025-08-31",
        "updates": {"후원수당": "20000"}
    }
    resp = client.post("/update_commission", json=payload)

    assert resp.status_code == 200
    data = resp.get_json()
    assert "수정되었습니다" in data.get("message", "")


def test_delete_commission_api(client, monkeypatch):
    """
    /delete_commission API 테스트
    """
    class DummySheet:
        def __init__(self):
            self.headers = ["지급일자", "회원명", "후원수당", "비고"]
            self.rows = [
                ["2025-08-30", "홍길동", "5000", "비고1"],
                ["2025-08-31", "홍길동", "10000", "비고2"],
                ["2025-08-31", "이태수", "8000", "비고3"]
            ]
        def get_all_values(self):
            return [self.headers] + self.rows
        def delete_rows(self, idx):
            if 2 <= idx <= len(self.rows) + 1:
                self.rows.pop(idx - 2)

    dummy_sheet = DummySheet()
    monkeypatch.setattr("service.commission_service.get_commission_sheet", lambda: dummy_sheet)

    payload = {"회원명": "홍길동", "지급일자": "2025-08-31"}
    resp = client.post("/delete_commission", json=payload)

    assert resp.status_code == 200
    data = resp.get_json()
    assert "삭제 완료" in data.get("message", "")
