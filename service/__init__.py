"""
service 패키지 초기화
공식적으로 공개되는 서비스 함수만 __all__에 정의
"""




# --------------------------
# 회원 서비스
# --------------------------
from .service import (
    register_member, find_member, update_member, delete_member,
    find_member_internal, clean_member_data,
    register_member_internal, update_member_internal,
    delete_member_internal, delete_member_field_nl_internal,
    process_member_query, 
    update_member_info,  # ✅ 추가
)
# --------------------------
# 메모 서비스
# --------------------------
from .service import (
    save_memo, find_memo,
    search_in_sheet,
)

# --------------------------
# 주문 서비스
# --------------------------
from .service import (
   
    save_order_to_sheet, find_order, register_order,
    update_order, delete_order, delete_order_by_row,
    clean_order_data, 
)

# --------------------------
# 후원수당 서비스
# --------------------------
from .service import (
    find_commission, register_commission,
    update_commission, delete_commission,
    clean_commission_data,
)

# --------------------------------------------------
# 공식 공개 API (__all__)
# --------------------------------------------------
__all__ = [
    # 회원
    "register_member", "find_member", "update_member", "delete_member",
    "find_member_internal", "clean_member_data",
    "register_member_internal", "update_member_internal",
    "delete_member_internal", "delete_member_field_nl_internal",
    "process_member_query", 
    "update_member_info",  # ✅ 추가
    # 메모
    "save_memo", "find_memo", "search_in_sheet", 

    # 주문
   
    "save_order_to_sheet", "find_order", "register_order",
    "update_order", "delete_order", "delete_order_by_row",
    "clean_order_data", 

    # 후원수당
    "find_commission", "register_commission",
    "update_commission", "delete_commission",
    "clean_commission_data",
]






