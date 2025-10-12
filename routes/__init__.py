"""
routes 패키지 초기화 파일
intent 기반 공식 API 함수만 export
(⚠️ intent_map 은 여기서 import 하지 않음 → 순환 import 방지)
"""

# --------------------------
# 회원 관련
# --------------------------
from .routes_member import (
    # 검색
    search_member_func,
    search_by_code_logic,
    find_member_logic,
    member_select_direct,
    member_select,
    call_member,
    handle_update_member,

    # 정보 출력
    sort_fields_by_field_map,
    get_full_member_info,
    get_summary_info,
    get_compact_info,

    # 등록/수정/저장
    register_member_func,
    update_member_func,
    save_member_func,

    # 삭제
    delete_member_func,
    delete_member_field_nl_func,
)

# --------------------------
# 메모 관련
# --------------------------
from .routes_memo import (
    memo_save_auto_func,
    add_counseling_func,
    search_memo_func,
    search_memo_from_text_func,
    memo_find_auto_func,
    search_memo_core,
)

# --------------------------
# 주문 관련
# --------------------------
from .routes_order import (
    order_upload_pc_func,
    order_upload_ipad_func,
    order_nl_func,
    order_auto_func,
    save_order_proxy_func,
    addOrders,
    handle_product_order,
)





# --------------------------
# 후원수당 관련
# --------------------------
from .routes_commission import (
    commission_find_auto_func,
    find_commission_func,
    search_commission_by_nl_func,
)

# --------------------------------------------------
# 공식 공개 API (__all__)
# --------------------------------------------------
__all__ = [
    # 회원 검색/출력
    "search_member_func", "search_by_code_logic", "find_member_logic",
    "member_select_direct", "member_select",
    "sort_fields_by_field_map", "get_full_member_info",
    "get_summary_info", "get_compact_info", "call_member",
    "handle_update_member",
    
    # 회원 등록/수정/저장
    "register_member_func", "update_member_func", "save_member_func",

    # 회원 삭제
    "delete_member_func", "delete_member_field_nl_func",

    # 메모
    "memo_save_auto_func", "add_counseling_func",
    "search_memo_func", "search_memo_from_text_func", "memo_find_auto_func",
    "search_memo_core",

    # 주문
    "order_upload_pc_func",
    "order_upload_ipad_func",
    "order_nl_func",
    "order_auto_func",
    "save_order_proxy_func",
    "addOrders",
    "handle_product_order",

    # 후원수당
    "commission_find_auto_func", "find_commission_func", "search_commission_by_nl_func",
]

