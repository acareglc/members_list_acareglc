import re
import json
from collections import OrderedDict
from flask import g, request, Response, jsonify, session

from service import update_member_info

# 시트/서비스/파서 의존성들
from utils import (
    get_rows_from_sheet,   # DB 시트 행 조회
    get_member_sheet,      # 회원 시트 접근
    safe_update_cell,      # 안전한 셀 수정
)

from service import (
    register_member_internal,        # 회원 등록
    update_member_internal,          # 회원 수정
    delete_member_internal,          # 회원 삭제
    delete_member_field_nl_internal, # 회원 필드 삭제 (자연어)
)



from parser.parse import parse_registration   # 회원 등록/수정 파서
from parser.parse import field_map  # ✅ field_map import
from parser.parse import field_map

SHEET_NAME_DB = "DB"  # 매직스트링 방지


from parser import field_map
from utils import get_member_fields
from utils import fallback_natural_search, normalize_code_query

from utils.sheets import get_member_sheet, safe_update_cell


# ────────────────────────────────────────────────────────────────────
# 공통 헬퍼
# ────────────────────────────────────────────────────────────────────
def _norm(s):
    return (s or "").strip()

def _digits(s):
    return re.sub(r"\D", "", s or "")

def _compact_row(r: dict) -> OrderedDict:
    """회원 정보를 고정된 필드 순서로 반환"""
    return OrderedDict([
        ("회원명", r.get("회원명", "")),
        ("회원번호", r.get("회원번호", "")),
        ("특수번호", r.get("특수번호", "")),
        ("휴대폰번호",r.get("휴대폰번호", "")),
        ("코드", r.get("코드", "")),
        ("생년월일", r.get("생년월일", "")),
        ("근무처", r.get("근무처", "")),
        ("계보도", r.get("계보도", "")),
        ("주소", r.get("주소", "")),
        ("메모", r.get("메모", "")),
    ])




def call_member(name: str) -> dict:
    """
    postMember 호출 결과를 search_member_func 포맷으로 변환
    """
    try:
        # 1. API 호출
        result = postMember({"query": name})  # 🔹 실제 API 호출 함수에 맞게 수정

        if result.get("status") != "success":
            return {**result, "http_status": 404}

        # 2. 회원 데이터 가져오기
        summary_raw = result.get("summary") or {}
        
        # 3. 정규화된 summary 만들기
        summary = _normalize_summary(summary_raw)

        # 4. 사람이 읽기 좋은 한 줄 요약
        summary_line = _line(summary)

        return {
            "status": "success",
            "message": f"{summary['회원명']}님의 요약 정보입니다. '전체정보' 또는 1을 입력하시면 상세 내용을 볼 수 있습니다.",
            "summary": summary,
            "summary_line": summary_line,
            "http_status": 200
        }

    except Exception as e:
        import traceback; traceback.print_exc()
        return {"status": "error", "message": str(e), "http_status": 500}





def _normalize_summary(row: dict) -> dict:
    """
    원본 row(dict)에서 필요한 필드를 뽑아 summary(dict)로 정규화
    """
    return {
        "회원명": row.get("회원명", "").strip(),
        "회원번호": str(row.get("회원번호", "")).strip(),
        "특수번호": row.get("특수번호", "").strip(),
        "휴대폰번호": row.get("휴대폰번호", "").strip(),
        "코드": row.get("코드", "").strip().upper(),
        "생년월일": row.get("생년월일", "").strip(),
        "계보도": row.get("계보도", "").strip(),
        "근무처": row.get("근무처", "").strip(),
        "주소": row.get("주소", "").strip(),
        "메모": row.get("메모", "").strip(),
    }


def _line(summary: dict) -> str:
    """
    사람이 읽기 좋은 한 줄 요약 (정규화된 summary 사용)
    """
    parts = [
        f"회원번호: {summary['회원번호']}",
        f"특수번호: {summary['특수번호']}",
        f"휴대폰번호: {summary['휴대폰번호']}",
        f"코드: {summary['코드']}",
        f"생년월일: {summary['생년월일']}",
        f"계보도: {summary['계보도']}",
        f"근무처: {summary['근무처']}",
        f"주소: {summary['주소']}",
        f"메모: {summary['메모']}",
    ]
    # 값이 없는 항목은 제외
    # parts = [p for p in parts if not p.endswith(": ")]
    return f"{summary['회원명']} ({', '.join(parts)})"







# ────────────────────────────────────────────────────────────────────
# 1) 허브: search_member_func  ← nlu_to_pc_input 가 intent='search_member'로 보냄
# ────────────────────────────────────────────────────────────────────
def search_member_func(name):
    """
    이름으로 검색 → 요약 정보만 출력 + g.query["last_name"] 저장
    """
    try:
        if not name or not isinstance(name, str):
            return {"status": "error", "message": "회원 이름(name)이 필요합니다.", "http_status": 400}

        # 🟢 불필요한 꼬리 단어 제거 (조회, 검색 등)
        cleaned = name.strip()
        for token in ["회원조회", "회원 검색", "회원조회", "회원검색", "조회", "검색"]:
            if cleaned.endswith(token):
                cleaned = cleaned.replace(token, "").strip()
        name = cleaned




        result = find_member_logic(name)

        if result.get("status") != "success":
            return {**result, "http_status": 404}

        members = result.get("results", [])





        if not members:
            return {"status": "error", "message": f"{name}에 해당하는 회원이 없습니다.", "http_status": 404}

        # ✅ 동명이인 처리
        if len(members) > 1:
            return {
                "status": "need_choice",   # ✅ 통일된 상태 코드
                "message": f"⚠️ 동일 이름 회원 '{name}'이(가) {len(members)}명 있습니다. 번호를 선택하세요.",
                "candidates": [
                    {
                        "choice": i + 1,
                        "회원명": m.get("회원명"),
                        "회원번호": m.get("회원번호"),
                        "휴대폰번호": m.get("휴대폰번호")
                    }
                    for i, m in enumerate(members)
                ],
                "http_status": 200,
            }



        # ✅ 이름 기억 (전체정보용)
        g.query["last_name"] = name

        # ✅ 정규화된 요약 정보 사용
        member = members[0]
        summary = _normalize_summary(member)

        # ✅ 사람이 읽기 좋은 한 줄 요약도 생성
        summary_line = _line(summary)

        return {
            "status": "success",
            "message": f"{name}님의 요약 정보입니다. '전체정보'를 입력하시면 상세 내용을 볼 수 있습니다.",
            "summary": summary,
            "summary_line": summary_line,
            "http_status": 200
        }

    except Exception as e:
        import traceback; traceback.print_exc()
        return {"status": "error", "message": str(e), "http_status": 500}



# ────────────────────────────────────────────────────────────────────
# 2) 코드 검색: '코드a', '코드 A', 'code:B' 등
# ────────────────────────────────────────────────────────────────────
def search_by_code_logic():
    """
    코드 컬럼 정확 일치 (대소문자 무시)로 검색
    허용 입력: '코드a', '코드 A', '코드:A', 'code b', 'code: c'
    """
    try:
        raw = g.query.get("query") or ""
        text = str(raw).strip()

        print("=== ENTER search_by_code_logic ===")
        print("raw from g.query:", g.query.get("query"))


        # ✅ 한글/영문 '코드' + 선택적 콜론 + 공백 허용
        m = re.match(r"^(?:코드|code)\s*:?\s*([A-Za-z0-9]+)$", text, re.IGNORECASE)
        
        print("=== DEBUG REGEX ===", "text:", text, "m:", m)

        if not m:
            return {
                "status": "error",
                "message": f"올바른 코드 검색어가 아닙니다. 입력값={text}, 예: 코드a, 코드 A, code:B",
                "http_status": 400
            }

        code_value = m.group(1).upper()
        rows = get_rows_from_sheet("DB")

        # ✅ 코드 컬럼 필터링
        matched = [r for r in rows if str(r.get("코드", "")).strip().upper() == code_value]
        matched.sort(key=lambda r: str(r.get("회원명", "")).strip())

       
        # 🔽 여기서 디버깅 로그 찍기
        print("=== DEBUG search_by_code_logic ===")
        print("raw:", raw)
        print("text:", text)
        print("code_value:", code_value)
        print("rows 첫 3개:", rows[:3])
        print("matched 개수:", len(matched))       
             
       
        matched.sort(key=lambda r: str(r.get("회원명", "")).strip())
        print("=== DEBUG REGEX ===", "text:", text, "m:", m)   # 👈 여기에 추가



        # ✅ summary 정규화 → display 변환
        results = [_normalize_summary(r) for r in matched]
        display = [_line(s) for s in results]



        return {
            "status": "success",
            "intent": "search_by_code",
            "code": code_value,
            "count": len(results),
            "results": results,
            "display": display,
            "raw_text": raw
        }

    except Exception as e:
        import traceback; traceback.print_exc()
        return {"status": "error", "message": str(e), "http_status": 500}

    
# ────────────────────────────────────────────────────────────────────
# 3) 일반 검색: 이름/회원번호/휴대폰/특수번호/부분매칭
# ────────────────────────────────────────────────────────────────────
def find_member_logic(name=None):
    """
    일반 회원 검색
    - g.query["query"] 가 dict 또는 str
      dict 예: {"회원명":"홍길동"} / {"회원번호":"123456"} / {"휴대폰번호":"010-1234-5678"} / {"특수번호":"A1"}
      str  예: "홍길동" / "1234567" / "01012345678" / "특수번호 A1"
    """
    try:
        q = name if name is not None else g.query.get("query")
        rows = get_rows_from_sheet("DB")  # list[dict]

        # 1) 검색 키 추출
        f = {"회원명": None, "회원번호": None, "휴대폰번호": None, "특수번호": None}

        if isinstance(q, dict):
            for k in list(f.keys()):
                if k in q: f[k] = _norm(q.get(k))



        elif isinstance(q, str):
            text = _norm(q)

            if text.startswith("코드") or text.lower().startswith("code"):
                g.query["query"] = text
                return search_by_code_logic()




            if re.fullmatch(r"\d{5,8}", text):
                f["회원번호"] = text
            elif re.fullmatch(r"(010-\d{3,4}-\d{4}|010\d{7,8})", text):
                f["휴대폰번호"] = text
            else:
                m = re.search(r"특수번호\s*([a-zA-Z0-9!@#]+)", text)
                if m:
                    f["특수번호"] = m.group(1)
                elif re.fullmatch(r"[가-힣]{2,4}", text):
                    f["회원명"] = text
                else:
                    # 폴백: 회원명 부분 매칭
                    f["회원명"] = text
        else:
            return {"status": "error", "message": "지원하지 않는 query 형식입니다.", "http_status": 400}

        # 2) 필터링
        def match_row(r: dict) -> bool:
            if f["회원명"]:
                db_name = (r.get("회원명", "") or "").strip()
                print("[DEBUG] 회원명 비교:", f["회원명"], "vs", repr(db_name))
                if f["회원명"] != db_name:
                    return False

            if f["회원번호"]:
                if _norm(r.get("회원번호", "")) != f["회원번호"]:
                    return False
            if f["휴대폰번호"]:
                if _digits(r.get("휴대폰번호", "")) != _digits(f["휴대폰번호"]):
                    return False
            if f["특수번호"] is not None:
                if _norm(r.get("특수번호", "")) != f["특수번호"]:
                    return False
            return True


        matched = [r for r in rows if match_row(r)]
        matched.sort(key=lambda r: _norm(r.get("회원명", "")))

        results = [sort_fields_by_field_map(r) for r in matched]
        display = [_line(d) for d in results]


        return {
            "status": "success",
            "intent": "search_member",
            "count": len(results),
            "results": results,
            "display": display
        }

    except Exception as e:
        import traceback; traceback.print_exc()
        return {"status": "error", "message": str(e), "http_status": 500}


from flask import request, jsonify, session



def member_select_direct(results):
    if not results:
        return {
            "status": "error",
            "message": "회원 검색 결과가 없습니다.",
            "http_status": 404
        }

    return {
        "status": "success",
        "message": "회원 전체정보입니다.",
        "results": results,
        "http_status": 200
    }






# ===================**************
def member_select(choice=None):
    data = request.json or {}
    choice = str(data.get("choice", "")).strip()
    member_name = str(data.get("회원명", "")).strip()

    # 🔹 자연어 "홍길동 전체정보" 같은 경우 → 회원명 직접 처리
    if member_name:
        results = find_member_logic(member_name)
        if results.get("status") == "success":
            return {
                "status": "success",
                "message": "회원 전체정보입니다.",
                "results": results["results"],
                "http_status": 200
            }
        else:
            return results

    # 🔹 choice 기반 처리 (번호 선택 전용)
    if choice in ["종료", "끝", "exit", "quit"]:
        choice = "2"
    elif choice in ["전체정보", "전체", "1", "상세", "detail", "info"]:
        choice = "1"

    results = session.get("last_search_results", [])

    if not results:
        return {
            "status": "error",
            "message": "이전에 검색된 결과가 없습니다. 먼저 회원명을 입력해주세요.",
            "http_status": 400
        }

    if choice == "1":
        return {
            "status": "success",
            "message": "회원 전체정보입니다.",
            "results": results,
            "http_status": 200
        }
    elif choice == "2":
        session.pop("last_search_results", None)
        return {
            "status": "success",
            "message": "세션을 종료했습니다.",
            "http_status": 200
        }

    return {
        "status": "error",
        "message": "잘못된 선택입니다. '전체정보' 또는 '종료'를 입력해주세요.",
        "http_status": 400
    }








# =================================================
# value 기준 우선순위 리스트 생성
field_order = []
seen = set()
for v in field_map.values():
    if v not in seen:
        field_order.append(v)
        seen.add(v)


def sort_fields_by_field_map(r: dict) -> OrderedDict:
    ordered = OrderedDict()
    for key in field_order:
        if key in r:
            ordered[key] = r[key]
    for k, v in r.items():
        if k not in ordered:
            ordered[k] = v
    return ordered


def get_full_member_info(results):
    if not results:
        return {
            "status": "error",
            "message": "회원 검색 결과가 없습니다.",
            "http_status": 404
        }
    full_data = [sort_fields_by_field_map(r) for r in results]
    return {
        "status": "success",
        "message": "회원 전체정보입니다.",
        "results": full_data,
        "http_status": 200
    }


def get_summary_info(results):
    summaries = [_line(r) for r in results]
    return {
        "status": "success",
        "message": "회원 요약정보입니다.",
        "summary": summaries,
        "http_status": 200
    }


def get_compact_info(results):
    compacts = [_compact_row(r) for r in results]
    return {
        "status": "success",
        "message": "회원 간략정보입니다.",
        "results": compacts,
        "http_status": 200
    }





















# ======================================================================================
# ✅ 회원 등록 (라우트)
# ======================================================================================
def register_member_func(data=None):

    """
    회원 등록 함수 (라우트 아님)
    📌 설명:
    - 자연어 요청문: "회원등록 이판주 12345678 010-2759-9001"
    - JSON 입력: {"회원명": "이판주", "회원번호": "12345678", "휴대폰번호": "010-2759-9001"}
    - JSON 입력(간단): {"회원명": "이판주"}
    - JSON 입력(중간): {"회원명": "이판주", "회원번호": "12345678"}
    """
    try:
        # ✅ query 감싸진 구조와 일반 dict 모두 지원
        if data and isinstance(data, dict):
            query = data
        elif hasattr(g, "query") and isinstance(g.query, dict):
            query = g.query.get("query", g.query)
        else:
            query = {}




        raw_text = query.get("raw_text")


        name, number, phone = "", "", ""




        # 1) 자연어 입력 기반 파싱
        if raw_text:
            parts = raw_text.split()
            for part in parts:
                if re.fullmatch(r"[가-힣]{2,10}", part):  # 이름
                    name = name or part
                elif re.fullmatch(r"\d{5,8}", part):   # 회원번호
                    number = number or part
                elif re.fullmatch(r"(010-\d{3,4}-\d{4}|010\d{7,8})", part):  # 휴대폰
                    phone = phone or part





        # 2) JSON 입력 방식
        if isinstance(query, dict):
            if query.get("회원명"):
                name = query.get("회원명", name).strip()
            if query.get("회원번호"):
                number = query.get("회원번호", number).strip()
            if query.get("휴대폰번호"):
                phone = query.get("휴대폰번호", phone).strip()

        if not name:
            return {
                "status": "error",
                "message": "회원명은 필수 입력 항목입니다.",
                "http_status": 400
            }

        result = register_member_internal(name, number, phone)
        return {**result, "http_status": 201}

    except ValueError as ve:
        return {
            "status": "error",
            "message": str(ve),
            "http_status": 400
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e),
            "http_status": 500
        }







# ======================================================================================
# ✅ JSON 기반 회원 수정/저장 API
# ======================================================================================
def save_member_func():
    """
    회원 저장/수정 함수 (라우트 아님)
    📌 설명:
    - 자연어 요청문을 파싱하여 회원을 신규 등록하거나, 기존 회원 정보를 수정합니다.
    - 업서트(Upsert) 기능: 없으면 등록, 있으면 수정
    📥 입력 예시:
    {
      "요청문": "홍길동 회원번호 12345 휴대폰 010-1111-2222 주소 서울"
    }
    """
    try:
        query = g.query.get("query") if hasattr(g, "query") else None
        raw_text = g.query.get("raw_text") if hasattr(g, "query") else None

        # ✅ 요청문 추출
        요청문 = ""
        if isinstance(query, dict):
            요청문 = query.get("요청문") or query.get("회원명", "")
        elif isinstance(query, str):
            요청문 = query
        if not 요청문 and raw_text:
            요청문 = raw_text

        if not 요청문:
            return {
                "status": "error",
                "message": "입력 문장이 없습니다.",
                "http_status": 400
            }

        # ✅ 파싱
        name, number, phone, lineage = parse_registration(요청문)
        if not name:
            return {
                "status": "error",
                "message": "회원명을 추출할 수 없습니다.",
                "http_status": 400
            }

        # ✅ 주소 기본값 처리
        address = ""
        if isinstance(query, dict):
            address = query.get("주소") or query.get("address", "")

        # ✅ 시트 접근
        sheet = get_member_sheet()
        headers = [h.strip() for h in sheet.row_values(1)]
        rows = sheet.get_all_records()

        # ✅ 기존 회원 여부 확인 (수정)
        for i, row in enumerate(rows):
            if str(row.get("회원명", "")).strip() == name:
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

                return {
                    "status": "success",
                    "message": f"{name} 기존 회원 정보 수정 완료",
                    "http_status": 200
                }

        # ✅ 신규 등록
        new_row = [""] * len(headers)
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
        return {
            "status": "success",
            "message": f"{name} 회원 신규 등록 완료",
            "http_status": 201
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e),
            "http_status": 500
        }



# ======================================================================================
# ✅ 회원 삭제 API
# ======================================================================================
def delete_member_func(data=None):
    """
    회원 삭제 함수 (회원 전체 삭제 + 특정 필드 삭제 지원)
    - 자연어 입력:
        "회원명 휴대폰번호 삭제"
        "회원명 삭제 휴대폰번호, 주소"
        "회원명 제거 메모 그리고 코드"
    - JSON 입력:
        {"회원명": "이판수", "삭제필드": ["주소", "코드"]}
    - 회원 전체 삭제:
        "회원명 삭제"
    """
    try:
        query = data or getattr(g, "query", {})

        # query 중첩 처리
        if isinstance(query, dict) and "query" in query and isinstance(query["query"], dict):
            query = query["query"]

        if isinstance(query, str):
            from utils import fallback_natural_search
            query = fallback_natural_search(query)

        print("[DEBUG] query:", query)

        raw_text = query.get("raw_text") or query.get("요청문", "")
        if isinstance(raw_text, dict):
            raw_text = ""

        name = (
            query.get("회원명")
            or query.get("name")
            or query.get("member_name")
            or ""
        ).strip()

        print("[DEBUG] name:", name)

        choice = str(query.get("choice", "")).strip()

        if not name:
            return {
                "status": "error",
                "message": "회원명은 필수 입력 항목입니다.",
                "http_status": 400
            }

        # ✅ DB 시트에서 이름으로 검색
        sheet = get_member_sheet()
        rows = sheet.get_all_records()
        headers = sheet.row_values(1)

        candidates = [
            (idx, row)
            for idx, row in enumerate(rows, start=2)
            if str(row.get("회원명", "")).strip() == name
        ]

        if not candidates:
            return {
                "status": "error",
                "message": f"{name} 회원을 찾을 수 없습니다.",
                "http_status": 404
            }

        # ✅ 동명이인 처리
        if len(candidates) > 1 and not choice:
            return {

                "status": "need_choice",

                "message": f"{name} 회원이 여러 명 존재합니다. 삭제할 번호(choice)를 선택하세요.",
                "candidates": [
                    {"번호": i + 1, "회원명": r.get("회원명"), "회원번호": r.get("회원번호"), "휴대폰번호": r.get("휴대폰번호")}
                    for i, r in enumerate([c[1] for c in candidates])
                ],
                "http_status": 200
            }

        target_row = candidates[0][0] if len(candidates) == 1 else candidates[int(choice) - 1][0]

        # --------------------------
        # 🔽 필드 삭제 요청 처리
        # --------------------------
        fields_to_delete = []

        # JSON 입력: 삭제필드 리스트 지원
        if isinstance(query, dict) and "삭제필드" in query and isinstance(query["삭제필드"], list):
            for f in query["삭제필드"]:
                normalized_field = field_map.get(f, f)
                if normalized_field in MEMBER_FIELDS and normalized_field != "회원명":
                    fields_to_delete.append(normalized_field)

        # 자연어 입력 처리
        if isinstance(raw_text, str) and raw_text:
            # 패턴1: "<이름> 필드1, 필드2 삭제"
            m1 = re.match(rf"^{name}\s+(.+?)\s*(삭제|제거|지워줘|없애)$", raw_text)
            # 패턴2: "<이름> (삭제|제거) 필드1, 필드2"
            m2 = re.match(rf"^{name}\s+(삭제|제거|지워줘|없애)\s+(.+)$", raw_text)

            if m1:
                fields_text = m1.group(1)
            elif m2:
                fields_text = m2.group(2)
            else:
                fields_text = ""

            if fields_text:
                # 쉼표/그리고 분리
                parts = re.split(r"[,\s]+그리고\s+|,", fields_text)
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    normalized_field = field_map.get(part, part)
                    if normalized_field in MEMBER_FIELDS and normalized_field != "회원명":
                        fields_to_delete.append(normalized_field)

        if fields_to_delete:
            updated = []
            for field in fields_to_delete:
                if field in headers:
                    col = headers.index(field) + 1
                    safe_update_cell(sheet, target_row, col, "")
                    updated.append(field)

            return {
                "status": "success",
                "message": f"✅ 회원 [{name}]의 [{', '.join(updated)}] 항목 삭제 완료",
                "deleted_fields": updated,
                "http_status": 200,
            }

        # --------------------------
        # 🔽 회원 전체 삭제 처리
        # --------------------------
        member_number = candidates[0][1].get("회원번호", "")
        result = delete_member_internal(name, member_number)

        if isinstance(result, dict):
            return {**result, "http_status": result.get("http_status", 200)}
        elif isinstance(result, tuple):
            status, message = result
            return {
                "status": status,
                "message": message,
                "http_status": 200 if status in ("ok", "success") else 400
            }
        else:
            return {
                "status": "success" if result else "error",
                "message": f"{name} ({member_number}) 회원 삭제 {'완료' if result else '실패'}",
                "http_status": 200 if result else 400
            }

    except Exception as e:
        import traceback; traceback.print_exc()
        return {
            "status": "error",
            "message": str(e),
            "http_status": 500
        }












# ======================================================================================
# ✅ 자연어 요청 회원 삭제 라우트
# ======================================================================================




# ✅ member_fields.py
MEMBER_FIELDS = [
    "회원명", "회원번호", "휴대폰번호", "특수번호", "가입일자", "생년월일", "통신사", "친밀도",
    "근무처", "계보도", "소개한분", "주소", "메모", "코드", "카드사", "카드주인", "카드번호",
    "유효기간", "비번", "카드생년월일", "분류", "회원단계", "연령/성별", "직업", "가족관계",
    "니즈", "애용제품", "콘텐츠", "습관챌린지", "비즈니스시스템", "GLC프로젝트", "리더님", "특수번호"
    ]


# 전화번호 포맷 함수 (없으면 추가)
def format_phone(v: str) -> str:
    digits = re.sub(r"\D", "", v)
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    elif len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return v


def update_member_func(data: dict = None):
    """
    회원 정보 수정 (자연어/JSON 요청 지원)
    - 여러 필드 동시 수정 가능
    - 동일 이름 회원 존재 시 choice 로 특정 회원만 수정
    - 회원번호, 휴대폰번호, 특수번호는 숫자 패턴으로 자동 인식
    - 수정 시 기존 값을 공란("")으로 지운 후 새 값 입력
    """
    try:
        # --------------------------
        # 1. 입력 데이터 확보
        # --------------------------
        query = {}
        if hasattr(g, "query") and isinstance(g.query, dict):
            query.update(g.query)
        if data and isinstance(data, dict):
            query.update(data)
            if "query" in data and isinstance(data["query"], dict):
                query.update(data["query"])   # ✅ 중첩 query 병합


        # ✅ raw_text 초기화 및 타입 보정
        raw_text = query.get("raw_text") or query.get("요청문") or ""
        if not isinstance(raw_text, str):
            raw_text = str(raw_text or "")   # ✅ dict/None 방지용
        print(f"[DEBUG] raw_text type={type(raw_text)}, value={raw_text}")

        member_name = query.get("회원명")


        if not raw_text.strip():
            return {"status": "error", "message": "❌ 요청문이 비어 있습니다.", "http_status": 400}


        # ✅ raw_text에서 회원명 추출 시도
        # 케이스A: "<이름> 수정|변경|업데이트 ..."
        m = re.match(r"^([가-힣]{2,4})\s+(수정|변경|업데이트)\s+", raw_text)
        if m:
            member_name = m.group(1)
    
        # 케이스B: "회원수정|회원변경|회원업데이트 <이름> ..."
        m0 = re.match(r"^회원\s*(수정|변경|업데이트)\s*([가-힣]{2,4})\s+", raw_text)
        if m0:
            member_name = m0.group(2)





        print("DEBUG update_member_func >>> data =", data)
        print("DEBUG update_member_func >>> query =", query)
        print("DEBUG update_member_func >>> member_name =", member_name)
        print(">>> raw_text =", raw_text)

        # --------------------------
        # 2. 수정할 필드/값 추출
        # --------------------------
        updates = {}

        # ✅ JSON 기반 필드 처리
        for key, value in query.items():
            standard_key = field_map.get(key, key)
            if standard_key in MEMBER_FIELDS and standard_key != "회원명":
                updates[standard_key] = value.strip() if isinstance(value, str) else value

        # ✅ 숫자 기반 (휴대폰번호, 회원번호)
        for k, v in query.items():
            if isinstance(v, str):
                digits = re.sub(r"\D", "", v)
                if digits == v:  # 숫자만 있을 때만 회원번호로 간주
                    if re.fullmatch(r"\d{5,8}", digits):
                        updates["회원번호"] = digits
                if re.fullmatch(r"010\d{8}", digits):
                    updates["휴대폰번호"] = format_phone(v)

       
      
        # ✅ 자연어 기반 필드 처리
        if isinstance(raw_text, str) and raw_text:
            # 케이스0: "회원수정|회원변경|회원업데이트 <이름> ..." (여러 필드)
            m0 = re.match(r"^회원\s*(수정|변경|업데이트)\s*([가-힣]{2,4})\s+(.+)$", raw_text)
            if m0:
                _, member_name, fields_text = m0.groups()

            else:
                # 케이스1: "<이름> 수정|변경|업데이트 ..." (여러 필드)
                m1 = re.match(r"^([가-힣]{2,4})\s+(?:수정|변경|업데이트)\s+(.+)$", raw_text)
                if m1:
                    member_name, fields_text = m1.groups()
                else:
                    # 케이스2: "<이름> <필드> 수정|변경|업데이트 <값>" (단일 필드)
                    m2 = re.match(r"^([가-힣]{2,4})\s+(\S+)\s+(수정|변경|업데이트)\s+(.+)$", raw_text)
                    if m2:
                        member_name, raw_field, _, new_value = m2.groups()
                        normalized_field = field_map.get(raw_field, raw_field)
                        if normalized_field == "회원명":
                            return {"status": "error", "message": "❌ 회원명은 수정할 수 없습니다.", "http_status": 400}
                        if normalized_field in MEMBER_FIELDS:
                            updates[normalized_field] = new_value.strip()

            # 여러 필드 처리 (쉼표/그리고)
            if "fields_text" in locals():
                parts = re.split(r"[,\s]+그리고\s+|,", fields_text)
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    m2 = re.match(r"(\S+)\s+(.+)", part)
                    if m2:
                        raw_field, new_value = m2.groups()
                        normalized_field = field_map.get(raw_field, raw_field)
                        if normalized_field == "회원명":
                            return {"status": "error", "message": "❌ 회원명은 수정할 수 없습니다.", "http_status": 400}
                        if normalized_field in MEMBER_FIELDS:
                            updates[normalized_field] = new_value.strip()
                    else:
                        inferred = fallback_natural_search(part)
                        for k, v in inferred.items():
                            if k in MEMBER_FIELDS and k != "회원명":
                                updates[k] = v

            # 케이스3: "<이름> 수정 특수번호 XXX"
            m3 = re.match(r"^([가-힣]{2,4})\s+(?:수정|변경|업데이트)\s+특수번호\s+(.+)$", raw_text)
            if m3:
                member_name, new_value = m3.groups()
                updates["특수번호"] = new_value.strip()






        # --------------------------
        # 3. 유효성 검사
        # --------------------------
        if not member_name:
            return {"status": "error", "message": "❌ 회원명이 필요합니다.", "http_status": 400}
        if not updates:
            return {"status": "error", "message": "❌ 수정할 필드가 없습니다.", "http_status": 400}

        # --------------------------
        # 4. 회원 검색
        # --------------------------
        sheet = get_member_sheet()
        rows = sheet.get_all_records()
        headers = sheet.row_values(1)

        candidates = [
            (idx, row)
            for idx, row in enumerate(rows, start=2)
            if str(row.get("회원명", "")).strip() == member_name.strip()
        ]

        if not candidates:
            return {"status": "error", "message": f"❌ 회원 '{member_name}'을(를) 찾을 수 없습니다.", "http_status": 404}

        # --------------------------
        # 5. 동명이인 처리
        # --------------------------
        choice = query.get("choice")
        if len(candidates) > 1 and not choice:
            return {
                "status": "need_choice",
                "message": f"⚠️ 동일 이름 회원 '{member_name}'이(가) {len(candidates)}명 있습니다. 번호를 선택하세요.",
                "candidates": [
                    {
                        "choice": i + 1,
                        "회원명": row.get("회원명"),
                        "회원번호": row.get("회원번호"),
                        "휴대폰번호": row.get("휴대폰번호"),
                    }
                    for i, (_, row) in enumerate(candidates)
                ],
                "http_status": 200,
            }

        target_row = candidates[0][0] if len(candidates) == 1 else candidates[int(choice) - 1][0]

        # --------------------------
        # 6. 수정 반영
        # --------------------------
        for field, value in updates.items():
            if field in headers:
                col = headers.index(field) + 1
                safe_update_cell(sheet, target_row, col, "")
                safe_update_cell(sheet, target_row, col, value)

        return {
            "status": "success",
            "message": f"✅ 회원 [{member_name}] 수정 완료",
            "updated_fields": updates,
            "http_status": 200,
        }

    except Exception as e:
        import traceback; traceback.print_exc()
        return {"status": "error", "message": str(e), "http_status": 500}













# ======================================================================================
# ✅ 자연어 요청 회원 삭제 라우트
# ======================================================================================
# routes/routes_member.py
import re
from flask import g
from utils.sheets import get_member_sheet, safe_update_cell

MEMBER_FIELDS = [
    "회원명", "회원번호", "휴대폰번호", "특수번호", "가입일자", "생년월일", "통신사", "친밀도",
    "근무처", "계보도", "소개한분", "주소", "메모", "코드", "카드사", "카드주인", "카드번호",
    "유효기간", "비번", "카드생년월일", "분류", "회원단계", "연령/성별", "직업", "가족관계",
    "니즈", "애용제품", "콘텐츠", "습관챌린지", "비즈니스시스템", "GLC프로젝트", "리더님"
]

def delete_member_field_nl_func(data: dict = None):
    """
    회원 필드 삭제 (자연어 기반)
    예시:
      - "홍길동 주소 삭제"
      - "홍길동 휴대폰번호 메모 삭제"
    """
    try:
        raw_text = ""
        if hasattr(g, "query"):
            if isinstance(g.query, dict):
                raw_text = g.query.get("query", "")
            elif isinstance(g.query, str):
                raw_text = g.query
        if not raw_text and data:
            raw_text = data.get("query", "")

        if not raw_text:
            return {"status": "error", "message": "❌ 삭제할 요청문이 없습니다.", "http_status": 400}

        parts = raw_text.split()
        if len(parts) < 2:
            return {"status": "error", "message": "❌ 회원명과 필드명이 필요합니다.", "http_status": 400}

        member_name = parts[0]
        fields = [p for p in parts[1:] if p != "삭제"]

        if not fields:
            return {"status": "error", "message": "❌ 삭제할 필드명이 없습니다.", "http_status": 400}

        # DB 시트
        sheet = get_member_sheet()
        rows = sheet.get_all_records()
        header = sheet.row_values(1)

        # 회원 찾기 (동명이인 대비)
        candidates = []
        for idx, row in enumerate(rows, start=2):
            if str(row.get("회원명", "")).strip() == member_name.strip():
                candidates.append((idx, row))

        if not candidates:
            return {"status": "error", "message": f"❌ 회원 '{member_name}'을(를) 찾을 수 없습니다.", "http_status": 404}

        choice = (data or {}).get("choice") or (g.query.get("choice") if isinstance(g.query, dict) else None)
        if len(candidates) > 1 and not choice:
            return {
                "status": "need_choice",
                "message": f"⚠️ 동일 이름 회원 '{member_name}'이(가) {len(candidates)}명 있습니다. 번호를 선택하세요.",
                "candidates": [
                    {"choice": i + 1, "회원명": r.get("회원명"), "회원번호": r.get("회원번호"), "휴대폰번호": r.get("휴대폰번호")}
                    for i, (_, r) in enumerate(candidates)
                ],
                "http_status": 200
            }

        if len(candidates) == 1:
            target_row = candidates[0][0]
        else:
            try:
                target_row = candidates[int(choice) - 1][0]
            except Exception:
                return {"status": "error", "message": "❌ 올바른 choice 번호를 선택하세요.", "http_status": 400}

        # 필드 삭제 처리
        updated_fields = []
        for f in fields:
            if f in MEMBER_FIELDS and f in header:
                col_idx = header.index(f) + 1
                safe_update_cell(sheet, target_row, col_idx, "")
                updated_fields.append(f)
            else:
                if re.fullmatch(r"\d{5,8}", f):
                    if "회원번호" in header:
                        col_idx = header.index("회원번호") + 1
                        safe_update_cell(sheet, target_row, col_idx, "")
                        updated_fields.append("회원번호")
                elif re.fullmatch(r"010\d{7,8}", f) or "휴대" in f:
                    if "휴대폰번호" in header:
                        col_idx = header.index("휴대폰번호") + 1
                        safe_update_cell(sheet, target_row, col_idx, "")
                        updated_fields.append("휴대폰번호")

        if not updated_fields:
            return {"status": "error", "message": f"❌ 삭제할 필드를 찾을 수 없습니다. (입력={fields})", "http_status": 400}

        return {
            "status": "success",
            "intent": "delete_member_field_nl_func",
            "message": f"✅ 회원 '{member_name}'의 {', '.join(updated_fields)} 필드를 삭제했습니다.",
            "http_status": 200
        }

    except Exception as e:
        import traceback; traceback.print_exc()
        return {"status": "error", "message": str(e), "http_status": 500}








def handle_update_member(query: str):
    import re

    # dict가 들어오면 문자열 추출
    if isinstance(query, dict):
        query = query.get("요청문") or query.get("raw_text") or ""

    m = re.match(r"([가-힣]{2,4})\s+(주소|전화번호|이메일)\s+(수정|변경|업데이트)\s+(.+)", query)
    if not m:
        return {
            "status": "error",
            "message": "수정할 내용을 파악할 수 없습니다.",
            "http_status": 400
        }

    name, field, _, value = m.groups()

    success = update_member_info(name, field, value)
    if not success:
        return {
            "status": "error",
            "message": f"{name}님의 {field} 수정 실패",
            "http_status": 500,
        }

    return {
        "status": "success",
        "message": f"{name}님의 {field}가 '{value}'로 수정되었습니다.",
        "http_status": 200,
    }







