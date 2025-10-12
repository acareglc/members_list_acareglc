# =================================================
# 표준 라이브러리
# =================================================
import re
import json
import traceback
import unicodedata
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# =================================================
# 외부 라이브러리
# =================================================
import requests
import gspread
from gspread.exceptions import WorksheetNotFound, APIError

# =================================================
# 프로젝트: config
# =================================================
from config import MEMBERSLIST_API_URL, SHEET_KEY, GOOGLE_SHEET_TITLE

# =================================================
# 프로젝트: utils (시트/검색/공통 기능)
# =================================================
from utils import (
    # 날짜/시간
    now_kst, process_order_date, parse_dt,

    # 문자열 정리
    clean_content, clean_tail_command, clean_value_expression,
    remove_spaces, build_member_query,

    # 시트 접근
    get_sheet, get_worksheet, get_rows_from_sheet,
    get_member_sheet, 
    get_counseling_sheet, get_personal_memo_sheet,
    get_activity_log_sheet, get_commission_sheet,
    safe_update_cell, delete_row,

    # 검색
    find_all_members_from_sheet, fallback_natural_search,
    is_match, match_condition,

    get_order_sheet, 
)






# =================================================
# 회원 서비스
# =================================================
def register_member(name: str, number: str, phone: str) -> bool:
    sheet = get_member_sheet()
    headers = sheet.row_values(1)
    data = {"회원명": name, "회원번호": number, "휴대폰번호": phone}
    row = [data.get(h, "") for h in headers]
    sheet.append_row(row, value_input_option="USER_ENTERED")
    return True


def find_member(name: str):
    sheet = get_member_sheet()
    rows = sheet.get_all_records()
    return [row for row in rows if str(row.get("회원명", "")).strip() == str(name).strip()]


def update_member(name: str, updates: dict) -> bool:
    sheet = get_member_sheet()
    headers = sheet.row_values(1)
    rows = sheet.get_all_records()
    for i, row in enumerate(rows, start=2):
        if str(row.get("회원명", "")).strip() == str(name).strip():
            for field, value in updates.items():
                if field in headers:
                    col_idx = headers.index(field) + 1
                    safe_update_cell(sheet, i, col_idx, value)
            return True
    return False


def delete_member(name: str) -> bool:
    sheet = get_member_sheet()
    rows = sheet.get_all_records()
    for i, row in enumerate(rows, start=2):
        if str(row.get("회원명", "")).strip() == str(name).strip():
            sheet.delete_rows(i)
            return True
    return False


def normalize_text(s) -> str:
    if s is None:
        return ""
    return unicodedata.normalize("NFC", str(s).strip())


def find_member_internal(name: str = "", number: str = "", code: str = "", phone: str = "", special: str = ""):
    rows = get_rows_from_sheet("DB")
    results = []
    name, number, code, phone, special = map(normalize_text, [name, number, code, phone, special])
    for row in rows:
        if (
            (name and normalize_text(row.get("회원명", "")) == name) or
            (number and normalize_text(row.get("회원번호", "")) == number) or
            (code and normalize_text(row.get("코드", "")) == code) or
            (phone and normalize_text(row.get("휴대폰번호", "")) == phone) or
            (special and normalize_text(row.get("특수번호", "")) == special)
        ):
            results.append(row)
    return results


def clean_member_data(data: dict) -> dict:
    if not data:
        return {}
    cleaned = {}
    for k, v in data.items():
        if isinstance(v, str): cleaned[k] = v.strip()
        elif v is None: cleaned[k] = ""
        else: cleaned[k] = v
    return cleaned


def register_member_internal(name: str, number: str = "", phone: str = ""):
    sheet = get_member_sheet()
    headers = sheet.row_values(1)
    rows = sheet.get_all_records()

    # ✅ 기존 회원 여부 확인
    for row in rows:
        # ⚠️ 반드시 str()로 감싸야 int → 문자열 변환
        row_name = str(row.get("회원명") or "").strip()
        row_number = str(row.get("회원번호") or "").strip()

        if name == row_name and number and number == row_number:
            return {
                "status": "exists",
                "message": f"{name} ({number})님은 이미 등록된 회원입니다.",
                "data": row
            }

        if number and number == row_number and name != row_name:
            return {
                "status": "error",
                "message": f"⚠️ 회원번호 {number}는 이미 '{row_name}'님에게 등록되어 있습니다."
            }

    # ✅ 신규 등록
    new_row = [""] * len(headers)
    if "회원명" in headers:
        new_row[headers.index("회원명")] = name
    if "회원번호" in headers and number:
        new_row[headers.index("회원번호")] = number
    if "휴대폰번호" in headers and phone:
        new_row[headers.index("휴대폰번호")] = phone

    sheet.insert_row(new_row, 2)
    return {
        "status": "created",
        "message": f"{name} 회원 신규 등록 완료",
        "data": {
            "회원명": name,
            "회원번호": number,
            "휴대폰번호": phone
        }
    }


def update_member_internal(요청문, 회원명=None, 필드=None, 값=None):
    try:
        ws = get_member_sheet()
        if not 회원명:
            m = re.match(r"([가-힣]{2,4})", 요청문)
            if m: 회원명 = m.group(1)
        if not 회원명:
            return {"status": "error", "message": "❌ 회원명을 찾을 수 없습니다.", "http_status": 400}
        if 필드 and 값:
            headers = ws.row_values(1)
            if 필드 not in headers:
                return {"status": "error", "message": f"❌ 시트에 '{필드}' 컬럼이 없습니다.", "http_status": 400}
            rows = ws.get_all_records()
            target_row = None
            for idx, row in enumerate(rows, start=2):
                if row.get("회원명") == 회원명: target_row = idx; break
            if not target_row:
                return {"status": "error", "message": f"❌ '{회원명}' 회원을 찾을 수 없습니다.", "http_status": 404}
            col_idx = headers.index(필드) + 1
            ws.update_cell(target_row, col_idx, 값)
            return {"status": "success", "message": f"✅ {회원명}님의 {필드}가 '{값}'으로 수정되었습니다.", "http_status": 200}
        return {"status": "success", "message": f"요청 처리 완료: {요청문}", "http_status": 200}
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"status": "error", "message": str(e), "http_status": 500}


def delete_member_internal(name, member_number):
    if not name:
        return {"error": "회원명이 필요합니다."}, 400
    sheet = get_member_sheet()
    rows = sheet.get_all_records()
    headers = sheet.row_values(1)
    for i, row in enumerate(rows, start=2):
        if row.get("회원명", "").strip() == name:
            backup_sheet = get_worksheet("백업")
            if not backup_sheet:
                return {"error": "백업 시트를 찾을 수 없습니다."}, 500
            backup_row = [row.get(h, "") for h in headers]
            backup_sheet.insert_row(backup_row, 2)
            delete_row(sheet, i)
            return {"message": f"{name}님의 회원 정보가 '백업' 시트에 저장된 후 삭제되었습니다."}, 200
    return {"error": f"{name} 회원을 찾을 수 없습니다."}, 404


def delete_member_field_nl_internal(text: str, fields: list = None):
    sheet = get_member_sheet()
    rows = sheet.get_all_records()
    headers = sheet.row_values(1)
    name = None
    for row in rows:
        if str(row.get("회원명", "")) in text: name = row.get("회원명"); break
    if not name: return {"error": "회원명을 찾을 수 없습니다."}, 404
    if text.strip().startswith(name) and text.strip().endswith("삭제"):
        return {"error": "⚠️ 회원 전체 삭제는 별도 API(/delete_member)를 사용하세요."}, 400
    delete_keywords = ["삭제", "삭제해줘", "비워", "없애줘", "지워줘"]
    parts = split_to_parts(text)
    has_delete_kw = any(remove_spaces(dk) in [remove_spaces(p) for p in parts] for dk in delete_keywords)
    if not has_delete_kw: return {"error": "삭제 명령이 포함되어야 합니다."}, 400
    matched_fields = []
    for alias, canonical in field_map.items():
        if remove_spaces(alias) in [remove_spaces(p) for p in parts]:
            if canonical in headers and canonical not in matched_fields:
                matched_fields.append(canonical)
    if fields:
        for f in fields:
            if f in headers and f not in matched_fields:
                matched_fields.append(f)
    if not matched_fields: return {"error": "삭제할 필드를 찾을 수 없습니다."}, 400
    protected_fields = {"회원명", "회원번호"}
    if any(f in protected_fields for f in matched_fields):
        return {"error": "⚠️ 회원명, 회원번호는 삭제 불가 필드입니다."}, 400
    target_row = None
    for i, row in enumerate(rows, start=2):
        if row.get("회원명") == name: target_row = i; break
    if not target_row: return {"error": f"{name} 회원을 찾을 수 없습니다."}, 404
    for field in matched_fields:
        col_index = headers.index(field) + 1
        sheet.update_cell(target_row, col_index, "")
    return {"message": f"{name}님의 {', '.join(matched_fields)} 필드가 삭제되었습니다.", "deleted_fields": matched_fields}, 200


def process_member_query(user_input: str):
    processed = build_member_query(user_input)
    search_key = processed["query"]
    conditions = parse_conditions(search_key)
    sheet = get_member_sheet()
    records = sheet.get_all_records()
    results = []
    for row in records:
        match = True
        for field, value in conditions.items():
            cell_value = str(row.get(field, "")).strip()
            if field == "코드": cell_value = cell_value.upper()
            if cell_value != value: match = False; break
        if match: results.append(row)
    return {"original": user_input, "processed": search_key, "conditions": conditions, "results": results}

# =================================================
# 메모 서비스
# =================================================
def save_memo(sheet_name: str, member_name: str, content: str) -> bool:
    if not member_name or not content: raise ValueError("회원명과 내용은 필수")
    if sheet_name == "상담일지": sheet = get_counseling_sheet()
    elif sheet_name == "개인일지": sheet = get_personal_memo_sheet()
    elif sheet_name == "활동일지": sheet = get_activity_log_sheet()
    else: raise ValueError(f"지원하지 않는 일지: {sheet_name}")
    ts = now_kst().strftime("%Y-%m-%d %H:%M")
    sheet.insert_row([ts, member_name.strip(), content.strip()], index=2)
    return True


def find_memo(keyword: str, sheet_name: str = "상담일지") -> list:
    try:
        sheet = get_worksheet(sheet_name)
        if not sheet: return []
        all_records = sheet.get_all_records()
        return [row for row in all_records if keyword in " ".join(str(v) for v in row.values())]
    except Exception as e:
        print(f"[ERROR] find_memo 오류: {e}")
        return []


def search_in_sheet(sheet_name, keywords, search_mode="any", start_date=None, end_date=None, limit=20):
    sheet = get_worksheet(sheet_name)
    rows = sheet.get_all_values()
    if not rows or len(rows[0]) < 3: return [], False
    records, results = rows[1:], []
    for row in records:
        if len(row) < 3: continue
        작성일자, 회원명, 내용 = row[0], row[1], row[2]
        작성일_dt = parse_dt(작성일자)
        if 작성일_dt is None: continue
        if start_date and 작성일_dt < start_date: continue
        if end_date and 작성일_dt > (end_date + timedelta(days=1) - timedelta(seconds=1)): continue
        if match_condition(f"{회원명} {내용}", keywords, search_mode):
            results.append({"작성일자": 작성일자, "회원명": 회원명, "내용": 내용, "_작성일_dt": 작성일_dt})
    results.sort(key=lambda x: x["_작성일_dt"], reverse=True)
    for r in results: r.pop("_작성일_dt", None)
    has_more = len(results) > limit
    return results[:limit], has_more




# =================================================
# 주문 서비스
# =================================================



def handle_order_save(data: dict):
    sheet = get_worksheet("제품주문")
    if not sheet: raise Exception("제품주문 시트를 찾을 수 없습니다.")
    order_date = process_order_date(data.get("주문일자", ""))
    row = [
        order_date, data.get("회원명", ""), data.get("회원번호", ""), data.get("휴대폰번호", ""),
        data.get("제품명", ""), float(data.get("제품가격", 0)), float(data.get("PV", 0)),
        data.get("결재방법", ""), data.get("주문자_고객명", ""), data.get("주문자_휴대폰번호", ""),
        data.get("배송처", ""), data.get("수령확인", "")
    ]
    values = sheet.get_all_values()
    if not values:
        headers = ["주문일자", "회원명", "회원번호", "휴대폰번호", "제품명", "제품가격", "PV", "결재방법",
                   "주문자_고객명", "주문자_휴대폰번호", "배송처", "수령확인"]
        sheet.append_row(headers)
    for existing in values[1:]:
        if existing[0] == order_date and existing[1] == data.get("회원명") and existing[4] == data.get("제품명"):
            print("⚠️ 이미 동일한 주문이 존재하여 저장하지 않음")
            return
    sheet.insert_row(row, index=2)









def handle_product_order(text: str, member_name: str):
    try:
        from parser import parse_order_text
        parsed = parse_order_text(text)
        parsed["회원명"] = member_name
        handle_order_save(parsed)
        return {"message": f"{member_name}님의 제품주문 저장이 완료되었습니다."}
    except Exception as e:
        return {"error": f"제품주문 처리 중 오류 발생: {str(e)}"}


def save_order_to_sheet(order: dict) -> bool:
    try:
        sheet = get_order_sheet()
        headers = sheet.row_values(1)
        row_data = [order.get(h, "") for h in headers]
        append_row(sheet, row_data)
        return True
    except Exception as e:
        print(f"[ERROR] 주문 저장 중 오류: {e}")
        return False


def find_order(member_name: str = "", product: str = "") -> list[dict]:
    sheet = get_order_sheet()
    db = sheet.get_all_values()
    if not db or len(db) < 2: return []
    headers, rows = db[0], db[1:]
    return [dict(zip(headers, row)) for row in rows if (member_name and row[headers.index("회원명")] == member_name) or (product and row[headers.index("제품명")] == product)]


def register_order(order_data: dict) -> bool:
    sheet = get_order_sheet()
    headers = sheet.row_values(1)
    row = {h: "" for h in headers}
    for k, v in order_data.items():
        if k in headers: row[k] = str(v)
    values = [row.get(h, "") for h in headers]
    sheet.append_row(values)
    return True


def update_order(member_name: str, updates: dict) -> bool:
    sheet = get_order_sheet()
    headers = sheet.row_values(1)
    values = sheet.get_all_values()
    member_col = headers.index("회원명") + 1
    target_row = None
    for i, row in enumerate(values[1:], start=2):
        if len(row) >= member_col and row[member_col - 1] == member_name.strip():
            target_row = i; break
    if not target_row: raise ValueError(f"'{member_name}' 회원의 주문을 찾을 수 없습니다.")
    for field, value in updates.items():
        if field in headers:
            sheet.update_cell(target_row, headers.index(field) + 1, str(value))
    return True


def delete_order(member_name: str) -> bool:
    sheet = get_order_sheet()
    values = sheet.get_all_values()
    headers = values[0] if values else []
    member_col = headers.index("회원명") if "회원명" in headers else None
    if member_col is None: raise ValueError("주문 시트에 '회원명' 컬럼이 없습니다.")
    for i, row in enumerate(values[1:], start=2):
        if len(row) > member_col and row[member_col] == member_name.strip():
            delete_row(sheet, i); return True
    return False


def delete_order_by_row(row: int):
    sheet = get_order_sheet()
    delete_row(sheet, row)


def clean_order_data(order: dict) -> dict:
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in order.items()}

# =================================================
# 후원수당 서비스
# =================================================
def find_commission(data: dict):
    sheet = get_commission_sheet()
    rows = sheet.get_all_records()
    results = []
    for row in rows:
        match = True
        for k, v in data.items():
            if v and str(row.get(k, "")).strip() != str(v).strip():
                match = False; break
        if match: results.append(row)
    return results


def register_commission(data: dict) -> bool:
    sheet = get_commission_sheet()
    headers = sheet.row_values(1)
    row = [data.get(h, "") for h in headers]
    append_row(sheet, row)
    return True


def update_commission(member: str, date: str, updates: Dict[str, Any]) -> None:
    sheet = get_commission_sheet()
    headers = sheet.row_values(1)
    rows = sheet.get_all_records()
    for i, row in enumerate(rows, start=2):
        if row.get("회원명") == member and row.get("기준일자") == date:
            for k, v in updates.items():
                if k in headers:
                    sheet.update_cell(i, headers.index(k) + 1, v)
            return


def delete_commission(회원명: str, 기준일자: str = None) -> dict:
    sheet = get_commission_sheet()
    rows = sheet.get_all_records()
    headers = sheet.row_values(1)
    for i, row in enumerate(rows, start=2):
        if row.get("회원명") == 회원명 and (기준일자 is None or row.get("기준일자") == 기준일자):
            delete_row(sheet, i)
            return {"status": "success", "message": f"{회원명}의 후원수당 기록이 삭제되었습니다."}
    return {"status": "error", "message": "해당 조건에 맞는 후원수당 기록이 없습니다."}


def clean_commission_data(data: dict) -> dict:
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in data.items()}


# service/member_service.py

def update_member_info(name: str, field: str, value: str) -> bool:
    """
    시트에서 회원 정보를 업데이트하는 함수
    """
    print(f"[UPDATE] {name}님의 {field}를 {value}로 수정합니다.")
    # TODO: 실제 시트 수정 로직 구현
    return True


