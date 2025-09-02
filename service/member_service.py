import gspread
from flask import jsonify

from utils import (
    clean_tail_command, clean_value_expression, remove_spaces,
    get_member_sheet, safe_update_cell, delete_row,
)

from parser.field_map import field_map



# ==============================
# 회원 등록 (Create)
# ==============================
def register_member(name: str, number: str, phone: str) -> bool:
    """
    DB 시트에 새로운 회원을 등록
    예: register_member("홍길동", "123456", "010-1234-5678")
    """
    sheet = get_member_sheet()
    headers = sheet.row_values(1)

    data = {
        "회원명": name,
        "회원번호": number,
        "휴대폰번호": phone,
    }

    # header 순서에 맞춰서 값 넣기
    row = [data.get(h, "") for h in headers]
    sheet.append_row(row, value_input_option="USER_ENTERED")
    return True


# ==============================
# 회원 조회 (Read)
# ==============================
def find_member(name: str):
    """
    DB 시트에서 회원명으로 회원을 조회
    여러 건일 수 있으므로 list 반환
    예: [{"회원명": "홍길동", "회원번호": "123456", "휴대폰번호": "010-1234-5678"}]
    """
    sheet = get_member_sheet()
    rows = sheet.get_all_records()

    result = []
    for row in rows:
        if str(row.get("회원명", "")).strip() == str(name).strip():
            result.append(row)
    return result


# ==============================
# 회원 수정 (Update)
# ==============================
def update_member(name: str, updates: dict) -> bool:
    """
    특정 회원의 여러 필드 값을 수정
    예: update_member("홍길동", {"주소": "부산", "휴대폰번호": "010-0000-0000"})
    """
    sheet = get_member_sheet()
    headers = sheet.row_values(1)
    rows = sheet.get_all_records()

    updated = False
    for i, row in enumerate(rows, start=2):  # 2행부터 데이터 시작
        if str(row.get("회원명", "")).strip() == str(name).strip():
            for field, value in updates.items():
                if field in headers:
                    col_idx = headers.index(field) + 1
                    safe_update_cell(sheet, i, col_idx, value)
                    updated = True
            break
    return updated


# ==============================
# 회원 삭제 (Delete)
# ==============================
def delete_member(name: str) -> bool:
    """
    DB 시트에서 특정 회원 전체 행 삭제
    예: delete_member("홍길동")
    """
    sheet = get_member_sheet()
    rows = sheet.get_all_records()

    for i, row in enumerate(rows, start=2):  # 2행부터 데이터 시작
        if str(row.get("회원명", "")).strip() == str(name).strip():
            sheet.delete_rows(i)
            return True
    return False


# ==============================
# 회원명 텍스트 탐색 (보정용)
# ==============================
def find_member_in_text(text: str) -> str | None:
    """
    입력 문장에서 DB 시트의 회원명을 탐색하여 반환
    - 여러 명이 매칭되면 긴 이름 우선 반환
    - 없으면 None
    """
    if not text:
        return None

    sheet = get_member_sheet()
    member_names = sheet.col_values(1)[1:]  # 첫 행은 헤더 제외

    # 긴 이름부터 매칭되도록 정렬 (예: '김철수' > '김')
    member_names = sorted([n.strip() for n in member_names if n], key=len, reverse=True)

    for name in member_names:
        if name in text:
            return name
    return None


def find_member_internal(name: str = "", number: str = "") -> list[dict]:
    sheet = get_member_sheet()
    records = sheet.get_all_records()

    results = []
    name = (name or "").strip().lower()
    number = (number or "").strip()

    print(f"[DEBUG] 찾는 회원명: '{name}', 회원번호: '{number}'")

    for row in records:
        member_name = str(row.get("회원명", "")).strip().lower()
        member_number = str(row.get("회원번호", "")).strip()
        print(f"[DEBUG] 비교 대상 회원명: '{member_name}', 회원번호: '{member_number}'")

        if name and name in member_name:
            print(f"[MATCH] 이름 매칭됨 → {row}")
            results.append(row)
            continue

        if number and number == member_number:
            print(f"[MATCH] 번호 매칭됨 → {row}")
            results.append(row)

    return results




def clean_member_data(data: dict) -> dict:
    """
    회원 데이터 전처리 함수 (기본 구현)
    - 문자열이면 strip() 처리
    - None 은 "" 로 변환
    - 불필요한 공백 제거
    """
    if not data:
        return {}

    cleaned = {}
    for k, v in data.items():
        if isinstance(v, str):
            cleaned[k] = v.strip()
        elif v is None:
            cleaned[k] = ""
        else:
            cleaned[k] = v
    return cleaned



def register_member_internal(data: dict) -> bool:
    """
    내부 회원 등록 함수
    - data 딕셔너리를 받아 DB 시트에 바로 저장
    - headers 순서에 맞게 row 생성 후 append_row

    예시 data:
    {
        "회원명": "홍길동",
        "회원번호": "123456",
        "휴대폰번호": "010-1111-2222",
        "주소": "서울"
    }
    """
    sheet = get_member_sheet()
    headers = sheet.row_values(1)

    # 데이터 전처리
    from service.member_service import clean_member_data
    cleaned = clean_member_data(data)

    # header 순서에 맞게 값 채우기
    row = [cleaned.get(h, "") for h in headers]

    try:
        sheet.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        print(f"[ERROR] register_member_internal: {e}")
        return False




def update_member_internal(요청문):
    try:
        # ... 파싱 및 시트 업데이트 로직 ...
        return jsonify({
            "status": "success",
            "message": f"요청 처리 완료: {요청문}"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500





def delete_member_internal(name: str):
    """
    회원명 기준으로 DB 시트에서 해당 행 삭제
    """
    if not name:
        return {"error": "회원명이 필요합니다."}, 400

    sheet = get_member_sheet()
    rows = sheet.get_all_records()

    for i, row in enumerate(rows):
        if row.get("회원명", "").strip() == name:
            delete_row(sheet, i + 2)  # 헤더 제외 +2
            return {"message": f"{name}님의 회원 정보가 삭제되었습니다."}, 200

    return {"error": f"{name} 회원을 찾을 수 없습니다."}, 404





def delete_member_internal(name: str):
    """
    회원명 기준으로 DB 시트에서 해당 회원 전체 행 삭제
    """
    if not name:
        return {"error": "회원명이 필요합니다."}, 400

    sheet = get_member_sheet()
    rows = sheet.get_all_records()

    for i, row in enumerate(rows):
        if row.get("회원명", "").strip() == name:
            delete_row(sheet, i + 2)  # 헤더 제외
            return {"message": f"{name}님의 회원 정보가 삭제되었습니다."}, 200

    return {"error": f"{name} 회원을 찾을 수 없습니다."}, 404


def delete_member_field_nl_internal(text: str, fields: list):
    """
    자연어 요청 기반으로 특정 회원의 일부 필드만 삭제
    ex: "홍길동 휴대폰번호 삭제"
    """
    if not text or not fields:
        return {"error": "요청문 또는 필드가 필요합니다."}, 400

    sheet = get_member_sheet()
    rows = sheet.get_all_records()

    # 회원명 추출
    name = None
    for row in rows:
        if str(row.get("회원명", "")) in text:
            name = row.get("회원명")
            break

    if not name:
        return {"error": "회원명을 찾을 수 없습니다."}, 404

    headers = sheet.row_values(1)

    # 대상 행 찾기
    target_row = None
    row_index = None
    for i, row in enumerate(rows, start=2):
        if row.get("회원명") == name:
            target_ro_



