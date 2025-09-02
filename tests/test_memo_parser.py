import pytest
from parser.memo_parser import parse_memo


# ==============================
# DummySheet (테스트용 시트)
# ==============================
class DummySheet:
    def __init__(self):
        self.headers = ["날짜", "회원명", "내용"]
        self.rows = []

    def append_row(self, row, value_input_option=None):
        self.rows.append(row)

    def get_all_records(self):
        return [dict(zip(self.headers, row)) for row in self.rows]


# ==============================
# Fixture
# ==============================
@pytest.fixture
def dummy_sheet():
    return DummySheet()


@pytest.fixture(autouse=True)
def patch_get_worksheet(monkeypatch, dummy_sheet):
    # 상담일지 / 개인메모 / 활동일지 모두 같은 dummy_sheet 반환
    monkeypatch.setattr("parser.memo_parser.get_worksheet", lambda name: dummy_sheet)
    return dummy_sheet


# ==============================
# Tests
# ==============================
def test_parse_memo_success(dummy_sheet):
    text = "이태수 상담일지 저장 오늘은 비가 옵니다"
    result = parse_memo(text)

    assert result["status"] == "success"
    assert result["sheet"] == "상담일지"
    assert result["member"] == "이태수"
    assert "오늘은 비가 옵니다" in result["content"]

    records = dummy_sheet.get_all_records()
    assert len(records) == 1
    assert records[0]["회원명"] == "이태수"
    assert "오늘은 비가 옵니다" in records[0]["내용"]


def test_parse_memo_fail_invalid_text():
    text = "저장만"  # 회원명/시트명 없음
    result = parse_memo(text)

    assert result["status"] == "fail"


def test_parse_memo_personal_memo(dummy_sheet):
    text = "홍길동 개인일지 기록 운동을 시작했습니다"
    result = parse_memo(text)

    assert result["status"] == "success"
    assert result["sheet"] == "개인메모"
    assert result["member"] == "홍길동"

    records = dummy_sheet.get_all_records()
    assert records[-1]["회원명"] == "홍길동"
    assert "운동을 시작했습니다" in records[-1]["내용"]
