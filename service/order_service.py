import re
import json
from typing import Dict, Any

from utils import process_order_date, parse_order_from_text, get_product_order_sheet




# ===============================================
# ✅ 외부 API 연동
# ===============================================
def addOrders(payload: dict) -> dict:
    """
    외부 MEMBERSLIST API에 주문 JSON을 전송합니다.
    """
    resp = requests.post(MEMBERSLIST_API_URL, json=payload)
    resp.raise_for_status()
    return resp.json()









# ===============================================
# ✅ 주문 시트 저장
# ===============================================
def handle_order_save(data: dict):
    """
    파싱된 주문 데이터를 Google Sheets '제품주문' 시트에 저장합니다.
    - 중복 체크 (회원명 + 제품명 + 주문일자 기준)
    """
    sheet = get_worksheet("제품주문")
    if not sheet:
        raise Exception("제품주문 시트를 찾을 수 없습니다.")

    order_date = process_order_date(data.get("주문일자", ""))
    row = [
        order_date,
        data.get("회원명", ""),
        data.get("회원번호", ""),
        data.get("휴대폰번호", ""),
        data.get("제품명", ""),
        float(data.get("제품가격", 0)),
        float(data.get("PV", 0)),
        data.get("결재방법", ""),
        data.get("주문자_고객명", ""),
        data.get("주문자_휴대폰번호", ""),
        data.get("배송처", ""),
        data.get("수령확인", "")
    ]

    values = sheet.get_all_values()
    if not values:
        headers = [
            "주문일자", "회원명", "회원번호", "휴대폰번호",
            "제품명", "제품가격", "PV", "결재방법",
            "주문자_고객명", "주문자_휴대폰번호", "배송처", "수령확인"
        ]
        sheet.append_row(headers)

    for existing in values[1:]:
        if (existing[0] == order_date and
            existing[1] == data.get("회원명") and
            existing[4] == data.get("제품명")):
            print("⚠️ 이미 동일한 주문이 존재하여 저장하지 않음")
            return

    sheet.insert_row(row, index=2)


# ===============================================
# ✅ 제품 주문 처리
# ===============================================
def handle_product_order(text: str, member_name: str):
    """
    자연어 문장을 파싱 후 제품 주문을 저장합니다.
    """
    try:
        from parser.parser.order_parser import parse_order_text
        parsed = parse_order_text(text)
        parsed["회원명"] = member_name
        handle_order_save(parsed)
        return jsonify({"message": f"{member_name}님의 제품주문 저장이 완료되었습니다."})
    except Exception as e:
        return jsonify({"error": f"제품주문 처리 중 오류 발생: {str(e)}"}), 500


# ===============================================
# ✅ 주문 시트 직접 저장
# ===============================================
def save_order_to_sheet(order: dict) -> bool:
    """
    단일 주문 데이터를 '제품주문' 시트에 직접 저장합니다.
    """
    try:
        sheet = get_order_sheet()
        headers = sheet.row_values(1)
        row_data = [order.get(h, "") for h in headers]
        append_row(sheet, row_data)
        return True
    except Exception as e:
        print(f"[ERROR] 주문 저장 중 오류: {e}")
        return False


# ===============================================
# ✅ 주문 조회
# ===============================================
def find_order(member_name: str = "", product: str = "") -> list[dict]:
    """
    주문 시트에서 회원명 또는 제품명으로 조회합니다.
    """
    sheet = get_order_sheet()
    db = sheet.get_all_values()
    if not db or len(db) < 2:
        return []
    headers, rows = db[0], db[1:]
    matched = []
    for row in rows:
        row_dict = dict(zip(headers, row))
        if member_name and row_dict.get("회원명") == member_name.strip():
            matched.append(row_dict)
        elif product and row_dict.get("제품명") == product.strip():
            matched.append(row_dict)
    return matched


# ===============================================
# ✅ 주문 등록
# ===============================================
def register_order(order_data: dict) -> bool:
    """
    주문 데이터를 직접 등록합니다.
    """
    sheet = get_order_sheet()
    headers = sheet.row_values(1)
    row = {h: "" for h in headers}
    for k, v in order_data.items():
        if k in headers:
            row[k] = str(v)
    values = [row.get(h, "") for h in headers]
    sheet.append_row(values)
    return True


# ===============================================
# ✅ 주문 수정
# ===============================================
def update_order(member_name: str, updates: dict) -> bool:
    """
    특정 회원의 주문 정보를 수정합니다.
    """
    sheet = get_order_sheet()
    headers = sheet.row_values(1)
    values = sheet.get_all_values()
    member_col = headers.index("회원명") + 1
    target_row = None
    for i, row in enumerate(values[1:], start=2):
        if len(row) >= member_col and row[member_col - 1] == member_name.strip():
            target_row = i
            break
    if not target_row:
        raise ValueError(f"'{member_name}' 회원의 주문을 찾을 수 없습니다.")
    for field, value in updates.items():
        if field not in headers:
            continue
        col = headers.index(field) + 1
        safe_update_cell(sheet, target_row, col, value, clear_first=True)
    return True


# ===============================================
# ✅ 주문 삭제
# ===============================================
def delete_order(member_name: str) -> bool:
    """
    특정 회원의 주문 레코드를 삭제합니다.
    """
    sheet = get_order_sheet()
    headers = sheet.row_values(1)
    values = sheet.get_all_values()
    member_col = headers.index("회원명") + 1
    target_row = None
    for i, row in enumerate(values[1:], start=2):
        if len(row) >= member_col and row[member_col - 1] == member_name.strip():
            target_row = i
            break
    if not target_row:
        raise ValueError(f"'{member_name}' 회원의 주문을 찾을 수 없습니다.")
    sheet.delete_rows(target_row)
    return True


# ===============================================
# ✅ 주문 삭제 (행 번호 기준)
# ===============================================
def delete_order_by_row(row: int):
    """
    행 번호로 주문 레코드를 삭제합니다.
    """
    delete_row("제품주문", row)


# ===============================================
# ✅ 주문 데이터 정리
# ===============================================
def clean_order_data(order: dict) -> dict:
    """
    주문 dict 데이터를 전처리(clean)합니다.
    """
    if not isinstance(order, dict):
        return {}
    cleaned = {}
    for k, v in order.items():
        if v is None:
            continue
        if isinstance(v, str):
            v = v.strip()
        cleaned[k.strip()] = v
    return cleaned
