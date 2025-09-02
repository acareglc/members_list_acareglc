def guess_intent(text: str) -> str:
    """
    자연어 문장에서 intent 추측
    - 회원 / 주문 / 메모 / 후원수당 카테고리 구분
    """
    text = (text or "")

    # 회원
    if any(k in text for k in ["회원등록", "등록", "추가"]):
        return "register_member"
    if any(k in text for k in ["수정", "변경", "업데이트"]):
        return "update_member"
    if any(k in text for k in ["삭제", "지워", "제거"]):
        return "delete_member"
    if any(k in text for k in ["조회", "찾아", "검색", "알려줘"]):
        return "find_member"

    # 주문
    if "주문" in text and "저장" in text:
        return "save_order"
    if "주문" in text and any(k in text for k in ["조회", "찾아", "검색"]):
        return "find_order"

    # 메모 / 일지
    if any(k in text for k in ["상담일지", "개인일지", "활동일지"]):
        return "save_memo"
    if "메모" in text and any(k in text for k in ["조회", "검색", "찾아"]):
        return "find_memo"

    # 후원수당
    if "후원수당" in text and any(k in text for k in ["등록", "추가", "저장"]):
        return "save_commission"
    if "후원수당" in text and any(k in text for k in ["조회", "검색", "알려줘"]):
        return "find_commission"

    return "unknown"



