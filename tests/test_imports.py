import pytest
import traceback

def test_app_imports():
    """
    app.py가 정상적으로 import 되고,
    그 안에서 정의/임포트된 함수들이 에러 없이 로드되는지 확인합니다.
    """
    try:
        import app
    except Exception as e:
        traceback.print_exc()
        pytest.fail(f"❌ app.py import 실패: {e}")

    # ✅ app 네임스페이스에서 주요 함수들이 존재하는지 확인
    required_functions = [
        # 회원(Member)
        "find_member_route", "search_by_natural_language",
        "update_member_route", "save_member", "register_member_route",
        "delete_member_route", "delete_member_field_nl",

        # 주문(Order)
        "upload_order_auto", "upload_order_ipad", "upload_order_pc",
        "upload_order_text", "add_orders", "save_order_from_json",
        "saveOrder", "parse_and_save_order", "register_order_route",
        "update_order_route", "delete_order_route", "delete_order_confirm",
        "delete_order_request", "find_order_route", "search_order_by_nl",
        "order_find_auto",

        # 메모(Note)
        "save_memo_route", "add_counseling_route", "memo_save_auto",
        "memo_find_auto", "search_memo", "search_memo_from_text",

        # 후원수당(Commission)
        "register_commission_route", "update_commission_route",
        "delete_commission_route", "find_commission_route",
        "search_commission_by_nl", "commission_find_auto",
    ]

    missing = []
    for func in required_functions:
        if not hasattr(app, func):
            missing.append(func)

    if missing:
        pytest.fail(f"❌ app.py에 누락된 함수들: {missing}")
    else:
        print("✅ 모든 라우트 함수 import 성공")
