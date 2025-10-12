"""
parser 패키지 초기화
공식적으로 공개되는 파서 함수만 __all__에 정의
"""

# --------------------------
# intent / 전처리
# --------------------------
from .parse import (
    field_map,
    INTENT_RULES,
    guess_intent,
    preprocess_user_input,
)

# --------------------------
# 회원 관련 파서
# --------------------------
from .parse import (
    extract_value, parse_field_value,
    extract_phone, extract_member_number,
    extract_password, extract_referrer,
    parse_registration,
    infer_field_from_value, parse_request_and_update,
    parse_natural_query, parse_korean_phone,
    parse_member_number, parse_request,
    parse_deletion_request, parse_deletion_request_compat,
    parse_conditions,
)

# --------------------------
# 메모 관련 파서
# --------------------------
from .parse import (
    parse_request_line,
    parse_memo,
)

# --------------------------
# 주문 관련 파서
# --------------------------
from .parse import (
    parse_order_text,
    ensure_orders_list,
    parse_order_text_rule,
    
   
    
)

# --------------------------
# 후원수당 관련 파서
# --------------------------
from .parse import (
    process_date,
    clean_commission_data,
    parse_commission,
)

# --------------------------------------------------
# 공식 공개 API (__all__)
# --------------------------------------------------
__all__ = [
    # intent
    "field_map", "INTENT_RULES", "guess_intent", "preprocess_user_input",

    # 회원 파서
    "extract_value", "parse_field_value", "extract_phone", "extract_member_number",
    "extract_password", "extract_referrer", "parse_registration",
    "infer_field_from_value", "parse_request_and_update",
    "parse_natural_query", "parse_korean_phone", "parse_member_number",
    "parse_request", "parse_deletion_request", "parse_deletion_request_compat",
    "parse_conditions",

    # 메모 파서
    "parse_request_line", "parse_memo",

    # 주문 파서
    "parse_order_text", "ensure_orders_list", "parse_order_text_rule", 

    # 후원수당 파서
    "process_date", "clean_commission_data", "parse_commission",
]
