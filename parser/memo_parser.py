import re
from typing import Tuple, Optional, Dict

from utils import now_kst, get_worksheet



# ======================================================================================
# ✅ 메모 요청 파서
# ======================================================================================
def parse_request_line(text: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    자연어 문장에서 메모 저장 요청 파싱
    예: '이태수 상담일지 저장 오늘은 비가 옵니다'
    반환: (회원명, 시트명, 액션, 내용)
    """
    if not text or not text.strip():
        return None, None, None, None

    s = text.strip()
    m = re.match(
        r"^\s*(\S+)\s*(상담\s*일지|개인\s*일지|활동\s*일지)\s*(저장|기록|입력)\s*(.*)$",
        s,
    )
    if m:
        member, sheet_raw, action, content = m.groups()
        sheet = sheet_raw.replace(" ", "")
        return member, sheet, action, content

    # fallback: 단순 분리
    parts = s.split(maxsplit=3)
    if len(parts) < 3:
        return None, None, None, None

    member, sheet, action = parts[0], parts[1].replace(" ", ""), parts[2]
    content = parts[3] if len(parts) > 3 else ""
    return member, sheet, action, content


# ======================================================================================
# ✅ 메모 파서 + 저장
# ======================================================================================
def parse_memo(text: str) -> Dict[str, str]:
    """
    자연어 문장에서 메모(상담일지/개인일지/활동일지)를 추출 후 시트에 저장
    예: "이태수 상담일지 저장 오늘은 비가 옵니다"
    """
    member, sheet, action, content = parse_request_line(text)
    if not member or not sheet or not content:
        return {"status": "fail", "reason": "입력 문장에서 필요한 정보를 추출하지 못했습니다."}

    # ✅ 시트명 매핑
    sheet_map = {
        "상담일지": "상담일지",
        "개인일지": "개인메모",   # 내부적으로는 개인메모 시트
        "활동일지": "활동일지",
    }
    target_sheet_name = sheet_map.get(sheet)
    if not target_sheet_name:
        return {"status": "fail", "reason": f"지원하지 않는 시트명: {sheet}"}

    # ✅ 시트 불러오기
    ws = get_worksheet(target_sheet_name)

    # ✅ 행 구성 (날짜, 회원명, 내용)
    row = [now_kst(), member, content]
    ws.append_row(row, value_input_option="USER_ENTERED")

    return {
        "status": "success",
        "sheet": target_sheet_name,
        "member": member,
        "content": content,
    }
