# utils/memo_utils.py

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
    personal, counsel, activity = [], [], []

    for r in results:
        date = r.get("날짜")
        content = r.get("내용")
        member = r.get("회원명")
        mode = r.get("종류")

        line = f"✍️ {date} {content} ({member})"

        if mode == "개인일지":
            personal.append(line)
        elif mode == "상담일지":
            counsel.append(line)
        elif mode == "활동일지":
            activity.append(line)

    output = "🔎 검색 결과\n\n"

    if personal:
        output += "📌 개인일지\n" + "\n".join(personal) + "\n\n"
    if counsel:
        output += "📌 상담일지\n" + "\n".join(counsel) + "\n\n"
    if activity:
        output += "📌 활동일지\n" + "\n".join(activity) + "\n\n"

    return output.strip()


# 📌 특정 회원 필터링 기능
def filter_results_by_member(results, member_name: str):
    """검색 결과 중 특정 회원만 필터링"""
    return [r for r in results if r.get("회원명") == member_name]
