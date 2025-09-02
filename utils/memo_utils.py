# utils/memo_utils.py
from datetime import datetime



# 📌 예시 데이터 (실제 환경에서는 API 결과로 대체)
def get_memo_results(query):
    return [
        {"날짜": "2025-08-27", "내용": "오늘 오후에 비가 온다 했는데 비는 오지 않고 날은 무덥습니다", "회원명": "이태수", "종류": "개인일지"},
        {"날짜": "2025-08-26", "내용": "오늘은 포항으로 후원을 가고 있습니다. 하늘에 구름이 많고 오후에는 비가 온다고 합니다", "회원명": "이태수", "종류": "개인일지"},
        {"날짜": "2025-08-10", "내용": "오늘은 비가 오지 않네요", "회원명": "이판사", "종류": "개인일지"},
        {"날짜": "2025-08-04", "내용": "이경훈을 상담했습니다. 비도 많이 옵니다", "회원명": "이태수", "종류": "상담일지"},
        {"날짜": "2025-08-26", "내용": "오늘 하늘에 구름이 많이 꼈고 저녁에 비가 온다고 하는데 확실하지 않습니다", "회원명": "이태수", "종류": "활동일지"},
    ]


# 📌 결과 포맷터 (개인일지 / 상담일지 / 활동일지 블록 구분)
def format_memo_results(results):
    """
    검색된 메모 결과를 정리해서 문자열 블록으로 반환
    - 날짜는 YYYY-MM-DD 형식으로만 출력
    - 정렬은 하루 단위 최신순
    - 출력 순서: 활동일지 → 상담일지 → 개인일지
    - 출력 형식: · (YYYY-MM-DD, 회원명) 내용
    """
    # ✅ 하루 단위 최신순 정렬
    try:
        results.sort(
            key=lambda r: datetime.strptime(str(r.get("날짜", "1900-01-01")).split()[0], "%Y-%m-%d"),
            reverse=True
        )
    except Exception:
        pass

    personal, counsel, activity = [], [], []

    for r in results:
        date = str(r.get("날짜") or "").split()[0]
        content = r.get("내용") or ""
        member = r.get("회원명") or ""
        mode = r.get("일지종류") or r.get("종류")

        if date and member:
            line = f"· ({date}, {member}) {content}"
        elif date:
            line = f"· ({date}) {content}"
        elif member:
            line = f"· ({member}) {content}"
        else:
            line = f"· {content}"

        if mode == "개인일지":
            personal.append(line)
        elif mode == "상담일지":
            counsel.append(line)
        elif mode == "활동일지":
            activity.append(line)

    output_text = "🔎 검색 결과\n\n"
    if activity:
        output_text += "🗂 활동일지\n" + "\n".join(activity) + "\n\n"
    if counsel:
        output_text += "📂 상담일지\n" + "\n".join(counsel) + "\n\n"
    if personal:
        output_text += "📒 개인일지\n" + "\n".join(personal) + "\n\n"

    return {
        "text": output_text.strip(),
        "lists": {
            "활동일지": activity,
            "상담일지": counsel,
            "개인일지": personal
        }
    }


def filter_results_by_member(results, member_name):
    """
    검색 결과(results) 중 특정 회원명(member_name)만 필터링
    """
    if not member_name:
        return results
    return [r for r in results if r.get("회원명") == member_name]

