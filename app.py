# =================================================
# 표준 라이브러리
# =================================================
import os
import re
import json
import traceback
import unicodedata
import inspect   # ✅ 이거 추가
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from flask import request, jsonify
from flask import g

# =================================================
# 외부 라이브러리
# =================================================
import requests
from flask import Flask, request, jsonify, Response, g, send_from_directory
from flask_cors import CORS

# =================================================
# 프로젝트: config
# =================================================
from config import (
    API_URLS, HEADERS,
    GOOGLE_SHEET_TITLE, SHEET_KEY,
    OPENAI_API_KEY, OPENAI_API_URL, MEMBERSLIST_API_URL, openai_client,
    SHEET_MAP,
)

# =================================================
# 프로젝트: parser
# =================================================
from parser import (
    guess_intent,
    preprocess_user_input,
    
)

# =================================================
# 프로젝트: service
# =================================================
from service import (
    # 회원
    find_member_internal, clean_member_data,
    register_member_internal, update_member_internal,
    delete_member_internal, delete_member_field_nl_internal,
    process_member_query,

    # 주문
    handle_order_save, 
    find_order, register_order, update_order,
    delete_order, delete_order_by_row, clean_order_data,
    save_order_to_sheet,

    # 메모
    save_memo, find_memo, search_in_sheet,

    # 후원수당
    find_commission, register_commission,
    update_commission, delete_commission,
)

# =================================================
# 프로젝트: utils
# =================================================
from utils import (
    normalize_code_query,
    clean_member_query,
    now_kst, search_member, run_intent_func,
    call_searchMemo, openai_vision_extract_orders,
    normalize_request_data, clean_memo_query,
    clean_order_query,
    fallback_natural_search,
    format_memo_results
)

# =================================================
# 프로젝트: routes
# =================================================
from routes import (
    # 회원
    search_member_func,
    call_member,
    register_member_func,
    update_member_func,
    save_member_func,
    delete_member_func,
    delete_member_field_nl_func,
    member_select,
    member_select_direct,
    find_member_logic,
    sort_fields_by_field_map,
    get_full_member_info,
    get_summary_info,
    get_compact_info,
    handle_update_member,

    # 메모
    memo_save_auto_func,
    add_counseling_func,
    search_memo_func,
    search_memo_from_text_func,
    memo_find_auto_func,
   

    # 주문
   
    order_upload_pc_func,
    order_upload_ipad_func,
    order_nl_func,
    order_auto_func,
    save_order_proxy_func,
    addOrders,


    # 후원수당
    commission_find_auto_func,
    find_commission_func,
    search_commission_by_nl_func,
)

# intent 매핑은 routes.intent_map 에서만 import
from routes.intent_map import (
    INTENT_MAP,
    MEMBER_INTENTS,
    MEMO_INTENTS,
    ORDER_INTENTS,
    COMMISSION_INTENTS,
)


from routes import search_memo_core
import re
from parser import field_map
from utils import get_member_fields
from utils import fallback_natural_search, normalize_code_query










# --------------------------------------------------
# Google Sheets
# --------------------------------------------------
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "DB")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT", "credentials.json")

# --------------------------------------------------
# OpenAI
# --------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL")
PROMPT_ID = os.getenv("PROMPT_ID")
PROMPT_VERSION = os.getenv("PROMPT_VERSION")

# --------------------------------------------------
# Memberslist API
# --------------------------------------------------
MEMBERSLIST_API_URL = os.getenv("MEMBERSLIST_API_URL")

print("✅ OPENAI_API_KEY 세팅됨:", bool(OPENAI_API_KEY))
print("✅ OPENAI_API_URL:", OPENAI_API_URL)



# ✅ Flask 초기화
app = Flask(__name__)
CORS(app)  # ← 추가

# --------------------------------------------------
# 📌 OpenAPI 스펙 반환
# --------------------------------------------------
with open("openapi.json", "r", encoding="utf-8") as f:
    openapi_spec = json.load(f)

@app.route("/openapi.json", methods=["GET"])
def openapi():
    """OpenAPI 스펙(JSON) 반환"""
    return jsonify(openapi_spec)

# --------------------------------------------------
# 📌 플러그인 manifest 반환
# --------------------------------------------------
@app.route('/.well-known/ai-plugin.json')
def serve_ai_plugin():
    """ChatGPT 플러그인 manifest 파일 반환"""
    return send_from_directory('.well-known', 'ai-plugin.json', mimetype='application/json')

# --------------------------------------------------
# 📌 로고 반환
# --------------------------------------------------
@app.route("/logo.png", methods=["GET"])
def plugin_logo():
    """플러그인 로고 이미지 반환"""
    return send_from_directory(".", "logo.png", mimetype="image/png")








# ✅ 확인용 출력 (선택)
if os.getenv("DEBUG", "false").lower() == "true":
    print("✅ GOOGLE_SHEET_TITLE:", os.getenv("GOOGLE_SHEET_TITLE"))
    print("✅ GOOGLE_SHEET_KEY 존재 여부:", "Yes" if os.getenv("GOOGLE_SHEET_KEY") else "No")


# --------------------------------------------------
# 📌 헬스체크
# --------------------------------------------------
# ✅ 홈 라우트
@app.route("/")
def home():
    """
    홈(Health Check) API
    📌 설명:
    서버가 정상 실행 중인지 확인하기 위한 기본 엔드포인트입니다.
    """
    return "Flask 서버가 실행 중입니다."




from utils.sheets import  get_sheet ,get_worksheet

# ======================================================================================
# 추가 부분
# ======================================================================================
@app.route("/debug_sheets", methods=["GET"])
def debug_sheets():
    """현재 연결된 구글 시트 목록과 특정 시트의 헤더 확인"""
    try:
        sheet = get_sheet()
        sheet_names = [ws.title for ws in sheet.worksheets()]

        # ?sheet=DB 파라미터 있으면 해당 시트의 헤더 반환
        target = request.args.get("sheet")
        headers = []
        if target:
            ws = get_worksheet(target)
            headers = ws.row_values(1)

        # ✅ 여기서 json.dumps + ensure_ascii=False 사용
        return app.response_class(
            response=json.dumps({"sheets": sheet_names, "headers": headers}, ensure_ascii=False),
            status=200,
            mimetype="application/json"
        )
    except Exception as e:
        return app.response_class(
            response=json.dumps({"error": str(e)}, ensure_ascii=False),
            status=500,
            mimetype="application/json"
        )












# --------------------------------------------------
# 공통 실행 유틸
# --------------------------------------------------
def run_intent_func(func, query=None, options=None):
    """함수 시그니처 검사 후 안전하게 실행"""
    sig = inspect.signature(func)
    if len(sig.parameters) == 0:
        return func()
    elif len(sig.parameters) == 1:
        return func(query)
    else:
        return func(query, options)







# --------------------------------------------------
# 요청 전처리
# --------------------------------------------------
@app.before_request
def preprocess_input():
    """
    요청 전처리
    1. /postIntent → 그대로 통과
    2. POST JSON 입력이 있으면 g.query 에 저장
    3. 자연어(str)만 들어온 경우 → post_intent() 로 우회
    """
    if request.endpoint == "post_intent":
        return None

    if request.method == "POST":
        data = request.get_json(silent=True) or {}

        # ✅ g.query 항상 세팅
        from flask import g
        if isinstance(data, str):
            # 문자열 요청 → {"query": "..."} 로 래핑
            g.query = {"query": data}
        elif isinstance(data, dict):
            g.query = data
        else:
            g.query = {}

        # -------------------------------
        # 자연어 판별 → post_intent 우회
        # -------------------------------
        q = ""
        if isinstance(g.query.get("query"), str):
            q = g.query.get("query", "").strip()
        elif isinstance(g.query.get("text"), str):
            q = g.query.get("text", "").strip()

        # 구조화 JSON이 아닌 경우 → 자연어로 간주
        if q and not ("회원명" in g.query or "회원번호" in g.query):
            return post_intent()

    return None








def preprocess_member_query(text: str) -> str:
    """
    회원 검색용 전처리
    - 회원번호, 휴대폰번호, 한글 이름 감지
    - 불필요한 접두어("회원검색")는 붙이지 않고 원래 값 그대로 반환
    """
    text = (text or "").strip()

    # 1. 회원번호 (숫자만)
    if text.isdigit():
        print(f"[preprocess_member_query] 회원번호 감지 → {text}")
        return text

    # 2. 휴대폰 번호 (010-xxxx-xxxx or 010xxxxxxxx)
    phone_pattern = r"^010[-]?\d{4}[-]?\d{4}$"
    if re.fullmatch(phone_pattern, text):
        print(f"[preprocess_member_query] 휴대폰번호 감지 → {text}")
        return text

    # 3. 한글 이름 (2~4자)
    name_pattern = r"^[가-힣]{2,4}$"
    if re.fullmatch(name_pattern, text):
        print(f"[preprocess_member_query] 한글이름 감지 → {text}")
        return text

    # 4. 기본 (변경 없음)
    print(f"[preprocess_member_query] 보정 없음 → {text}")
    return text


def ensure_query_dict(query) -> dict:
    """
    query가 문자열이면 {"raw_text": query}로 감싸고,
    None이면 {} 반환. dict면 그대로 반환.
    """
    if isinstance(query, str):
        return {"raw_text": query}
    if isinstance(query, dict):
        return query
    return {}

# --------------------------------------------------------------------
# postIntent (자연어 입력 전용 공식 진입점)
# --------------------------------------------------------------------
@app.route("/postIntent", methods=["POST"])
def post_intent():
    raw = request.get_json(silent=True)

    if isinstance(raw, str):
        data = {"query": raw}
    elif isinstance(raw, dict):
        data = raw
    else:
        data = {}

    text = data.get("text") or data.get("query") or ""
    print(f"[DEBUG] text type: {type(text)}, value: {text}")

    if isinstance(text, str):
        text = text.strip()
    else:
        return jsonify({
            "status": "error",
            "message": f"❌ text/query는 문자열이어야 합니다.",
            "http_status": 400
        })

    if not text:
        return jsonify({
            "status": "error",
            "message": "❌ text 또는 query 필드가 필요합니다."
        }), 400

    # ✅ 1단계: 규칙 기반 intent
    intent = guess_intent(text)
    if intent and intent != "unknown":
        parsed = nlu_to_pc_input(text)
        g.intent = intent
        g.query = parsed.get("query", {}) or {}
        print(f"[INTENT 규칙 기반 처리] intent={intent}, query={g.query}")
    else:
        # ✅ 2단계: NLU fallback
        parsed = nlu_to_pc_input(text)
        intent = parsed.get("intent", "unknown")
        g.intent = intent
        g.query = parsed.get("query", {}) or {}
        print(f"[INTENT NLU fallback 처리] intent={intent}, query={g.query}")

    # ✅ intent 기반 전처리
    initial_text = text
    if intent in ["register_member", "update_member", "delete_member"]:
        text = clean_member_query(initial_text)
        text = preprocess_member_query(text)
    elif intent in ["save_memo", "find_memo", "memo_add", "memo_search"]:
        text = clean_memo_query(initial_text)
    elif intent in ["register_order", "update_order", "delete_order", "find_order"]:
        text = clean_order_query(initial_text)
    else:
        text = clean_member_query(initial_text)
        text = preprocess_member_query(text)

    # ✅ NLU 재분석 (전처리 후 → NLU 보강)
    parsed = nlu_to_pc_input(text)
    refined_intent = parsed.get("intent")
    if (not intent or intent == "unknown") and refined_intent and refined_intent != "unknown":
        intent = refined_intent
        g.intent = intent
        g.query = parsed.get("query", {}) or {}

    # ✅ 여기 추가 (raw_text 세팅)
    if isinstance(g.query, dict):
        g.query["raw_text"] = initial_text  # 원본 자연어 그대로 저장    
        
    
    print(f"[INTENT 최종 확정 결과] intent={intent}, query={g.query}")


    # ✅ keywords 보정 (검색어 → keywords로 변환)
    if intent == "memo_search":
        if isinstance(g.query, dict):
            if "검색어" in g.query and isinstance(g.query["검색어"], str):
                g.query["keywords"] = g.query["검색어"].strip().split()
                del g.query["검색어"]
            elif "keywords" not in g.query:
                g.query["keywords"] = []






    try:
        # ✅ 특정 intent 직접 처리
        if intent == "member_select":
            import re
            name_match = re.match(r"([가-힣]{2,4})(?:\s*(전체정보|상세|info))?", text)
            if name_match:
                member_name = name_match.group(1)
                print(f"[AUTO] 세션 없이 '{member_name}' 전체정보 검색 시도")

                results = find_member_logic(member_name)
                if results.get("status") == "success":
                    return jsonify({
                        "status": "success",
                        "message": "회원 전체정보입니다.",
                        "results": results["results"],
                        "http_status": 200
                    }), 200
                else:
                    return jsonify(results), results.get("http_status", 400)

            return jsonify({
                "status": "error",
                "message": "회원 이름을 추출할 수 없습니다.",
                "http_status": 400
            })

        # ✅ 일반 intent 실행
        func = INTENT_MAP.get(intent)
        if not func:
            return jsonify({
                "status": "error",
                "message": f"❌ 처리할 수 없는 intent입니다. (intent={intent})"
            }), 400

        result = run_intent_func(func, text, {})

        if isinstance(result, dict):
            return jsonify(result), result.get("http_status", 200)
        if isinstance(result, list):
            return jsonify(result), 200

        return jsonify({
            "status": "error",
            "message": "알 수 없는 반환 형식"
        }), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"post_intent 처리 중 오류 발생: {str(e)}"
        }), 500








# ======================================================================================
# guess_intent 엔드포인트
# ======================================================================================
@app.route("/guess_intent", methods=["POST"])
def guess_intent_entry():
    data = request.json or {}
    user_input = data.get("query", "")

    if not user_input:
        return jsonify({"status": "error", "message": "❌ 입력(query)이 비어 있습니다."}), 400

    # 1. 전처리
    processed = preprocess_user_input(user_input)
    normalized_query = processed["query"]
    options = processed["options"]

    # 2. intent 추출
    intent = guess_intent(normalized_query)
    if not intent or intent == "unknown":
        return jsonify({"status": "error", "message": f"❌ intent 추출 실패 (query={normalized_query})"}), 400

    # 3. 실행 함수 매핑
    func = INTENT_MAP.get(intent)
    if not func:
        return jsonify({"status": "error", "message": f"❌ 처리할 수 없는 intent입니다. (intent={intent})"}), 400

    # 4. 실행
    result = run_intent_func(func, normalized_query, options)

    if isinstance(result, dict):
        return jsonify(result), result.get("http_status", 200)
    if isinstance(result, list):
        return jsonify(result), 200

    return jsonify({"status": "error", "message": "알 수 없는 반환 형식"}), 500







# ======================================================================================
# nlu_to_pc_input 엔드포인트
# ======================================================================================
def nlu_to_pc_input(text: str) -> dict:
    """
    자연어 입력을 intent + query(dict) 구조로 변환
    - guess_intent + nlu_to_pc_input 통합
    - 회원 / 메모 / 주문 intent 지원
    """
    text = (text or "").strip()




    # -------------------------------
    # 회원 관련
    # -------------------------------
    # 회원 등록
    if any(word in text for word in ["회원등록", "회원추가", "회원 등록", "회원 추가"]):
        # ✅ 케이스3: "<이름> 회원 등록 ..." → 이름 + 나머지
        print("[DEBUG] 회원등록 케이스3 매치 시도:", text)
        # 더 안전한 대안 (이름에서 '회원'이 분리된 경우만 추출)
        m = re.match(r"(?<!\S)([가-힣]{2,10})\s+회원\s*(등록|추가)\s*(.*)", text)

        if m:
            print("[DEBUG] 회원등록 케이스3 성공:", m.groups())
            member_name, _, extra = m.groups()
            return {
                "intent": "register_member",
                "query": {
                    "회원명": member_name.strip(),
                    "raw_text": extra.strip()
                }
            }

        # 케이스1: "<이름> 회원등록"
        m = re.search(r"([가-힣]{2,10})\s*(회원등록|회원추가|회원 등록|회원 추가)", text)
        if m:
            return {
                "intent": "register_member",
                "query": {
                    "회원명": m.group(1),
                    "raw_text": text   # ✅ 꼭 포함해야 함!
                }
            }



        # 케이스2: "회원등록 <이름>"
        m = re.search(r"(회원등록|회원추가|회원 등록|회원 추가)\s*([가-힣]{2,10})", text)
        if m:
            return {
                "intent": "register_member",
                "query": {
                    "회원명": m.group(2),
                    "raw_text": text   # ✅ 꼭 포함해야 함!
                }
            }



        # fallback
        return {"intent": "register_member", "query": {"raw_text": text}}







    # 회원 수정
    if any(word in text for word in ["수정", "회원수정", "회원변경", "회원 수정", "회원 변경"]):
        return {
            "intent": "update_member",
            "query": {
                "raw_text": text
            }
        }






    # 회원 삭제
    if any(word in text for word in ["회원삭제", "회원제거", "회원 삭제", "회원 제거", "삭제", "제거"]):
        # "회원삭제 이판주", "이판주 삭제", "이판주 회원삭제", "삭제 이판주" 등 위치에 관계없이 추출
        m = re.search(r"(?:회원)?\s*([가-힣]{2,4})\s*(?:회원)?\s*(삭제|제거)", text)
        if m:
            return {"intent": "delete_member", "query": {"회원명": m.group(1)}}
        return {"intent": "delete_member", "query": {"raw_text": text}}

    # 회원 조회 / 검색 (동의어 지원)
    if any(word in text for word in ["회원조회", "회원검색", "검색회원", "조회회원", "회원 조회", "회원 검색", "검색 회원", "조회 회원"]):
    # 이름까지 붙었는지 확인
        m = re.search(r"(회원\s*(검색|조회)\s*)([가-힣]{2,4})", text)
        if m:
            return {"intent": "search_member", "query": {"회원명": m.group(3)}}
        
        return {"intent": "search_member", "query": {"raw_text": text}}
    
    # 코드 검색 (코드a, 코드 b, 코드AA...)
    normalized = normalize_code_query(text)
    if normalized.startswith("코드"):
        return {"intent": "search_member", "query": {"코드": normalized}}

    # 회원명 + "회원"
    m = re.search(r"([가-힣]{2,4})\s*회원", text)
    if m:
        return {"intent": "search_member", "query": {"회원명": m.group(1)}}

    # 회원번호
    if re.fullmatch(r"\d{5,8}", text):
        return {"intent": "search_member", "query": {"회원번호": text}}

    # 휴대폰번호
    if re.fullmatch(r"(010-\d{3,4}-\d{4}|010\d{7,8})", text):
        return {"intent": "search_member", "query": {"휴대폰번호": text}}

    # 특수번호
    m = re.search(r"특수번호\s*([a-zA-Z0-9!@#]+)", text)
    if m:
        return {"intent": "search_member", "query": {"특수번호": m.group(1)}}

    # -------------------------------
    # 메모/일지 관련
    # -------------------------------
    # 메모 저장
    m = re.match(r"(\S+)\s+(개인일지|상담일지|활동일지|개인 일지|상담 일지|활동 일지)\s+저장\s+(.+)", text)
    if m:
        member_name, diary_type, content = m.groups()
        return {"intent": "memo_add", "query": {"회원명": member_name, "일지종류": diary_type, "내용": content}}

    # 메모 검색 (회원명 + 일지종류 + 검색)
    m = re.match(r"(\S+)\s+(개인일지|상담일지|활동일지|개인 일지|상담 일지|활동 일지)\s+(검색|조회)\s+(.+)", text)
    if m:
        member_name, diary_type, _, keyword = m.groups()
        return {"intent": "memo_search", "query": {"회원명": member_name, "일지종류": diary_type, "검색어": keyword}}

    # 전체 메모 검색
    m = re.match(r"전체\s*(메모|일지)\s*(검색|조회)\s*(.+)", text)
    if m:
        keyword = m.group(3)
        return {"intent": "memo_search", "query": {"회원명": "전체", "일지종류": "전체", "검색어": keyword}}

    # -------------------------------
    # 주문 관련
    # -------------------------------
    order_text = text.replace("제품주문", "주문")

    if "주문" in order_text:
        # 등록/추가/저장
        if any(word in order_text for word in ["등록", "추가", "저장"]):
            m = re.search(r"([가-힣]{2,4}).*(제품)?주문", order_text)
            if m:
                return {"intent": "order_upload_pc", "query": {"회원명": m.group(1)}}
            return {"intent": "order_upload_pc", "query": {"raw_text": text}}

        # 수정/변경/업데이트
        if any(word in order_text for word in ["수정", "변경", "업데이트"]):
            m = re.search(r"([가-힣]{2,4}).*(제품)?주문.*(수정|변경|업데이트)", order_text)
            if m:
                return {"intent": "update_order", "query": {"회원명": m.group(1)}}
            return {"intent": "update_order", "query": {"raw_text": text}}

        # 삭제/취소
        if any(word in order_text for word in ["삭제", "취소"]):
            m = re.search(r"([가-힣]{2,4}).*(제품)?주문.*(삭제|취소)", order_text)
            if m:
                return {"intent": "delete_order", "query": {"회원명": m.group(1)}}
            return {"intent": "delete_order", "query": {"raw_text": text}}

        # 단순 "홍길동 주문"
        m = re.search(r"([가-힣]{2,4}).*(제품)?주문", order_text)
        if m:
            return {"intent": "order_auto", "query": {"주문회원": m.group(1)}}

        # 그냥 "주문"
        return {"intent": "order_auto", "query": {"주문": True}}
    

    # -------------------------------
    # 회원 저장 (업서트)
    # -------------------------------
    if "회원 저장" in text:
        return {"intent": "save_member", "query": {"raw_text": text}}


    # -------------------------------
    # 후원수당
    # -------------------------------
    if "후원수당" in text or "수당" in text:
        return {"intent": "commission_find", "query": {"raw_text": text}}

    # -------------------------------
    # 기본 반환
    # -------------------------------
    parts = text.split()
    result = {}
    for part in parts:
        parsed = fallback_natural_search(part)
        result.update(parsed)

    if result.get("회원명") and (result.get("회원번호") or result.get("휴대폰번호")):
        return {
            "intent": "register_member",
            "query": result
        }

    return {"intent": "unknown", "query": {"raw_text": text}}
































# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

# ======================================================================================
# ✅ 회원 조회 자동 분기 API intent 기반 단일 라우트
# ======================================================================================
# ✅ 회원 조회 자동 분기 API
@app.route("/member", methods=["POST"])
def member_route():
    """
    회원 관련 API (intent 기반 단일 라우트)
    - g.query["intent"] 가 있으면 그대로 실행
    - 없으면 자연어 입력 분석해서 search_member / select_member 자동 분기
    """
    data = request.get_json(silent=True) or {}
    g.query = data
    intent = data.get("intent")

    # ✅ (1) intent 직접 지정된 경우
    if intent and intent in MEMBER_INTENTS:
        func = MEMBER_INTENTS[intent]

        if intent in ("register_member", "update_member", "save_member"):
            result = func(data)

        elif intent == "search_member":
            name = (
                data.get("회원명")
                or data.get("name")
                or data.get("member_name")
                or data.get("query")
                or ""
            )
            result = func(name)

        elif intent in ("delete_member", "delete_member_field_nl_func"):
            result = func()

        elif intent in ("member_select", "select_member"):
            choice = data.get("choice") or g.query.get("choice", "")
            result = func(choice)

        elif intent == "search_by_code_logic":
            code = data.get("코드") or data.get("code") or ""
            result = func(code)

        elif intent in ("summary_member", "compact_member"):
            result = func()

        else:
            result = func()

        return jsonify(result), result.get("http_status", 200)

    # ✅ (2) intent가 없을 경우 자연어 쿼리 자동 분석
    if not intent:
        if isinstance(data.get("query"), str) and not any(k in data for k in ("회원명", "회원번호")):
            query_text = data.get("query", "").strip()

            # ✅ "회원등록" 포함 시 무조건 register_member
            if "회원등록" in query_text:
                intent = "register_member"
            elif query_text.endswith("등록"):
                intent = "register_member"

            elif query_text.endswith("수정"):
                intent = "update_member"

            elif "삭제" in query_text:
                parts = query_text.split()
                if len(parts) >= 3:
                    intent = "delete_member_field_nl_func"
                else:
                    intent = "delete_member"
            elif "전체정보" in query_text or query_text in ["1", "상세", "detail", "info"]:
                intent = "select_member"
                g.query["choice"] = "1"
            elif "종료" in query_text or query_text in ["2", "끝", "exit", "quit"]:
                intent = "select_member"
                g.query["choice"] = "2"
            else:
                # 그 외 자연어 → 별도 intent 처리기로 위임
                return post_intent()

    # ✅ (3) fallback: intent 추론된 상태에서 처리
    func = MEMBER_INTENTS.get(intent)
    if not func:
        result = {
            "status": "error",
            "message": f"❌ 처리할 수 없는 회원 intent입니다. (intent={intent})",
            "http_status": 400,
        }
    else:
        if intent in ("register_member", "update_member", "save_member"):
            result = func(data)
        elif intent == "search_member":
            name = (
                data.get("회원명")
                or data.get("name")
                or data.get("member_name")
                or data.get("query")
                or ""
            )
            result = func(name)
        elif intent in ("delete_member", "delete_member_field_nl_func"):
            result = func()
        elif intent in ("member_select", "select_member"):
            choice = data.get("choice") or g.query.get("choice", "")
            result = func(choice)
        elif intent == "search_by_code_logic":
            code = data.get("코드") or data.get("code") or ""
            result = func(code)
        else:
            result = func()



        # ✅ 결과 None 방지 (Flask 안전 반환)
        if not result:
            return jsonify({
                "status": "error",
                "message": f"❌ {intent or 'unknown'} intent 처리 결과가 비어 있습니다.",
                "http_status": 500
            }), 500

        return jsonify(result), result.get("http_status", 200)







# ======================================================================================
# ✅ 일지 & 메모 (자동 분기) intent 기반 단일 라우트
# ======================================================================================
# intent 매핑 (이미 선언되어 있다고 가정)
# from routes.intent_map import MEMO_INTENTS
# from routes.routes_memo import (post_intent, ...)

@app.route("/memo", methods=["POST"])
def memo_route():
    """
    메모 관련 API (저장/검색 자동 분기)
    - 자연어 입력은 무조건 post_intent() 우회
    - JSON 입력은 구조 분석 → 저장 / 검색 분기
    """
    try:
        # ✅ g.query 우선, 없으면 request.get_json() 사용
        data = normalize_request_data()
        intent = data.get("intent")

        # ✅ 자연어 입력 간주 조건 → post_intent() 우회
        if "query" in data and isinstance(data["query"], str) and not intent:
            query_text = data["query"]
            # ❌ 회원수정 관련 문장은 post_intent로 넘기지 않음
            if any(keyword in query_text for keyword in ["회원수정", "주소 변경", "전화번호 수정", "번호 수정"]):
                return jsonify({
                    "status": "error",
                    "message": "회원수정 관련 요청은 /member 라우트에서 처리해야 합니다.",
                    "http_status": 400
                }), 400

            # ✅ 나머지 자연어 입력만 post_intent()로 우회
            return post_intent()

        




        # intent가 없는 경우 JSON 구조로 자동 판별
        if not intent:
            if all(k in data for k in ("회원명", "내용", "일지종류")):
                intent = "memo_add"
            elif "keywords" in data and "일지종류" in data:
                intent = "memo_search"

        func = MEMO_INTENTS.get(intent)

        if not func:
            result = {
                "status": "error",
                "message": f"❌ 처리할 수 없는 메모 intent입니다. (intent={intent})",
                "http_status": 400
            }
        else:



            # ✅ intent별로 호출 방식 분리
            if intent == "memo_add":
                if isinstance(data.get("query"), dict):
                    g.query = data["query"]  # ✅ query dict만 추출해서 g.query로
                    result = add_counseling_func()
                else:
                    # 자연어 케이스는 기존 방식
                    text = data.get("text") or data.get("내용") or data.get("query", "")
                    result = memo_save_auto_func(text)



            elif intent == "add_counseling":
                # JSON 저장 → g.query 기반 처리
                result = add_counseling_func()



            elif intent in ("memo_search", "search_memo"):
                result = func()
                if isinstance(result, list):
                    result = format_memo_results(result)
            else:
                result = func()


        # ✅ 반환 형식 처리
        if isinstance(result, dict):
            return jsonify(result), result.get("http_status", 200)

        if isinstance(result, list):
            return jsonify(format_memo_results(result)), 200


        return jsonify({"status": "error", "message": "알 수 없는 반환 형식"}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"메모 처리 중 오류 발생: {str(e)}",
            "http_status": 500
        }), 500


    



    






# ======================================================================================
# ✅ 제품주문 (자동 분기) intent 기반 단일 라우트
# ======================================================================================
@app.route("/order", methods=["POST"])
def order_route():
    """
    제품 주문 처리 API (자연어 + OCR JSON 통합 지원)
    -------------------------------------------------
    ① 자연어 명령 ("이태수 제품주문 저장 징코앤낫토 2개 카드결제")
    ② Vision OCR JSON ({ "orders": [...] })
    ③ multipart/form-data (iPad, 이미지 업로드 포함)
    모두 지원하는 단일 엔드포인트.
    -------------------------------------------------
    """
    try:
        print("\n" + "=" * 80)
        print("🟢 [STEP 1] /order 요청 수신")

        # -------------------------------------------------
        # 1️⃣ 요청 데이터 파싱
        # -------------------------------------------------
        data = request.get_json(silent=True)
        if not data:
            # ✅ Vision (multipart/form-data) 요청 처리
            if request.form:
                print("📸 multipart/form-data 감지 → 수동 파싱 시도")

                text = request.form.get("text") or request.form.get("query") or ""
                orders_raw = request.form.get("orders") or request.form.get("payload")

                try:
                    orders = json.loads(orders_raw) if orders_raw else []
                except Exception as e:
                    print("⚠️ orders JSON 파싱 실패:", e)
                    orders = []

                # 이미지 파일
                file = request.files.get("image")
                image_url = ""
                if file:
                    upload_folder = "./uploaded_images"
                    os.makedirs(upload_folder, exist_ok=True)
                    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
                    save_path = os.path.join(upload_folder, filename)
                    file.save(save_path)
                    image_url = f"/static/{filename}"

                data = {
                    "query": text.strip(),
                    "orders": orders,
                    "image_url": image_url,
                }
            else:
                return jsonify({
                    "status": "error",
                    "message": "❌ JSON 또는 form-data 형식이 아닙니다.",
                    "http_status": 400
                }), 400

        # -------------------------------------------------
        # 2️⃣ query / orders 필드 확인
        # -------------------------------------------------
        query_text = data.get("query", "").strip()
        orders = data.get("orders", [])

        print(f"📋 명령문: {query_text}")
        print(f"📦 OCR 추출된 주문 수: {len(orders)}")

        # -------------------------------------------------
        # 3️⃣ 자연어 문장인 경우 → post_intent()로 분기
        # -------------------------------------------------
        if query_text and not orders:
            # 자연어 명령 ("이태수 제품주문 저장") 형태는 post_intent()로 위임
            print("🧠 자연어 입력 감지 → post_intent() 위임")
            return post_intent()

        # -------------------------------------------------
        # 4️⃣ OCR 결과가 존재하는 경우 → 직접 저장
        # -------------------------------------------------
        from parser import handle_order_save

        saved_results = []
        for o in orders:
            order_data = {
                "주문일자": datetime.now().strftime("%Y-%m-%d"),
                "회원명": o.get("주문자_고객명", ""),
                "제품명": o.get("제품명", ""),
                "제품가격": o.get("제품가격", 0),
                "PV": o.get("PV", 0),
                "주문자_고객명": o.get("주문자_고객명", ""),
                "주문자_휴대폰번호": o.get("주문자_휴대폰번호", ""),
                "배송처": o.get("배송처", ""),
            }

            print(f"🧾 시트 저장 준비: {order_data}")
            result = handle_order_save(order_data)
            saved_results.append(result)

        # -------------------------------------------------
        # 5️⃣ 결과 반환
        # -------------------------------------------------
        return jsonify({
            "status": "success",
            "message": f"✅ {len(saved_results)}건의 주문이 저장되었습니다.",
            "saved_results": saved_results,
            "http_status": 200,
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"주문 처리 중 오류 발생: {str(e)}",
            "http_status": 500
        }), 500















# ======================================================================================
# ✅ 후원수당 조회 (자동 분기) intent 기반 단일 라우트
# ======================================================================================
@app.route("/commission", methods=["POST"])
def commission_route():
    """
    후원수당 관련 API (intent 기반 단일 엔드포인트)
    - before_request 에서 g.query 세팅됨
    - 자연어 입력이면 postIntent로 우회
    """
    try:
        data = getattr(g, "query", {}) or {}
        q = data.get("query")

        # 1) 자연어 판별: 문자열이거나, dict여도 텍스트성 키만 있고 구조화 키가 없으면 자연어
        if isinstance(q, str):
            return post_intent()

        if isinstance(q, dict):
            text_like_keys = {"text", "요청문", "조건", "criteria"}
            structured_keys = {
                "회원", "회원명", "member",
                "월", "연도", "기간", "시작일", "종료일", "from", "to",
                "지급일", "구분", "유형"
            }
            if any(k in q for k in text_like_keys) and not any(k in q for k in structured_keys):
                return post_intent()

        # 2) intent 기반 실행
        intent = data.get("intent")
        func = COMMISSION_INTENTS.get(intent)

        if not func:
            result = {
                "status": "error",
                "message": f"❌ 처리할 수 없는 후원수당 intent입니다. (intent={intent})",
                "http_status": 400
            }
        else:
            result = func()

        if isinstance(result, dict):
            return jsonify(result), result.get("http_status", 200)
        if isinstance(result, list):
            return jsonify(result), 200

        return jsonify({"status": "error", "message": "알 수 없는 반환 형식"}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"후원수당 처리 중 오류 발생: {str(e)}"
        }), 500



@app.route("/routes", methods=["GET"])
def show_routes():
    """현재 등록된 모든 Flask 라우트 확인"""
    return {"routes": [str(rule) for rule in app.url_map.iter_rules()]}



# 변경있음


# 잘 작동함

# 정상




















if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)


