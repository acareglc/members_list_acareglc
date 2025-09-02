# utils/http.py
import os
import requests
from typing import Any, Dict, Optional

# ⬇️ 로컬에서만 .env 자동 로드
if os.getenv("RENDER") is None:
    try:
        from dotenv import load_dotenv
        if os.path.exists(".env"):
            load_dotenv(".env")
    except Exception:
        pass

DEFAULT_TIMEOUT = int(os.getenv("HTTP_DEFAULT_TIMEOUT", "30"))
MEMBERSLIST_API_URL = os.getenv("MEMBERSLIST_API_URL")


class MemberslistError(RuntimeError):
    """Memberslist API 호출 실패 예외"""
    pass


def _normalize_timeout(t: Optional[int]) -> int:
    try:
        return int(t) if t is not None else DEFAULT_TIMEOUT
    except Exception:
        return DEFAULT_TIMEOUT


def _ensure_json_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    raise MemberslistError(f"payload는 dict여야 합니다. (got: {type(payload).__name__})")


def _post_json(url: str, payload: Dict[str, Any], timeout: Optional[int] = None) -> Dict[str, Any]:
    p = _ensure_json_payload(payload)
    to = _normalize_timeout(timeout)
    r = requests.post(url, json=p, timeout=to)
    r.raise_for_status()
    try:
        return r.json()
    except ValueError:
        # JSON 이 아니면 원문 텍스트라도 반환
        return {"ok": True, "raw": r.text}


def call_memberslist_add_orders(payload: Dict[str, Any], timeout: Optional[int] = None) -> Dict[str, Any]:
    """
    멤버리스트 API로 주문 데이터 전송.
    - 기본 URL(환경변수 MEMBERSLIST_API_URL)에 먼저 요청
    - 404 이면 add_orders <-> addOrders 상호 변환하여 재시도 (호환성)
    """
    if not MEMBERSLIST_API_URL:
        raise MemberslistError("MEMBERSLIST_API_URL 미설정")

    url = MEMBERSLIST_API_URL.rstrip("/")
    try:
        return _post_json(url, payload, timeout)
    except requests.HTTPError as e:
        status = getattr(e.response, "status_code", None)
        if status == 404:
            # 경로 호환 처리
            if url.endswith("/add_orders"):
                fallback = url[:-len("/add_orders")] + "/addOrders"
            elif url.endswith("/addOrders"):
                fallback = url[:-len("/addOrders")] + "/add_orders"
            else:
                # 예상 경로가 아니면 에러 메시지 명확화
                raise MemberslistError(f"404 Not Found: {url}") from e
            return _post_json(fallback, payload, timeout)

        detail = getattr(e.response, "text", str(e))
        raise MemberslistError(f"Memberslist HTTPError: {status} | {detail}") from e
    except requests.RequestException as e:
        raise MemberslistError(f"Memberslist RequestException: {e}") from e



IMPACT_API_URL = os.getenv("IMPACT_API_URL")

class ImpactError(Exception):
    pass

def call_impact_sync(payload: dict):
    """
    임팩트 API로 데이터 동기화
    - 기본 URL: IMPACT_API_URL (예: /sync)
    - payload 예시: {"type": "order", "member": "...", "orders": [...], "source": "sheet_gpt"}
    """
    if not IMPACT_API_URL:
        raise ImpactError("IMPACT_API_URL 미설정")

    try:
        r = requests.post(IMPACT_API_URL, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        raise ImpactError(f"임팩트 API 요청 실패: {str(e)}")
