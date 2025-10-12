# =================================================
# intent_map (routes → intent 함수 매핑)
# =================================================
from flask import g

from routes.routes_member import (
    search_member_func, register_member_func, update_member_func,
    save_member_func, delete_member_func, search_by_code_logic, member_select,
    get_full_member_info, get_summary_info, get_compact_info,
    delete_member_field_nl_func, handle_update_member,
)
from routes.routes_memo import (
    memo_save_auto_func, add_counseling_func,
    search_memo_func, search_memo_from_text_func, memo_find_auto_func,
)
from routes.routes_order import (
    order_upload_pc_func,
    order_upload_ipad_func,
    order_nl_func,
    order_auto_func,
    save_order_proxy_func,
)
from routes.routes_commission import (
    commission_find_auto_func, find_commission_func, search_commission_by_nl_func,
)


from routes.routes_image import upload_image_func, search_image_func


# routes/intent_map.py
from routes.routes_order import parse_and_save_order  # ✅ 올바른 경로


from routes.routes_order import handle_product_order  # routes 폴더 내 라우터 기반 처리 함수





# ======================================================================================
# intent_map
# ======================================================================================

# 회원 관련
MEMBER_INTENTS = {
    "search_member": search_member_func,
    "member_select": member_select,  # 전체정보 / 종료
    "register_member": register_member_func,
    "update_member": update_member_func, 
    "save_member": save_member_func,
    "delete_member": delete_member_func,
    "delete_member_field_nl_func": delete_member_field_nl_func,
    "search_by_code_logic": search_by_code_logic,
    

    # 추가 intent 처리
    "select_member": lambda: get_full_member_info(g.query.get("results", [])),
    "summary_member": lambda: get_summary_info(g.query.get("results", [])),
    "compact_member": lambda: get_compact_info(g.query.get("results", [])),
}

# 메모/일지 관련
MEMO_INTENTS = {
    "memo_add": memo_save_auto_func,             # 자연어 저장
    "add_counseling": add_counseling_func,       # JSON 저장
    "memo_search": search_memo_func,             # JSON 기반 검색
    "search_memo_from_text": search_memo_from_text_func,  # 자연어 기반 검색
    "memo_find": memo_find_auto_func,
    "memo_find_auto": memo_find_auto_func,
}


# 이미지메모 관련
IMAGE_INTENTS = {
    "upload_image": upload_image_func,
    "search_image": search_image_func,
}




# 주문 관련
ORDER_INTENTS = {
    "order_upload_pc": order_upload_pc_func,
    "order_upload_ipad": order_upload_ipad_func,
    "order_nl": order_nl_func,
    "order_auto": order_auto_func,
    "save_order_proxy": save_order_proxy_func,
    "handle_product_order": handle_product_order,

}





# 후원수당 관련
COMMISSION_INTENTS = {
    "commission_find": find_commission_func,
    "commission_find_auto": commission_find_auto_func,
    "search_commission_by_nl": search_commission_by_nl_func,
}

# 전체 intent 매핑
INTENT_MAP = {
    **MEMBER_INTENTS,
    **MEMO_INTENTS,
    **IMAGE_INTENTS,  # ✅ 추가
    **ORDER_INTENTS,
    **COMMISSION_INTENTS,
 

}





