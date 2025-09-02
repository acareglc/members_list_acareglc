from typing import List, Dict, Any
from utils.sheets import get_commission_sheet, get_worksheet, safe_update_cell
from parser.commission_parser import clean_commission_data




SHEET_NAME = "후원수당"
COLUMNS = ["지급일자", "회원명", "후원수당", "비고"]


# ======================================================================================
# ✅ 내부 유틸
# ======================================================================================
def _get_headers(ws) -> List[str]:
    return [h.strip() for h in ws.row_values(1)]

def _ensure_headers(ws):
    headers = _get_headers(ws)
    if not headers:
        ws.append_row(COLUMNS)
        return COLUMNS
    return headers

def _row_to_obj(row: List[str], headers: List[str]) -> Dict[str, Any]:
    obj = {}
    for i, h in enumerate(headers):
        obj[h] = row[i] if i < len(row) else ""
    return obj


# ======================================================================================
# ✅ 후원수당 조회
# ======================================================================================
def find_commission(data: dict):
    sheet = get_commission_sheet()
    회원명 = data.get("회원명")

    if not 회원명:
        return {"error": "회원명이 없습니다."}

    all_rows = sheet.get_all_records()
    results = [row for row in all_rows if str(row.get("회원명", "")).strip() == 회원명]

    return results


# ======================================================================================
# ✅ 후원수당 등록
# ======================================================================================
def register_commission(data: dict) -> bool:
    """
    후원수당 시트에 새로운 데이터를 추가합니다.
    """
    try:
        ws = get_worksheet(SHEET_NAME)
        if not ws:
            return False

        headers = _ensure_headers(ws)

        # 데이터 정리
        data = clean_commission_data(data)

        row_data = [data.get(h, "") for h in headers]
        ws.append_row(row_data, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        print(f"[ERROR] register_commission: {e}")
        return False


# ======================================================================================
# ✅ 후원수당 수정
# ======================================================================================
def update_commission(member: str, date: str, updates: Dict[str, Any]) -> None:
    ws = get_worksheet(SHEET_NAME)
    headers = _ensure_headers(ws)
    vals = ws.get_all_values()

    try:
        idx_date = headers.index("지급일자")
        idx_member = headers.index("회원명")
    except ValueError:
        raise ValueError("후원수당 시트에 '지급일자' 또는 '회원명' 헤더가 없습니다.")

    target_row = None
    for i, r in enumerate(vals[1:], start=2):
        if len(r) > max(idx_date, idx_member) and r[idx_date].strip() == date and r[idx_member].strip() == member:
            target_row = i
            break

    if not target_row:
        raise ValueError(f"'{member}'의 {date} 지급 내역을 찾을 수 없습니다.")

    for field, value in updates.items():
        if field not in headers:
            continue
        col = headers.index(field) + 1
        safe_update_cell(ws, target_row, col, value, clear_first=True)


# ======================================================================================
# ✅ 후원수당 삭제
# ======================================================================================
def delete_commission(회원명: str, 기준일자: str = None) -> dict:
    sheet = get_commission_sheet()
    all_values = sheet.get_all_values()
    headers = all_values[0]
    rows = all_values[1:]

    target_indexes = []
    for i, row in enumerate(rows, start=2):
        row_dict = dict(zip(headers, row))
        if row_dict.get("회원명") == 회원명:
            if 기준일자 is None or row_dict.get("지급일자") == 기준일자:
                target_indexes.append(i)

    if not target_indexes:
        return {"message": "삭제할 데이터가 없습니다."}

    for idx in reversed(target_indexes):
        sheet.delete_rows(idx)

    return {"message": f"{len(target_indexes)}건 삭제 완료"}
