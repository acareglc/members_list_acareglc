# routes/memos.py
import re
from flask import g
from parser.parse import save_memo, parse_memo,  find_memo
from utils import handle_search_memo
from utils.sheets import get_worksheet
from datetime import datetime

sheet_name, keywords, member_name = None, [], None
start_date, end_date = None, None  # ✅ 추가



# ────────────────────────────────────────────────────────────────────
# 공통 헬퍼
# ────────────────────────────────────────────────────────────────────
def _norm(s: str) -> str:
    return (s or "").strip()

def _get_text_from_g() -> str:
    """
    g.query에서 자연어 텍스트를 안전하게 추출
    우선순위: raw_text(str) > query(str) > query(dict)["text"/"요청문"/"메모"/"내용"]
    """
    if not hasattr(g, "query") or not isinstance(g.query, dict):
        return ""
    # 1) raw_text 우선
    rt = g.query.get("raw_text")
    if isinstance(rt, str) and rt.strip():
        return rt.strip()

    q = g.query.get("query")
    # 2) query가 문자열
    if isinstance(q, str) and q.strip():
        return q.strip()
    # 3) query가 dict면 대표 키들에서 추출
    if isinstance(q, dict):
        for k in ("text", "요청문", "메모", "내용"):
            v = q.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""

# ────────────────────────────────────────────────────────────────────
# 1) 메모/일지 자동 분기 허브
# ────────────────────────────────────────────────────────────────────
def memo_find_auto_func():
    """
    메모/일지 자동 분기 허브
    - '저장' 포함 → memo_save_auto_func
    - '검색' 포함 → search_memo_from_text_func
    - 그 외 → search_memo_func
    """
    try:
        text = _get_text_from_g()
        if "저장" in text:
            return memo_save_auto_func(text)      # ✅ text 넘겨주기
        if "검색" in text:
            return search_memo_from_text_func()   # g.query에서 꺼냄
        return search_memo_func()
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"status": "error", "message": str(e), "http_status": 500}
    

    
# ────────────────────────────────────────────────────────────────────
# 2) 자연어 메모 저장
# ────────────────────────────────────────────────────────────────────
def memo_save_auto_func(text: str):
    """
    자연어 문장을 받아 상담일지/개인일지/활동일지에 자동 저장
    """
    try:
        parts = text.strip().split(maxsplit=3)

        if len(parts) < 4:
            return {
                "status": "error",
                "message": f"❌ 입력 문장에서 회원명/일지종류/내용을 추출할 수 없습니다. (입력={text})",
                "http_status": 400,
            }

        # ✅ 파싱
        member_name = parts[0]       # 이태수
        diary_type = parts[1]        # 상담일지 / 개인일지 / 활동일지
        command = parts[2]           # 저장 (무시)
        content = parts[3]           # 오늘은 좋은 날씨

        # ✅ 시트명 매핑
        sheet_map = {
            "상담일지": "상담일지",
            "개인일지": "개인일지",
            "활동일지": "활동일지",
        }
        sheet_name = sheet_map.get(diary_type)
        if not sheet_name:
            return {
                "status": "error",
                "message": f"❌ 지원하지 않는 일지 종류입니다. (입력={diary_type})",
                "http_status": 400,
            }

        res = save_memo(sheet_name, member_name, content)
        return {"status": "success", "result": res, "http_status": 200}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"메모 저장 중 오류: {str(e)}",
            "http_status": 500,
        }





# ────────────────────────────────────────────────────────────────────
# 3) 자연어 기반 메모 검색
# ────────────────────────────────────────────────────────────────────
def search_memo_from_text_func():
    """
    자연어 기반 메모 검색 → JSON 기반과 동일한 흐름으로 검색
    """
    try:
        text = _get_text_from_g()
        if not text:
            return {"status": "error", "message": "검색 문장이 없습니다.", "http_status": 400}

        g.query = text  # 자연어 → g.query에 설정
        return search_memo_func()  # JSON 기반 검색 함수 호출

    except Exception as e:
        import traceback; traceback.print_exc()
        return {"status": "error", "message": str(e), "http_status": 500}





# ────────────────────────────────────────────────────────────────────
# 4) JSON 기반 메모 검색
# ────────────────────────────────────────────────────────────────────
def search_memo_func():
    """
    메모 검색 API
    - 자연어 입력 → parse_memo 통해 dict 변환
    - JSON 입력 → 그대로 사용
    - before_request에서 이미 dict로 파싱된 경우도 처리
    - "전체메모 검색 ..." → 상담일지+개인일지+활동일지 그룹핑
    - "동시" 키워드 → AND 검색 모드
    """
    try:
        q = getattr(g, "query", None)  # g.query 전체
        results = {}

        print("[DEBUG] raw g.query:", q)

        sheet_name, keywords, member_name = None, [], None

        # ----------------------------
        # 1) JSON / 자연어 / dict 분기
        # ----------------------------
        if isinstance(q, dict):
            query_data = q.get("query", q)
            sheet_name = query_data.get("일지종류", "").strip()
            member_name = query_data.get("회원명", "").strip()

            # ✅ keywords vs 검색어 보정
            if "keywords" in query_data:
                keywords = query_data.get("keywords", [])
            elif "검색어" in query_data:
                검색어 = query_data.get("검색어")
                if isinstance(검색어, str):
                    keywords = 검색어.strip().split()
                elif isinstance(검색어, list):
                    keywords = 검색어
                else:
                    keywords = []
            else:
                keywords = []

        else:
            # ✅ g.query가 문자열인 경우 (자연어 직접 입력)
            parsed = parse_memo(q) if q else {}
            start_date = parsed.get("start_date")
            end_date = parsed.get("end_date")



            print("[DEBUG] parse_memo output:", parsed)

            sheet_name = (parsed.get("일지종류") or "").strip()
            member_name = (parsed.get("회원명") or "").strip()


           

            if "keywords" in parsed:
                keywords = parsed["keywords"]
            elif "검색어" in parsed:
                keywords = parsed["검색어"].strip().split()
            else:
                keywords = []

        # ----------------------------
        # 2) keywords 정제
        # ----------------------------
        keywords = [kw.strip().lower() for kw in keywords if kw and kw.strip()]

        # ----------------------------
        # 2) sheet_name 검증
        # ----------------------------
        if not sheet_name:
            return {
                "status": "error",
                "message": "❌ 일지종류를 인식할 수 없습니다.",
                "http_status": 400
            }

        # ----------------------------
        # 2-1) "동시" 키워드 → AND 모드 전환
        # ----------------------------
        and_mode = False
        if "동시" in keywords:
            and_mode = True
            keywords = [kw for kw in keywords if kw != "동시"]

        # ----------------------------
        # 3) 검색 실행
        # ----------------------------
        if sheet_name == "전체":
            results = {}
            for sn in ["상담일지", "개인일지", "활동일지"]:
                core_results = search_memo_core(
                    sn,
                    keywords,
                    member_name=member_name,
                    and_mode=and_mode
                )
                print(f"[DEBUG] {sn} 검색 결과 {len(core_results)}건")
                results[sn] = core_results

        else:
            results = {
                sheet_name: search_memo_core(
                    sheet_name,
                    keywords,
                    member_name=member_name,
                    and_mode=and_mode
                )
            }


        # ----------------------------
        # 4) 반환
        # ----------------------------

        # 🔽 여기에 출력 코드 삽입
        results_data = results
        for category, memos in results_data.items():
            print(f"### {category}")
            for memo in memos:
                print(f"- 날짜: {memo.get('날짜')}")
                print(f"- 회원명: {memo.get('회원명')}")
                print(f"- 일지종류: {memo.get('일지종류')}")
                print(f"- 내용: {memo.get('내용')}\n")


        return {
            "status": "success",
            "intent": "search_memo",
            "results": results,
            "http_status": 200
        }

    except Exception as e:
        import traceback; traceback.print_exc()
        return {
            "status": "error",
            "message": str(e),
            "http_status": 500
        }











def search_memo_core(sheet_name, keywords, member_name=None,
                     start_date=None, end_date=None, limit=20,
                     and_mode=False, full_phrase=""):
    """
    메모 검색 Core
    - keywords: 검색 키워드 리스트
    - full_phrase: 키워드 전체 문장 기반 정확 검색
    - and_mode=True → 모든 키워드 포함(AND), 기본은 OR 검색
    """
    results = []
    sheet = get_worksheet(sheet_name)
    if not sheet:
        print(f"[ERROR] ❌ 시트를 가져올 수 없습니다: {sheet_name}")
        return []

    rows = sheet.get_all_records()

    # ✅ keywords 정규화
    keywords = [kw.strip().lower() for kw in keywords if kw and kw.strip()]
    full_phrase = full_phrase.strip().lower()

    start_dt, end_dt = None, None
    try:
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except Exception:
        pass

    for idx, row in enumerate(rows, start=1):
        content = str(row.get("내용", "")).strip()
        member = str(row.get("회원명", "")).strip()
        date_str = str(row.get("날짜", "")).strip()

        # ✅ 회원명 필터
        if member_name and member_name != "전체" and member != member_name:
            continue

        # ✅ 날짜 필터
        if date_str:
            try:
                row_date = datetime.strptime(date_str.split()[0], "%Y-%m-%d")
                if start_dt and row_date < start_dt:
                    continue
                if end_dt and row_date > end_dt:
                    continue
            except Exception:
                pass

        # ✅ 검색 대상: 회원명 + 내용 둘 다 포함
        search_target = f"{member.lower()} {content.lower()}"

        # ✅ 정확한 문장 일치 우선 검사
        if full_phrase and full_phrase not in search_target:
            continue

        # ✅ 키워드 검사 (AND/OR)
        if keywords:
            if and_mode:
                if not all(kw in search_target for kw in keywords):
                    continue
            else:
                if not any(kw in search_target for kw in keywords):
                    continue


        results.append({
            "날짜": date_str,
            "회원명": member,
            "내용": content,
            "일지종류": sheet_name
        })

        if len(results) >= limit:
            break

    print(f"[DEBUG] ✅ 최종 results({sheet_name}) | {len(results)}건")
    return results














# ────────────────────────────────────────────────────────────────────
# 5) 상담/개인/활동 일지 저장(JSON 전용)
# ────────────────────────────────────────────────────────────────────

def add_counseling_func():
    """
    상담일지/개인일지/활동일지 저장(JSON 전용)
    """
    try:
        q = g.query if hasattr(g, "query") and isinstance(g.query, dict) else None
        if not isinstance(q, dict):
            return {"status": "error", "message": "❌ 저장할 요청문이 없습니다.", "http_status": 400}

        # 필드 추출
        sheet_name = q.get("일지종류", "").strip() or "상담일지"
        member_name = q.get("회원명", "").strip()
        content = q.get("내용", "").strip() or q.get("text", "").strip()

        if not member_name or not content:
            return {"status": "error", "message": "❌ 회원명 또는 내용이 비어 있습니다.", "http_status": 400}

        # ✅ save_memo 호출 (항상 True/False 반환)
        ok = save_memo(sheet_name, member_name, content)

        return {
            "status": "success" if ok else "error",
            "intent": "add_counseling",
            "http_status": 201 if ok else 400
        }

    except Exception as e:
        import traceback; traceback.print_exc()
        return {"status": "error", "message": str(e), "http_status": 500}
