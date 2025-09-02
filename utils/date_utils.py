import re
from datetime import datetime, timedelta, timezone

def now_kst() -> datetime:
    """한국시간(KST) 기준 현재 시각 반환"""
    return datetime.now(timezone(timedelta(hours=9)))


def process_order_date(raw_date: str) -> str:
    """
    주문 저장 시 날짜 입력 처리
    - "오늘", "어제", "내일" → 실제 날짜
    - YYYY-MM-DD / YYYY.MM.DD / YYYY/MM/DD → YYYY-MM-DD
    - 실패 시 오늘 날짜 반환
    """
    try:
        if not raw_date or raw_date.strip() == "":
            return now_kst().strftime('%Y-%m-%d')

        text = raw_date.strip()
        today = now_kst()

        if "오늘" in text:
            return today.strftime('%Y-%m-%d')
        elif "어제" in text:
            return (today - timedelta(days=1)).strftime('%Y-%m-%d')
        elif "내일" in text:
            return (today + timedelta(days=1)).strftime('%Y-%m-%d')

        try:
            dt = datetime.strptime(text, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

        match = re.search(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})", text)
        if match:
            y, m, d = match.groups()
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    except Exception as e:
        print(f"[날짜 파싱 오류] {e}")

    return now_kst().strftime('%Y-%m-%d')


def parse_dt(s: str):
    """
    문자열을 datetime 객체로 변환
    지원 포맷: YYYY-MM-DD HH:MM, YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
    실패하면 None 반환
    """
    if not s:
        return None
    s = s.strip()
    for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"]:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None
