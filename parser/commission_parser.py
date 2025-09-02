import re
from typing import Dict, Any, Optional

from utils import (
    now_kst,
    get_worksheet,
)




# ======================================================================================
# ✅ 날짜 처리 파서
# ======================================================================================
def process_date(raw: Optional[str]) -> str:
    """
    '오늘/어제/내일', YYYY-MM-DD, 2025.8.7 / 2025/08/07 등 → YYYY-MM-DD
    """
    from datetime import timedelta
    try:
        if not raw:
            return now_kst().strftime("%Y-%m-%d")
        s = raw.strip()
        if "오늘" in s:
            return now_kst().strftime("%Y-%m-%d")
        if "어제" in s:
            return (now_kst() - timedelta(days=1)).strftime("%Y-%m-%d")
        if "내일" in s:
            return (now_kst() + timedelta(days=1)).strftime("%Y-%m-%d")
        m = re.search(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})", s)
        if m:
            y, mth, d = m.groups()
            return f"{int(y):04d}-{int(mth):02d}-{int(d):02d}"
    except Exception:
        pass
    return now_kst().strftime("%Y-%m-%d")


# ======================================================================================
# ✅ 후원수당 데이터 정리
# ======================================================================================
def clean_commission_data(data: dict) -> dict:
    """
    후원수당 데이터 정리 함수
    (예: 공백 제거, 숫자 변환 등)
    """
    cleaned = {}
    for k, v in data.items():
        if isinstance(v, str):
            cleaned[k] = v.strip()
        else:
            cleaned[k] = v
    return cleaned


# ======================================================================================
# ✅ 후원수당 파서 + 저장
# ======================================================================================
def parse_commission(text: str) -> Dict[str, Any]:
    """
    자연어 문장에서 후원수당 정보를 추출하고 시트에 저장
    예: "홍길동 2025-08-07 좌 10000 우 20000"
    """
    result = {
        "회원명": None,
        "기준일자": process_date("오늘"),
        "합계_좌": 0,
        "합계_우": 0,
    }

    if not text:
        return {"status": "fail", "reason": "입력 문장이 비어있습니다."}

    # 회원명 추출 (첫 단어)
    tokens = text.split()
    if tokens:
        result["회원명"] = tokens[0]

    # 날짜 추출
    date_match = re.search(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2})", text)
    if date_match:
        result["기준일자"] = process_date(date_match.group(1))

    # 좌/우 점수 추출
    left = re.search(r"(?:좌|왼쪽)\s*(\d+)", text)
    right = re.search(r"(?:우|오른쪽)\s*(\d+)", text)
    if left:
        result["합계_좌"] = int(left.group(1))
    if right:
        result["합계_우"] = int(right.group(1))

    # ✅ 시트에 저장
    ws = get_worksheet("후원수당")
    headers = ws.row_values(1)

    row = [result.get(h, "") for h in headers]
    ws.append_row(row, value_input_option="USER_ENTERED")

    return {"status": "success", "data": result}
