# utils/openai_utils.py
import os
import io
import re
import json
import base64
import requests
from typing import List, Dict, Any

from config import OPENAI_API_KEY, OPENAI_API_URL





# ⬇️ 로컬에서만 .env 자동 로드
if os.getenv("RENDER") is None:
    try:
        from dotenv import load_dotenv
        if os.path.exists(".env"):
            load_dotenv(".env")
    except Exception:
        pass

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL")  # e.g. https://api.openai.com/v1/chat/completions
MODEL_NAME     = os.getenv("OPENAI_MODEL", "gpt-4o")


def _ensure_orders_list(data: Any) -> List[Dict[str, Any]]:
    """응답을 무조건 orders 리스트 형태로 보정"""
    if isinstance(data, dict) and "orders" in data:
        return data["orders"] or []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return []


def openai_vision_extract_orders(image_bytes: io.BytesIO) -> List[Dict[str, Any]]:
    """
    이미지 → 주문 JSON 추출 (OpenAI Vision 모델)
    반환: [{'제품명':..., '제품가격':..., 'PV':..., '주문자_고객명':..., '주문자_휴대폰번호':..., '배송처':..., '결재방법': '', '수령확인': ''}, ...]
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY 미설정")
    if not OPENAI_API_URL:
        raise RuntimeError("OPENAI_API_URL 미설정")

    image_b64 = base64.b64encode(image_bytes.getvalue()).decode("utf-8")

    prompt = (
        "이미지를 분석하여 JSON 형식으로 추출하세요. "
        "여러 개의 제품이 있을 경우 'orders' 배열에 모두 담으세요. "
        "질문하지 말고 추출된 orders 전체를 그대로 저장할 준비를 하세요. "
        "(이름, 휴대폰번호, 주소)는 소비자 정보임. "
        "회원명, 결재방법, 수령확인, 주문일자 무시. "
        "필드: 제품명, 제품가격, PV, 주문자_고객명, 주문자_휴대폰번호, 배송처"
    )

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
            ]
        }],
        "temperature": 0
    }

    r = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=60)
    r.raise_for_status()

    resp = r.json()
    msg = resp["choices"][0]["message"]
    content = msg.get("content", "")

    # 문자열/리스트 모두 대응
    if isinstance(content, list):
        content_text = " ".join(
            c.get("text", "")
            for c in content
            if isinstance(c, dict) and c.get("type") == "text"
        ).strip()
    else:
        content_text = str(content).strip()

    # 코드펜스(json/일반) 제거
    clean = re.sub(r"```(?:json)?|```", "", content_text, flags=re.IGNORECASE).strip()

    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        # 모델이 순수 JSON이 아닌 텍스트를 반환한 경우, raw 텍스트로 보존
        data = {"raw_text": content_text}

    orders_list = _ensure_orders_list(data)

    # 정책: 결재방법/수령확인은 공란 유지 + 문자열 필드 trim
    for o in orders_list:
        o.setdefault("결재방법", "")
        o.setdefault("수령확인", "")
        for k, v in list(o.items()):
            if isinstance(v, str):
                o[k] = v.strip()

    return orders_list










# --------------------------------------------------
# GPT Vision: 이미지 → 주문 JSON
# --------------------------------------------------
# ===============================================
# ✅ GPT Vision 기반 이미지 파서
# ===============================================
def extract_order_from_uploaded_image(image_bytes):
    """
    주문서 이미지에서 JSON 구조의 주문 데이터를 추출합니다.
    - 입력: BytesIO 이미지
    - 출력: { "orders": [...] } 구조
    """
    image_base64 = base64.b64encode(image_bytes.getvalue()).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = (
        "이미지를 분석하여 JSON 형식으로 추출하세요. "
        "여러 개의 제품이 있을 경우 'orders' 배열에 모두 담으세요. "
        "질문하지 말고 추출된 orders 전체를 그대로 저장할 준비를 하세요. "
        "(이름, 휴대폰번호, 주소)는 소비자 정보임. "
        "회원명, 결재방법, 수령확인, 주문일자 무시. "
        "필드: 제품명, 제품가격, PV, 주문자_고객명, 주문자_휴대폰번호, 배송처"
    )

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }}
                ]
            }
        ],
        "temperature": 0
    }

    response = requests.post(OPENAI_API_URL, headers=headers, json=payload)
    response.raise_for_status()

    result_text = response.json()["choices"][0]["message"]["content"]

    # 코드블록 제거
    clean_text = re.sub(r"```(?:json)?", "", result_text).strip()

    try:
        order_data = json.loads(clean_text)
        return order_data
    except json.JSONDecodeError:
        return {"raw_text": result_text}
    
    

# --------------------------------------------------
# GPT Chat: 자연어 → 주문 JSON
# --------------------------------------------------
def parse_order_from_text(text: str):
    """자연어 주문 문장을 OpenAI Chat API에 보내 JSON 추출"""
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "자연어 주문 문장을 JSON으로 변환해 주세요."},
            {"role": "user", "content": text}
        ],
        "temperature": 0.0
    }

    resp = requests.post(OPENAI_API_URL, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()
