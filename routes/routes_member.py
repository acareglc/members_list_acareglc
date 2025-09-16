import re
import json
from collections import OrderedDict
from flask import g, request, Response, jsonify, session



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

        result = find_member_logic(name)

        if result.get("status") != "success":
            return {**result, "http_status": 404}

        members = result.get("results", [])
        if not members:
            return {"status": "error", "message": f"{name}에 해당하는 회원이 없습니다.", "http_status": 404}

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
def member_select():
    data = request.json or {}
    choice = str(data.get("choice", "")).strip()

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
def register_member_func():
    """
    회원 등록 함수 (라우트 아님)
    📌 설명:
    - 자연어 요청문: "회원등록 이판주 12345678 010-2759-9001"
    - JSON 입력: {"회원명": "이판주", "회원번호": "12345678", "휴대폰번호": "010-2759-9001"}
    """
    try:
        query = g.query.get("query")
        raw_text = g.query.get("raw_text")

        name, number, phone = "", "", ""

        # 1) 자연어 입력 기반 파싱
        if raw_text and "회원등록" in raw_text:
            parts = raw_text.split()
            for part in parts:
                if re.fullmatch(r"[가-힣]{2,4}", part):  # 이름
                    name = part
                elif re.fullmatch(r"\d{5,8}", part):   # 회원번호
                    number = part
                elif re.fullmatch(r"(010-\d{3,4}-\d{4}|\d{10,11})", part):  # 휴대폰
                    phone = part

        # 2) JSON 입력 방식
        if isinstance(query, dict):
            name = query.get("회원명", name).strip()
            number = query.get("회원번호", number).strip()
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
# ✅ 회원 수정
# ======================================================================================
def update_member_func():
    """
    회원 수정 함수 (라우트 아님)
    📌 설명:
    - g.query["query"] 또는 raw_text 에서 요청문을 추출하여 회원 정보를 수정
    - 자연어 요청문 예: "홍길동 주소 부산 해운대구로 변경"
    - JSON 입력 예: {"요청문": "홍길동 주소 부산 해운대구로 변경"}
    """
    try:
        query = g.query.get("query") if hasattr(g, "query") else None
        raw_text = g.query.get("raw_text") if hasattr(g, "query") else None

        요청문 = ""
        if isinstance(query, dict):
            요청문 = (query.get("요청문") or "").strip()
        elif isinstance(query, str):
            요청문 = query.strip()

        if not 요청문 and raw_text:
            요청문 = raw_text.strip()

        if not 요청문:
            return {
                "status": "error",
                "message": "요청문이 비어 있습니다.",
                "http_status": 400
            }

        result = update_member_internal(요청문)
        return {**result, "http_status": 200}

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
def delete_member_func():
    """
    회원 전체 삭제 함수 (라우트 아님)
    📌 설명:
    - 회원명을 기준으로 DB 시트에서 전체 행을 삭제합니다.
    - before_request 에서 g.query 에 값이 세팅되어 있어야 함.
    📥 입력(JSON 예시):
    {
      "회원명": "홍길동"
    }
    """
    try:
        query = g.query.get("query") if hasattr(g, "query") else None

        if isinstance(query, dict):
            name = (query.get("회원명") or "").strip()
        else:
            name = (query or "").strip()

        if not name:
            return {
                "status": "error",
                "message": "회원명은 필수 입력 항목입니다.",
                "http_status": 400
            }

        result, status = delete_member_internal(name)
        return {**result, "http_status": status}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e),
            "http_status": 500
        }





# ======================================================================================
# ✅ 자연어 요청 회원 삭제 라우트
# ======================================================================================
def delete_member_field_nl_func():
    """
    회원 필드 삭제 (자연어 기반)
    📌 설명:
    - 자연어 문장에서 특정 필드를 추출하여 해당 회원의 일부 필드를 삭제합니다.
    - '회원명', '회원번호'는 삭제 불가 (삭제 요청 자체를 막음)
    - '홍길동 삭제' → 전체 삭제 방지 (별도 API /delete_member 사용)

    📥 입력(JSON 예시):
    {
      "요청문": "이판여 주소랑 휴대폰번호 삭제"
    }
    """
    try:
        req = request.get_json(force=True)
        text = (req.get("요청문") or "").strip()

        if not text:
            return {"status": "error", "message": "요청문을 입력해야 합니다.", "http_status": 400}

        result, status = delete_member_field_nl_internal(text)
        return {**result, "http_status": status}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e), "http_status": 500}


