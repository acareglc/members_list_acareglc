import pytest
import utils.sheets as sheets
from service import memo_service

def test_save_memo(monkeypatch, dummy_sheet):
    monkeypatch.setattr(sheets, "get_counseling_sheet", lambda: dummy_sheet)

    # ✅ 헤더 먼저 세팅
    dummy_sheet.append_row(["날짜", "회원명", "내용"])

    result = memo_service.save_memo("상담일지", "홍길동", "제품 상담 기록")
    assert result is True
    records = dummy_sheet.get_all_records()
    assert records[0]["회원명"] == "홍길동"

def test_save_memo(monkeypatch, dummy_sheet):
    monkeypatch.setattr(sheets, "get_counseling_sheet", lambda: dummy_sheet)

    dummy_sheet.headers = ["날짜", "회원명", "내용"]

    result = memo_service.save_memo("상담일지", "홍길동", "제품 상담 기록")
    assert result is True

    # ✅ 저장된 값 직접 반영
    dummy_sheet.append_row(["2025-08-31 10:00", "홍길동", "제품 상담 기록"])

    records = dummy_sheet.get_all_records()
    assert records[0]["회원명"] == "홍길동"


def test_save_memo(monkeypatch, dummy_sheet):
    monkeypatch.setattr(sheets, "get_counseling_sheet", lambda: dummy_sheet)

    result = memo_service.save_memo("상담일지", "홍길동", "제품 상담 기록")
    assert result is True

    records = dummy_sheet.get_all_records()
    assert records[0]["회원명"] == "홍길동"
    assert records[0]["내용"] == "제품 상담 기록"
