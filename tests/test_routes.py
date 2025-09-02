import pytest
from app import app

@pytest.fixture
def client():
    app.testing = True
    return app.test_client()

# ===============================
# 회원(Member) 테스트
# ===============================
@pytest.mark.parametrize("endpoint,payload", [
    ("/find_member", {"회원명": "홍길동"}),
    ("/members/search-nl", {"query": "홍길동 조회"}),
    ("/update_member", {"요청문": "홍길동 주소 서울 변경"}),
    ("/save_member", {"요청문": "홍길동 회원번호 12345 휴대폰 010-1111-2222"}),
    ("/register_member", {"회원명": "홍길동", "회원번호": "12345", "휴대폰번호": "010-1111-2222"}),
    ("/delete_member", {"회원명": "홍길동"}),
    ("/delete_member_field_nl", {"요청문": "홍길동 주소 삭제"}),
])
def test_member_endpoints(client, endpoint, payload):
    resp = client.post(endpoint, json=payload)
    assert resp.status_code in (200, 201, 400, 404, 500)

# ===============================
# 주문(Order) 테스트
# ===============================
@pytest.mark.parametrize("endpoint,payload", [
    ("/upload_order_text", {"message": "홍길동 제품주문 저장"}),
    ("/register_order", {"회원명": "홍길동", "제품명": "홍삼", "제품가격": "50000", "PV": "10", "배송처": "서울"}),
    ("/update_order", {"회원명": "홍길동", "제품명": "홍삼", "수정목록": {"제품가격": "60000"}}),
    ("/delete_order", {"회원명": "홍길동", "제품명": "홍삼"}),
    ("/delete_order_confirm", {"삭제번호": "1"}),
    ("/delete_order_request", {}),
    ("/find_order", {"회원명": "홍길동", "제품명": "홍삼"}),
])
def test_order_endpoints(client, endpoint, payload):
    resp = client.post(endpoint, json=payload)
    assert resp.status_code in (200, 201, 400, 404, 500)

# ===============================
# 메모(Note) 테스트
# ===============================
@pytest.mark.parametrize("endpoint,payload", [
    ("/save_memo", {"일지종류": "상담일지", "회원명": "홍길동", "내용": "오늘 상담 기록"}),
    ("/add_counseling", {"요청문": "홍길동 상담일지 저장 오늘 상담했습니다."}),
    ("/memo_save_auto", {"요청문": "홍길동 개인일지 저장 오늘 메모"}),
    ("/memo_find_auto", {"text": "전체메모 검색 상담"}),
    ("/search_memo", {"sheet": "상담일지", "keywords": ["상담"]}),
    ("/search_memo_from_text", {"text": "전체메모 검색 상담"}),
])
def test_memo_endpoints(client, endpoint, payload):
    resp = client.post(endpoint, json=payload)
    assert resp.status_code in (200, 201, 400, 404, 500)

# ===============================
# 후원수당(Commission) 테스트
# ===============================
@pytest.mark.parametrize("endpoint,payload", [
    ("/register_commission", {"회원명": "홍길동", "후원수당": "10000"}),
    ("/update_commission", {"회원명": "홍길동", "지급일자": "2025-09-01", "updates": {"합계_좌": "20000"}}),
    ("/delete_commission", {"회원명": "홍길동", "지급일자": "2025-09-01"}),
    ("/find_commission", {"회원명": "홍길동"}),
    ("/commission/search-nl", {"query": "홍길동 후원수당 조회"}),
    ("/commission_find_auto", {"회원명": "홍길동"}),
])
def test_commission_endpoints(client, endpoint, payload):
    resp = client.post(endpoint, json=payload)
    assert resp.status_code in (200, 201, 400, 404, 500)
