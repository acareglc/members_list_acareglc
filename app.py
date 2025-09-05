# ===== stdlib =====
import os
import io
import re
import base64
import traceback
from datetime import datetime, timedelta, timezone

# ===== 3rd party =====
import requests
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

from itertools import chain



# ===== project: config =====
from config import (
    API_URLS, HEADERS,
    GOOGLE_SHEET_TITLE, SHEET_KEY,
    OPENAI_API_KEY, OPENAI_API_URL, MEMBERSLIST_API_URL, openai_client,
    SHEET_MAP,
)

# ===== project: utils =====
from utils.common import (
    now_kst,
    process_order_date,
    remove_josa,
    remove_spaces,
    split_to_parts,
    parse_dt,      
    is_match,       
)
from utils.sheets import (
    get_sheet,
    get_worksheet,
    get_member_sheet,
    get_product_order_sheet,
    get_commission_sheet,
    append_row,
    update_cell,
    safe_update_cell,
    delete_row,
)
from utils.clean_content import clean_content
from utils.http import call_memberslist_add_orders, call_impact_sync
from utils.openai_utils import (
    extract_order_from_uploaded_image,
    
)

from utils import format_memo_results


# ===== parser: member =====
# ===== parser =====
from parser import (
    parse_registration,
    parse_request_and_update,
    parse_natural_query,
    parse_deletion_request,
  
    parse_memo,
    parse_commission,
    guess_intent,
)


from service.member_service import (
    find_member_internal,
    clean_member_data,
    register_member_internal,
    update_member_internal,
    delete_member_internal,
    delete_member_field_nl_internal,
)

# ===== parser: order =====
from parser.order_parser import (
    parse_order_text,
    parse_order_text_rule,
    parse_order_from_text,
)
from service.order_service import (
    addOrders,
    handle_order_save,
    handle_product_order,
    find_order,
    register_order,
    update_order,
    delete_order,
    delete_order_by_row,
    clean_order_data,
    save_order_to_sheet,
)

# ===== parser: memo =====
from parser.memo_parser import (
    parse_memo,
    parse_request_line,
)
from service.memo_service import (
    save_memo,
    find_memo,
    search_in_sheet,
    search_memo_core 
)

# ===== parser: commission =====
from parser.commission_parser import (
    process_date,
    clean_commission_data,
)
from service.commission_service import (
    find_commission,
    register_commission,
    update_commission,
    delete_commission,
)

# ===== parser: intent =====
from parser.intent_parser import guess_intent

# ===== field map =====
from parser.field_map import field_map









# ✅ Flask 초기화
app = Flask(__name__)
CORS(app)  # ← 추가

# ✅ 확인용 출력 (선택)
if os.getenv("DEBUG", "false").lower() == "true":
    print("✅ GOOGLE_SHEET_TITLE:", os.getenv("GOOGLE_SHEET_TITLE"))
    print("✅ GOOGLE_SHEET_KEY 존재 여부:", "Yes" if os.getenv("GOOGLE_SHEET_KEY") else "No")



# ✅ 홈 라우트
@app.route("/")
def home():
    """
    홈(Health Check) API
    📌 설명:
    서버가 정상 실행 중인지 확인하기 위한 기본 엔드포인트입니다.
    """

    return "Flask 서버가 실행 중입니다."


# ======================================================================================
# 추가 부분
# ======================================================================================
@app.route("/debug_sheets", methods=["GET"])
def debug_sheets():
    try:
        sheet = get_sheet()
        sheet_names = [ws.title for ws in sheet.worksheets()]

        # ?sheet=DB 파라미터 있으면 해당 시트의 헤더 반환
        target = request.args.get("sheet")
        headers = []
        if target:
            ws = get_worksheet(target)
            headers = ws.row_values(1)

        return jsonify({
            "sheets": sheet_names,
            "headers": headers
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500




# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
# ======================================================================================
# ✅ 회원 조회 (자동 분기)
# ======================================================================================
@app.route("/member_find_auto", methods=["POST"])
def member_find_auto():
    """
    회원 조회 자동 분기 API
    📌 설명:
    - 자연어 기반 요청(text, query 포함) → search_by_natural_language
    - JSON 기반 요청(회원명, 회원번호 포함) → find_member_route
    """
    data = request.get_json(silent=True) or {}

    # 자연어 기반
    if "text" in data or "query" in data:
        return search_by_natural_language()

    # JSON 기반
    if "회원명" in data or "회원번호" in data:
        return find_member_route()

    return jsonify({
        "status": "error",
        "message": "❌ 입력이 올바르지 않습니다. "
                   "자연어는 'text/query', JSON은 '회원명/회원번호'를 포함해야 합니다."
    }), 400



# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
# ======================================================================================
# ✅ 회원 조회 (JSON 전용)
# ======================================================================================
@app.route("/find_member", methods=["POST"])
def find_member_route():
    """
    회원 조회 API (JSON 전용)
    📌 설명:
    회원명 또는 회원번호를 기준으로 DB 시트에서 정보를 조회합니다.
    📥 입력(JSON 예시):
    {
      "회원명": "신금자"
    }
    """
    try:
        data = request.get_json()
        name = data.get("회원명", "").strip()
        number = data.get("회원번호", "").strip()

        if not name and not number:
            return jsonify({"error": "회원명 또는 회원번호를 입력해야 합니다."}), 400

        matched = find_member_internal(name, number)
        if not matched:
            return jsonify({"error": "해당 회원 정보를 찾을 수 없습니다."}), 404

        if len(matched) == 1:
            return jsonify(clean_member_data(matched[0])), 200
        return jsonify([clean_member_data(m) for m in matched]), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    


# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
# ======================================================================================
# ✅ 자연어 기반 회원 검색 API
# ======================================================================================
@app.route("/members/search-nl", methods=["POST"])
def search_by_natural_language():
    """
    회원 자연어 검색 API (자연어 전용)
    📌 설명:
    자연어 문장에서 (필드, 키워드)를 추출하여 DB 시트에서 회원을 검색합니다.
    📥 입력(JSON 예시):
    {
      "query": "계보도 장천수 우측"
    }
    """
    data = request.get_json()
    query = data.get("query")
    if not query:
        return Response("query 파라미터가 필요합니다.", status=400)

    offset = int(data.get("offset", 0))

    field, keyword = parse_natural_query(query)
    if not field or not keyword:
        return Response("자연어에서 검색 필드와 키워드를 찾을 수 없습니다.", status=400)

    try:
        sheet = get_member_sheet()
        records = sheet.get_all_records()

        normalized_field = field.strip()
        normalized_keyword = keyword.strip().lower()
        if normalized_field == "계보도":
            normalized_keyword = normalized_keyword.replace(" ", "")

        filtered = [
            m for m in records
            if normalized_keyword == str(m.get(normalized_field, "")).strip().lower().replace(" ", "")
        ]
        filtered.sort(key=lambda m: m.get("회원명", ""))

        lines = [
            f"{m.get('회원명', '')} (회원번호: {m.get('회원번호', '')}" +
            (f", 연락처: {m.get('휴대폰번호', '')}" if m.get('휴대폰번호', '') else "") +
            ")"
            for m in filtered[offset:offset+40]
        ]

        if offset + 40 < len(filtered):
            lines.append("--- 다음 있음 ---")

        response_text = "\n".join(lines) if lines else "조건에 맞는 회원이 없습니다."
        return Response(response_text, mimetype='text/plain')

    except Exception as e:
        return Response(f"[서버 오류] {str(e)}", status=500)


    


# ======================================================================================
# ✅ 회원 수정
# ======================================================================================
# ======================================================================================
# ✅ 회원 수정 라우트
# ======================================================================================
@app.route("/update_member", methods=["POST"])
@app.route("/updateMember", methods=["POST"])
def update_member_route():
    """
    회원 수정 API
    📌 설명:
    자연어 요청문에서 {필드: 값} 쌍을 추출하여 회원 정보를 수정합니다.
    📥 입력(JSON 예시):
    {
    "요청문": "홍길동 주소 부산 해운대구로 변경"
    }
    """

    try:
        data = request.get_json(force=True)
        요청문 = data.get("요청문", "").strip()

        if not 요청문:
            return jsonify({"error": "요청문이 비어 있습니다."}), 400

        return update_member_internal(요청문)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    



# ======================================================================================
# ✅ JSON 기반 회원 저장/수정 API
# ======================================================================================
@app.route('/save_member', methods=['POST'])
def save_member():

    """
    회원 저장/수정 API
    📌 설명:
    자연어 요청문을 파싱하여 회원을 신규 등록하거나, 기존 회원 정보를 수정합니다.
    📥 입력(JSON 예시):
    {
    "요청문": "홍길동 회원번호 12345 휴대폰 010-1111-2222 주소 서울"
    }
    """

    try:
        req = request.get_json()
        print(f"[DEBUG] 📥 요청 수신: {req}")

        요청문 = req.get("요청문") or req.get("회원명", "")
        if not 요청문:
            return jsonify({"error": "입력 문장이 없습니다"}), 400

        # ✅ 파싱
        name, number, phone, lineage = parse_registration(요청문)
        if not name:
            return jsonify({"error": "회원명을 추출할 수 없습니다"}), 400

        # ✅ 주소 기본값 처리 (iPad 등 환경에서 누락 방지)
        address = req.get("주소") or req.get("address", "")

        # ✅ 시트 접근
        sheet = get_member_sheet()
        headers = [h.strip() for h in sheet.row_values(1)]
        rows = sheet.get_all_records()

        print(f"[DEBUG] 시트 헤더: {headers}")

        # ✅ 기존 회원 여부 확인
        for i, row in enumerate(rows):
            if str(row.get("회원명", "")).strip() == name:
                print(f"[INFO] 기존 회원 '{name}' 발견 → 수정")
                for key, value in {
                    "회원명": name,
                    "회원번호": number,
                    "휴대폰번호": phone,
                    "계보도": lineage,
                    "주소": address
                }.items():
                    if key in headers and value:


                        row_idx = i + 2
                        col_idx = headers.index(key) + 1
                        safe_update_cell(sheet, row_idx, col_idx, value, clear_first=True)


                return jsonify({"message": f"{name} 기존 회원 정보 수정 완료"}), 200

        # ✅ 신규 등록
        print(f"[INFO] 신규 회원 '{name}' 등록")
        new_row = [''] * len(headers)
        for key, value in {
            "회원명": name,
            "회원번호": number,
            "휴대폰번호": phone,
            "계보도": lineage,
            "주소": address
        }.items():
            if key in headers and value:
                new_row[headers.index(key)] = value

        sheet.insert_row(new_row, 2)
        return jsonify({"message": f"{name} 회원 신규 등록 완료"}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500




# ======================================================================================
# ✅ 회원 등록 (라우트)
# ======================================================================================
@app.route("/register_member", methods=["POST"])
def register_member_route():
    """
    회원 등록 API
    📌 설명:
    회원명, 회원번호, 휴대폰번호를 JSON으로 입력받아 신규 등록합니다.
    📥 입력(JSON 예시):
    {
    "회원명": "홍길동",
    "회원번호": "12345",
    "휴대폰번호": "010-1111-2222"
    }
    """

    try:
        data = request.get_json()
        name = data.get("회원명", "").strip()
        number = data.get("회원번호", "").strip()
        phone = data.get("휴대폰번호", "").strip()

        if not name:
            return jsonify({"error": "회원명은 필수 입력 항목입니다."}), 400

        register_member_internal(name, number, phone)
        return jsonify({"message": f"{name}님이 성공적으로 등록되었습니다."}), 201

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    


# ======================================================================================
# ✅ 회원 삭제 API
# ======================================================================================
@app.route('/delete_member', methods=['POST'])
def delete_member_route():
    """
    회원 삭제 API
    📌 설명:
    회원명을 기준으로 해당 회원의 전체 정보를 삭제합니다.
    📥 입력(JSON 예시):
    {
    "회원명": "이판주"
    }
    """

    try:
        name = request.get_json().get("회원명")
        return delete_member_internal(name)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500





# ======================================================================================
# ✅ 자연어 요청 회원 삭제 라우트
# ======================================================================================
@app.route('/delete_member_field_nl', methods=['POST'])
def delete_member_field_nl():
    """
    회원 필드 삭제 API
    📌 설명:
    자연어 문장에서 특정 필드를 추출하여 해당 회원의 필드를 비웁니다.
    📥 입력(JSON 예시):
    {
    "요청문": "이판여 휴대폰번호 삭제"
    }
    """

    try:
        req = request.get_json(force=True)
        text = req.get("요청문", "").strip()

        if not text:
            return jsonify({"error": "요청문을 입력해야 합니다."}), 400

        # 삭제 키워드 체크
        delete_keywords = ["삭제", "삭제해줘", "비워", "비워줘", "초기화", "초기화줘", "없애", "없애줘", "지워", "지워줘"]
        parts = split_to_parts(text)
        has_delete_kw = any(remove_spaces(dk) in [remove_spaces(p) for p in parts] for dk in delete_keywords)
        all_field_keywords = list(chain.from_iterable(field_map.values()))
        has_field_kw = any(remove_spaces(fk) in [remove_spaces(p) for p in parts] for fk in all_field_keywords)

        if not (has_delete_kw and has_field_kw):
            return jsonify({"error": "삭제 명령이 아니거나 필드명이 포함되지 않았습니다."}), 400

        # 매칭된 필드 추출
        matched_fields = []
        for field, keywords in sorted(field_map.items(), key=lambda x: -max(len(k) for k in x[1])):
            for kw in keywords:
                if remove_spaces(kw) in [remove_spaces(p) for p in parts] and field not in matched_fields:
                    matched_fields.append(field)

        return delete_member_field_nl_internal(text, matched_fields)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ======================================================================================
# ✅ 회원 조회
# ======================================================================================



































# ======================================================================================
# ======================================================================================
# ======================================================================================
# ======================================================================================
# ======================================================================================
# ✅ 제품 주문 루틴
# ======================================================================================
# ======================================================================================
# ✅ 제품 주문 루틴
# ======================================================================================
@app.route("/order/auto", methods=["POST"])
def order_auto():
    """
    제품 주문 자동 분기 API
    📌 설명:
    - 이미지 업로드 기반 요청(image, image_url, 파일 포함) → order_upload()
    - 자연어/JSON 기반 요청(text, query, 회원명, 제품명 등) → order_nl()
    """
    data = request.get_json(silent=True) or {}

    # 1️⃣ 이미지 업로드 요청 (form-data or JSON에 image 관련 필드 포함)
    if "image" in request.files or "image_url" in request.form or "image_url" in data:
        return order_upload()

    # 2️⃣ 자연어/JSON 기반 요청
    if "text" in data or "query" in data or "회원명" in data or "제품명" in data:
        return order_nl()

    return jsonify({
        "status": "error",
        "message": "❌ 입력이 올바르지 않습니다. "
                   "이미지 업로드는 'image/image_url', "
                   "자연어는 'text/query', "
                   "JSON은 '회원명/제품명'을 포함해야 합니다."
    }), 400









# 새로운 통합 엔드포인트
@app.route("/order/upload", methods=["POST"])
def order_upload():
    """
    제품 주문 업로드 API (PC/iPad 자동 분기)
    📌 설명:
    - User-Agent 기반으로 PC/iPad 자동 분기
    - 이미지 파일/URL 업로드 → GPT Vision 분석 → JSON 추출 → 시트 저장
    """
    user_agent = request.headers.get("User-Agent", "").lower()
    is_pc = ("windows" in user_agent) or ("macintosh" in user_agent)

    member_name = request.form.get("회원명")
    image_file = request.files.get("image")
    image_url = request.form.get("image_url")

    if not member_name:
        return jsonify({"error": "회원명이 필요합니다."}), 400

    try:
        # 이미지 읽기
        if image_file:
            image_bytes = io.BytesIO(image_file.read())
        elif image_url:
            resp = requests.get(image_url)
            if resp.status_code != 200:
                return jsonify({"error": "이미지 다운로드 실패"}), 400
            image_bytes = io.BytesIO(resp.content)
        else:
            return jsonify({"error": "이미지가 필요합니다."}), 400

        # GPT Vision → JSON
        order_data = extract_order_from_uploaded_image(image_bytes)

        # dict/list 보정
        if isinstance(order_data, dict) and "orders" in order_data:
            orders_list = order_data["orders"]
        elif isinstance(order_data, dict):
            orders_list = [order_data]
        elif isinstance(order_data, list):
            orders_list = order_data
        else:
            return jsonify({"error": "GPT 응답이 올바르지 않음", "raw": order_data}), 500

        # 공통 처리
        for o in orders_list:
            o["결재방법"] = ""
            o["수령확인"] = ""

        # 저장
        addOrders({"회원명": member_name, "orders": orders_list})

        return jsonify({
            "status": "success",
            "mode": "PC" if is_pc else "iPad",
            "회원명": member_name,
            "추출된_JSON": orders_list
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# --------------------------
# 📌 호환용 엔드포인트 (옛 API → 새 API)
# --------------------------

@app.route("/upload_order", methods=["POST"])
def compat_upload_order():
    """옛 API 호환용 → /order/upload로 리다이렉트"""
    return order_upload()

@app.route("/upload_order_pc", methods=["POST"])
def compat_upload_order_pc():
    """옛 API 호환용 → /order/upload로 리다이렉트"""
    return order_upload()

@app.route("/upload_order_ipad", methods=["POST"])
def compat_upload_order_ipad():
    """옛 API 호환용 → /order/upload로 리다이렉트"""
    return order_upload()









# --------------------------
# 📌 자연어/JSON 처리: 새 엔드포인트
# --------------------------
@app.route("/order/nl", methods=["POST"])
def order_nl():
    """
    자연어 및 JSON 기반 주문 처리 API
    📌 기능:
    - 자연어 문장 → 파싱 → 등록/조회/삭제
    - JSON 입력(회원명, 제품명 등) → 등록/수정/삭제/조회
    """
    data = request.get_json(silent=True) or {}

    # --- 자연어 입력 처리 ---
    if "text" in data:
        text = data["text"].strip()
        if "저장" in text:
            parsed = parse_order_text_rule(text)
            save_order_to_sheet(parsed)
            return jsonify({"status": "success", "action": "저장", "parsed": parsed}), 200
        elif "조회" in text:
            parsed = parse_order_text(text)
            matched = find_order(parsed.get("회원명"), parsed.get("제품명"))
            return jsonify([clean_order_data(o) for o in matched]), 200
        elif "삭제" in text:
            parsed = parse_order_text(text)
            member, product = parsed.get("회원명"), parsed.get("제품명")
            if member and product:
                delete_order(member, product)
                return jsonify({"status": "success", "message": f"{member}님의 {product} 주문 삭제"}), 200
            return jsonify({"status": "error", "message": "삭제할 주문을 찾을 수 없습니다."}), 404

    # --- JSON 입력 처리 ---
    member = data.get("회원명", "").strip()
    product = data.get("제품명", "").strip()

    if "수정목록" in data:  # 주문 수정
        update_order(member, product, data["수정목록"])
        return jsonify({"status": "success", "action": "수정"}), 200

    if all(k in data for k in ["회원명", "제품명", "제품가격"]):  # 주문 등록
        register_order(
            member, product,
            data.get("제품가격", ""), data.get("PV", ""),
            data.get("결재방법", ""), data.get("배송처", ""),
            data.get("주문일자", "")
        )
        return jsonify({"status": "success", "action": "등록"}), 201

    if member or product:  # 주문 조회
        matched = find_order(member, product)
        if not matched:
            return jsonify({"error": "해당 주문 없음"}), 404
        return jsonify([clean_order_data(o) for o in matched]), 200

    return jsonify({"status": "error", "message": "유효한 요청 아님"}), 400







# --------------------------
# 📌 호환용 엔드포인트 (옛 API → 새 API)
# --------------------------

@app.route("/upload_order_text", methods=["POST"])
def compat_upload_order_text():
    """옛 API 호환용 → /order/nl"""
    return order_nl()

@app.route("/parse_and_save_order", methods=["POST"])
def compat_parse_and_save_order():
    """옛 API 호환용 → /order/nl"""
    return order_nl()

@app.route("/find_order", methods=["POST"])
def compat_find_order():
    """옛 API 호환용 → /order/nl"""
    return order_nl()

@app.route("/orders/search-nl", methods=["POST"])
def compat_orders_search_nl():
    """옛 API 호환용 → /order/nl"""
    return order_nl()

@app.route("/order_find_auto", methods=["POST"])
def compat_order_find_auto():
    """옛 API 호환용 → /order/nl"""
    return order_nl()

@app.route("/register_order", methods=["POST"])
def compat_register_order():
    """옛 API 호환용 → /order/nl"""
    return order_nl()

@app.route("/update_order", methods=["POST"])
def compat_update_order():
    """옛 API 호환용 → /order/nl"""
    return order_nl()

@app.route("/delete_order", methods=["POST"])
def compat_delete_order():
    """옛 API 호환용 → /order/nl"""
    return order_nl()

@app.route("/delete_order_confirm", methods=["POST"])
def compat_delete_order_confirm():
    """옛 API 호환용 → /order/nl"""
    return order_nl()

@app.route("/delete_order_request", methods=["POST"])
def compat_delete_order_request():
    """옛 API 호환용 → /order/nl"""
    return order_nl()








# ======================================================================================
# ✅ 주문: 외부 API 프록시
# ======================================================================================
@app.route("/saveOrder", methods=["POST"])
def save_order_proxy():
    """
    외부 API 프록시 (호환용 메인 엔드포인트)
    📌 기능:
    - 입력된 주문 JSON을 MEMBERSLIST_API_URL로 그대로 전달
    """
    try:
        payload = request.get_json(force=True)
        resp = requests.post(MEMBERSLIST_API_URL, json=payload)
        resp.raise_for_status()
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --------------------------
# 📌 호환용 엔드포인트 (옛 API → 새 API)
# --------------------------
@app.route("/save_Order", methods=["POST"])
def compat_save_order():
    """옛 API 호환용 → /saveOrder"""
    return save_order_proxy()



















# ======================================================================================
# ✅ 메모(note: 상담일지/개인일지/활동일지) 저장
# ======================================================================================
# ======================================================================================
# ✅ 메모(note: 상담일지/개인일지/활동일지) 저장
# ======================================================================================
# ======================================================================================
# ✅ 메모(note: 상담일지/개인일지/활동일지) 저장
# ======================================================================================
# ======================================================================================
# ✅ 저장 (상담/개인/활동일지)
# ======================================================================================
# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
# ======================================================================================
# 자동 분기 메모 저장
# ======================================================================================
@app.route("/memo_save_auto", methods=["POST"])
def memo_save_auto():
    """
    메모 저장 자동 분기 API
    📌 설명:
    - JSON 입력(일지종류, 회원명, 내용) → save_memo_route
    - 자연어 입력(요청문) → add_counseling_route
    📥 입력(JSON 예시1 - JSON 전용):
    {
      "일지종류": "상담일지",
      "회원명": "홍길동",
      "내용": "오늘은 제품설명회를 진행했습니다."
    }
    📥 입력(JSON 예시2 - 자연어 전용):
    {
      "요청문": "이태수 상담일지 저장 오늘부터 슬림바디 다시 시작"
    }
    """
    data = request.get_json(silent=True) or {}

    if "요청문" in data or "text" in data:
        return add_counseling_route()
    if "일지종류" in data and "회원명" in data:
        return save_memo_route()

    return jsonify({
        "status": "error",
        "message": "❌ 입력이 올바르지 않습니다. "
                   "자연어는 '요청문/text', JSON은 '일지종류/회원명/내용'을 포함해야 합니다."
    }), 400






# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
# ======================================================================================
# JSON 전용 메모 저장
# ======================================================================================
@app.route("/save_memo", methods=["POST"])
def save_memo_route():
    """
    일지 저장 API (JSON 전용)
    📌 설명:
    회원명과 일지 종류, 내용을 JSON 입력으로 받아 시트에 저장합니다.
    📥 입력(JSON 예시):
    {
      "일지종류": "상담일지",
      "회원명": "홍길동",
      "내용": "오늘은 제품설명회를 진행했습니다."
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        sheet_name = data.get("일지종류", "").strip()
        member = data.get("회원명", "").strip()
        content = data.get("내용", "").strip()

        if not sheet_name or not member or not content:
            return jsonify({"status": "error", "error": "일지종류, 회원명, 내용은 필수 입력 항목입니다."}), 400

        ok = save_memo(sheet_name, member, content)
        if ok:
            return jsonify({"status": "success", "message": f"{member}님의 {sheet_name} 저장 완료"}), 201
        return jsonify({"status": "error", "error": "시트 저장에 실패했습니다."}), 500

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
# ======================================================================================
# 자연어 전용 메모 저장
# ======================================================================================
@app.route("/add_counseling", methods=["POST"])
def add_counseling_route():
    """
    상담/개인/활동 일지 저장 API (자연어 전용)
    📌 설명:
    자연어 요청문을 파싱하여 상담일지/개인일지/활동일지 시트에 저장합니다.
    📥 입력(JSON 예시):
    {
      "요청문": "이태수 상담일지 저장 오늘부터 슬림바디 다시 시작"
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        text = data.get("요청문", "").strip()

        match = re.search(r"([가-힣]{2,10})\s*(상담일지|개인일지|활동일지)\s*저장", text)
        if not match:
            return jsonify({"status": "error", "error": "회원명 또는 일지종류를 인식할 수 없습니다."}), 400

        member_name = match.group(1).strip()
        sheet_type = match.group(2)

        content = text.replace(f"{member_name} {sheet_type} 저장", "").strip()
        if not content:
            return jsonify({"status": "error", "error": "저장할 내용이 비어 있습니다."}), 400

        ok = save_memo(sheet_type, member_name, content)
        if ok:
            return jsonify({"status": "success", "message": f"{member_name}님의 {sheet_type} 저장 완료"}), 201
        return jsonify({"status": "error", "error": "시트 저장에 실패했습니다."}), 500

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


























    

# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
# ======================================================================================
# ✅ 메모 검색 (자동 분기)
# ======================================================================================
@app.route("/memo_find_auto", methods=["POST"])
def memo_find_auto():
    """
    메모 검색 자동 분기 API
    📌 설명:
    - 자연어 기반 요청(text, query 포함) → search_memo_from_text
    - JSON 기반 요청(sheet, keywords, member_name 등 포함) → search_memo
    """
    data = request.get_json(silent=True) or {}

    # ✅ 자연어 기반: query / text 가 있을 때
    if "query" in data or "text" in data:
        return search_memo_from_text()

    # ✅ JSON 기반: sheet / keywords / member_name 중 하나라도 있을 때
    if any(k in data for k in ["sheet", "keywords", "member_name"]):
        return search_memo()

    # ✅ 단일 문자열만 전달된 경우 (ex: { "text": "전체메모 검색 중국" } 로 처리)
    if isinstance(data, str) and data.strip():
        return search_memo_from_text()

    return jsonify({
        "status": "error",
        "message": "❌ 입력이 올바르지 않습니다. "
                   "자연어는 'query/text/단일문자열', "
                   "JSON은 'sheet/keywords/member_name'을 포함해야 합니다."
    }), 400


# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
# ======================================================================================
# ✅ API 고급 검색 (content 문자열 기반, 조건식 가능)
# ======================================================================================
@app.route("/search_memo", methods=["POST"])
def search_memo():
    """
    메모 고급 검색 API
    📌 설명:
    JSON 기반으로 상담/개인/활동 일지를 검색합니다.
    📥 입력(JSON 예시):
    {
        "sheet": "상담일지",       # 상담일지 / 개인일지 / 활동일지 / 전체
        "keywords": ["중국", "세미나"],
        "search_mode": "any",    # any | 동시검색
        "member_name": "이태수",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "limit": 20
    }
    """
    try:
        data = request.get_json(silent=True) or {}

        sheet = data.get("sheet", "전체")
        keywords = data.get("keywords", [])
        search_mode = data.get("search_mode", "any")
        member_name = data.get("member_name")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        limit = int(data.get("limit", 20)) or 20  # 기본값 20

        # ✅ 검색할 시트 결정
        if sheet == "상담일지":
            sheet_names = ["상담일지"]
        elif sheet == "개인일지":
            sheet_names = ["개인일지"]
        elif sheet == "활동일지":
            sheet_names = ["활동일지"]
        else:
            sheet_names = ["상담일지", "개인일지", "활동일지"]

        all_results = []
        for sheet_name in sheet_names:
            partial = search_memo_core(
                sheet_name=sheet_name,
                keywords=keywords,
                search_mode=search_mode,
                member_name=member_name,
                limit=limit
            )
            all_results.extend(partial)

        # ✅ 정렬 (기본 최신순)
        try:
            all_results.sort(
                key=lambda x: datetime.strptime(
                    x.get("작성일자", "1900-01-01 00:00"),
                    "%Y-%m-%d %H:%M"
                ),
                reverse=True
            )
        except Exception:
            pass

        has_more = len(all_results) > limit
        results = all_results[:limit]

        return jsonify({
            "status": "success",
            "sheets": sheet_names,
            "keywords": keywords,
            "search_mode": search_mode,
            "member_name": member_name,
            "limit": limit,
            "results": results,
            "has_more": has_more
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500







# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
# ======================================================================================
# ✅ 자연어 검색 (사람 입력 “검색” 문장) ipad용
# ======================================================================================
@app.route("/search_memo_from_text", methods=["POST"])
def search_memo_from_text():
    """
    자연어 메모 검색 API (페이지네이션 + 일지 분류 출력 + 순서 고정 + 텍스트/JSON 선택)
    📌 설명:
    - 기본 출력: 사람이 읽기 좋은 텍스트 블록
    - {"detail": true} 옵션 추가 시: JSON 상세 구조 반환
    """
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    limit = int(data.get("limit", 20))
    offset = int(data.get("offset", 0))
    detail = data.get("detail", False)

    if not text:
        return jsonify({"error": "text가 비어 있습니다."}), 400
    if "검색" not in text:
        return jsonify({"error": "'검색' 키워드가 반드시 포함되어야 합니다."}), 400

    # ✅ 시트 모드 판별
    if "개인" in text:
        sheet_names = ["개인일지"]
    elif "상담" in text:
        sheet_names = ["상담일지"]
    elif "활동" in text:
        sheet_names = ["활동일지"]
    else:
        sheet_names = ["상담일지", "개인일지", "활동일지"]

    # ✅ 검색 모드 판별
    search_mode = "동시검색" if ("동시" in text or "동시검색" in text) else "any"

    # ✅ 불필요한 단어 제거
    ignore = {
        "검색", "해주세요", "내용", "다음", "에서", "메모",
        "동시", "동시검색", "전체메모", "개인일지", "상담일지", "활동일지"
    }
    tokens = [t for t in text.split() if t not in ignore]

    # ✅ 회원명 추출
    member_name = None
    for i in range(len(tokens) - 2):
        if (
            re.match(r"^[가-힣]{2,10}$", tokens[i]) and
            tokens[i+1] in {"개인일지", "상담일지", "활동일지"} and
            "검색" in tokens[i+2]
        ):
            member_name = tokens[i]
            break

    # ✅ 검색 키워드 추출 + clean_content 적용
    content_tokens = [t for t in tokens if t != member_name]
    raw_content = " ".join(content_tokens).strip()
    search_content = clean_content(raw_content, member_name)

    if not search_content:
        return jsonify({"error": "검색할 내용이 없습니다."}), 400

    keywords = search_content.split()

    # ✅ 전체 시트 검색
    all_results = []
    for sheet_name in sheet_names:
        partial = search_memo_core(
            sheet_name=sheet_name,
            keywords=keywords,
            search_mode=search_mode,
            member_name=member_name,
            limit=9999
        )
        for p in partial:
            p["일지종류"] = sheet_name
        all_results.extend(partial)

    # ✅ 최신순 정렬
    try:
        all_results.sort(
            key=lambda x: datetime.strptime(
                x.get("작성일자", "1900-01-01 00:00"), "%Y-%m-%d %H:%M"
            ),
            reverse=True
        )
    except Exception:
        pass

    # ✅ 일지별 그룹핑 (출력 순서 고정)
    grouped = {"활동일지": [], "상담일지": [], "개인일지": []}
    for item in all_results:
        if item["일지종류"] in grouped:
            grouped[item["일지종류"]].append(item)

    # ✅ 페이지네이션 적용
    for key in grouped:
        grouped[key] = grouped[key][offset:offset + limit]

    # ✅ 텍스트 블록 변환
    icons = {"활동일지": "🗂", "상담일지": "📂", "개인일지": "📒"}
    text_blocks = []
    for sheet_name in ["활동일지", "상담일지", "개인일지"]:
        entries = grouped.get(sheet_name, [])
        if entries:
            block = [f"{icons[sheet_name]} {sheet_name}"]
            for e in entries:
                line = f"· ({e.get('작성일자')}) {e.get('내용')} — {e.get('회원명')}"
                block.append(line)
            text_blocks.append("\n".join(block))
    response_text = "\n\n".join(text_blocks)

    # ✅ 분기 응답
    if detail:
        return jsonify({
            "status": "success",
            "sheets": sheet_names,
            "member_name": member_name,
            "search_mode": search_mode,
            "keywords": keywords,
            "results": grouped,
            "has_more": any(len(v) > limit for v in grouped.values())
        }), 200
    else:
        return jsonify({
            "status": "success",
            "keywords": keywords,
            "formatted_text": response_text,
            "has_more": any(len(v) > limit for v in grouped.values())
        }), 200




# ======================================================================================
# ✅ 메모(note: 상담일지/개인일지/활동일지) 저장
# ======================================================================================
# ======================================================================================
# ✅ 메모(note: 상담일지/개인일지/활동일지) 저장
# ======================================================================================
# ======================================================================================
# ✅ 메모(note: 상담일지/개인일지/활동일지) 저장
# ======================================================================================











# ======================================================================================
# ✅ 후원수당 등록
# ======================================================================================
# ======================================================================================
# ✅ 후원수당 등록
# ======================================================================================
# ======================================================================================
# ✅ 후원수당 등록
# ======================================================================================

# ======================================================================================
# 후원 수당
# ======================================================================================
# ✅ 후원수당 조회 후원수당 시트에서 검색
# ==============================
# 후원수당 API
# ==============================

# ======================================================================================

# ==============================
# 후원수당 API
# ==============================

@app.route("/register_commission", methods=["POST"])
def register_commission_route():
    """
    후원수당 등록 API
    📌 설명:
    회원명을 기준으로 후원수당 데이터를 시트에 등록합니다.
    """
    try:
        data = request.get_json()
        member = data.get("회원명", "").strip()
        amount = data.get("후원수당", "").strip()

        if not member or not amount:
            return jsonify({"status": "error", "error": "회원명과 후원수당은 필수 입력 항목입니다."}), 400

        ok = register_commission(data)
        if ok:
            return jsonify({
                "status": "success",
                "message": f"{member}님의 후원수당 {amount}원이 등록되었습니다."
            }), 200
        else:
            return jsonify({"status": "error", "error": "등록 실패"}), 500

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500






@app.route("/update_commission", methods=["POST"])
def update_commission_route():
    """후원수당 수정 API"""
    try:
        data = request.get_json()
        member = data.get("회원명", "").strip()
        date = data.get("지급일자", "").strip()
        updates = data.get("updates", {})

        if not member or not date:
            return jsonify({"status": "error", "error": "회원명과 지급일자는 필수 항목입니다."}), 400

        update_commission(member, date, updates)
        return jsonify({
            "status": "success",
            "message": f"{member}님의 {date} 후원수당 데이터가 수정되었습니다."
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500



@app.route("/delete_commission", methods=["POST"])
def delete_commission_route():
    """후원수당 삭제 API"""
    try:
        data = request.get_json()
        member = data.get("회원명", "").strip()
        date = data.get("지급일자", "").strip()

        if not member:
            return jsonify({"status": "error", "error": "회원명이 필요합니다."}), 400

        result = delete_commission(member, 기준일자=date if date else None)
        return jsonify({
            "status": "success",
            "message": result.get("message", "")
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

# ============================================================




























# ======================================================================================
# ✅ 주문 조회 (자동 분기)
# ======================================================================================
@app.route("/order_find_auto", methods=["POST"])
def order_find_auto():
    """
    주문 조회 자동 분기 API
    📌 설명:
    - 자연어 기반 요청(query, text) → search_order_by_nl
    - JSON 기반 요청(회원명, 제품명) → find_order_route
    """
    data = request.get_json(silent=True) or {}

    # ✅ 자연어 기반
    if "query" in data or "text" in data:
        return search_order_by_nl()

    # ✅ JSON 기반
    if "회원명" in data or "제품명" in data:
        return find_order_route()

    # ✅ 단일 문자열만 전달된 경우
    if isinstance(data, str) and data.strip():
        return search_order_by_nl()

    return jsonify({
        "status": "error",
        "message": "❌ 입력이 올바르지 않습니다. "
                   "자연어는 'query/text/단일문자열', "
                   "JSON은 '회원명/제품명'을 포함해야 합니다."
    }), 400




# ======================================================================================
# ✅ 주문 조회 (JSON 전용)
# ======================================================================================
@app.route("/find_order", methods=["POST"])
def find_order_route():
    """
    주문 조회 API (JSON 전용)
    📌 설명:
    회원명과 제품명을 기준으로 주문 내역을 조회합니다.
    📥 입력(JSON 예시):
    {
      "회원명": "김상민",
      "제품명": "헤모힘"
    }
    """
    try:
        data = request.get_json()
        member = data.get("회원명", "").strip()
        product = data.get("제품명", "").strip()

        if not member and not product:
            return jsonify({"error": "회원명 또는 제품명을 입력해야 합니다."}), 400

        matched = find_order(member, product)
        if not matched:
            return jsonify({"error": "해당 주문을 찾을 수 없습니다."}), 404

        if len(matched) == 1:
            return jsonify(clean_order_data(matched[0])), 200
        return jsonify([clean_order_data(o) for o in matched]), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ======================================================================================
# ✅ 주문 조회 (자연어 전용)
# ======================================================================================
@app.route("/orders/search-nl", methods=["POST"])
def search_order_by_nl():
    """
    주문 자연어 검색 API (자연어 전용)
    📌 설명:
    자연어 문장에서 회원명, 제품명 등을 추출하여 주문 내역을 조회합니다.
    📥 입력(JSON 예시):
    {
      "query": "김상민 헤모힘 주문 조회"
    }
    """
    try:
        data = request.get_json()
        query = data.get("query")
        if not query:
            return Response("query 파라미터가 필요합니다.", status=400)

        parsed = parse_order_text(query)
        if not parsed:
            return Response("자연어에서 주문 정보를 추출할 수 없습니다.", status=400)

        member = parsed.get("회원명", "")
        product = parsed.get("제품명", "")

        matched = find_order(member, product)
        if not matched:
            return jsonify({"error": "해당 주문을 찾을 수 없습니다."}), 404

        return jsonify([clean_order_data(o) for o in matched]), 200

    except Exception as e:
        return Response(f"[서버 오류] {str(e)}", status=500)












































# ======================================================================================
# ✅ 후원수당 조회 (자동 분기)
# ======================================================================================
@app.route("/commission_find_auto", methods=["POST"])
def commission_find_auto():
    """
    후원수당 조회 자동 분기 API
    📌 설명:
    - 자연어 기반 요청(query, text) → search_commission_by_nl
    - JSON 기반 요청(회원명) → find_commission_route
    """
    data = request.get_json(silent=True) or {}

    # ✅ 자연어 기반
    if "query" in data or "text" in data:
        return search_commission_by_nl()

    # ✅ JSON 기반
    if "회원명" in data:
        return find_commission_route()

    # ✅ 단일 문자열만 전달된 경우
    if isinstance(data, str) and data.strip():
        return search_commission_by_nl()

    return jsonify({
        "status": "error",
        "message": "❌ 입력이 올바르지 않습니다. "
                   "자연어는 'query/text/단일문자열', "
                   "JSON은 '회원명'을 포함해야 합니다."
    }), 400





# ======================================================================================
# ✅ 후원수당 조회 (JSON 전용)
# ======================================================================================
@app.route("/find_commission", methods=["POST"])
def find_commission_route():
    """
    후원수당 조회 API (JSON 전용)
    📌 설명:
    회원명을 기준으로 후원수당 데이터를 조회합니다.
    📥 입력(JSON 예시):
    {
      "회원명": "홍길동"
    }
    """
    try:
        data = request.get_json()
        member = data.get("회원명", "").strip()
        if not member:
            return jsonify({"status": "error", "error": "회원명이 필요합니다."}), 400

        results = find_commission({"회원명": member})
        return jsonify({"status": "success", "results": results}), 200

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ======================================================================================
# ✅ 후원수당 조회 (자연어 전용)
# ======================================================================================
@app.route("/commission/search-nl", methods=["POST"])
def search_commission_by_nl():
    """
    후원수당 자연어 검색 API (자연어 전용)
    📌 설명:
    자연어 문장에서 회원명을 추출하여 후원수당을 조회합니다.
    📥 입력(JSON 예시):
    {
      "query": "홍길동 후원수당 조회"
    }
    """
    try:
        data = request.get_json()
        query = data.get("query")
        if not query:
            return Response("query 파라미터가 필요합니다.", status=400)

        parsed = parse_commission(query)
        member = parsed.get("회원명", "")
        if not member:
            return Response("자연어에서 회원명을 추출할 수 없습니다.", status=400)

        results = find_commission({"회원명": member})
        return jsonify({"status": "success", "results": results}), 200

    except Exception as e:
        return Response(f"[서버 오류] {str(e)}", status=500)













if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)


