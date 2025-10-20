그럼 지금까지 만든 파일들을 모듈화해서 깔끔하게 import 할 수 있도록 구조를 정리해드리겠습니다.

📂 제안하는 프로젝트 구조
project/
 ├─ app.py                # Flask 엔드포인트
 ├─ parser.py             # 일지 파싱/저장 함수
 ├─ config.py             # API_BASE, API_URLS, HEADERS 관리
 └─ utils/
     ├─ __init__.py       # utils 패키지 선언
     ├─ api.py            # post_api() - API 요청 함수
     ├─ sheets.py         # 구글시트 관련 함수
     └─ member.py         # 회원 관련 함수 (update_member_field 등)

📌 각 파일별 코드
1. config.py
import os
from urllib.parse import urljoin

API_BASE = os.getenv("API_BASE", "https://my-flask-api.com")
HEADERS = {"Content-Type": "application/json"}

API_URLS = {
    "counseling": urljoin(API_BASE, "/add_counseling"),
    "member_update": urljoin(API_BASE, "/updateMember"),
    "order": urljoin(API_BASE, "/save_order"),
}

2. utils/api.py
import requests
from config import API_URLS, HEADERS

def post_api(name: str, payload: dict):
    """사전 정의된 API 엔드포인트로 POST 요청"""
    if name not in API_URLS:
        raise ValueError(f"정의되지 않은 API 이름: {name}")
    url = API_URLS[name]
    r = requests.post(url, json=payload, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()

3. utils/sheets.py

(지금 쓰시는 get_ws, get_member_sheet, safe_update_cell 그대로 유지)

4. utils/member.py
from utils.api import post_api
from utils.sheets import get_member_sheet, safe_update_cell, header_maps

def update_member_field(member_name: str, field: str, value: str):
    """
    자연어 기반 회원 필드 업데이트 (API 호출)
    """
    member_name = (member_name or "").strip()
    field = (field or "").strip()
    value = (value or "").strip()

    post_api("member_update", {"요청문": f"{member_name} {field} ''"})
    post_api("member_update", {"요청문": f"{member_name} {field} {value}"})


def update_member_field_strict(member_name: str, field_name: str, value: str) -> bool:
    """
    DB 시트에 직접 접근해서 해당 회원의 특정 필드 값을 정확히 업데이트
    """
    sheet = get_member_sheet()
    headers, idx, _ = header_maps(sheet)

    if "회원명" not in idx:
        raise RuntimeError("DB 시트에 '회원명' 헤더가 없습니다.")
    if field_name not in idx:
        raise RuntimeError(f"DB 시트에 '{field_name}' 헤더가 없습니다.")

    member_col = idx["회원명"]
    field_col = idx[field_name]

    values = sheet.get_all_values()
    target_row = None
    for i, row in enumerate(values[1:], start=2):
        if len(row) >= member_col and row[member_col - 1].strip() == member_name.strip():
            target_row = i
            break

    if not target_row:
        return False

    return bool(safe_update_cell(sheet, target_row, field_col, value, clear_first=True))

5. parser.py

(앞서 만든 save_to_sheet, parse_request_line 포함)

6. app.py
import re, traceback
from flask import Flask, request, jsonify
from parser import save_to_sheet
from utils.api import post_api

try:
    app
except NameError:
    app = Flask(__name__)


@app.route('/add_counseling', methods=['POST'])
def add_counseling():
    try:
        data = request.get_json()
        text = data.get("요청문", "").replace(".", "").strip()

        replacements = {
            "개인 메모": "개인일지", "상담 일지": "상담일지",
            "활동 일지": "활동일지", "회원 메모": "회원메모",
            "제품 주문": "제품주문", "회원 주소": "회원주소"
        }
        for k, v in replacements.items():
            text = text.replace(k, v)

        sheet_keywords = [
            "상담일지", "개인일지", "활동일지", "회원메모", "제품주문", "회원주소",
            "상담 일지", "개인 일지", "활동 일지", "회원 메모", "제품 주문", "회원 주소"
        ]
        action_keywords = ["저장", "기록", "입력"]

        match = re.search(r"([가-힣]{2,10})\s*(상담\s*일지|개인\s*일지|활동\s*일지|회원\s*메모|회원\s*주소|제품\s*주문)", text)
        if not match:
            return jsonify({"message": "회원명을 인식할 수 없습니다."})
        member_name = match.group(1)

        matched_sheet = next((kw for kw in sheet_keywords if kw in text), None)
        if not matched_sheet:
            return jsonify({"message": "저장할 시트를 인식할 수 없습니다."})
        matched_sheet = matched_sheet.replace(" ", "")

        for kw in sheet_keywords + action_keywords:
            text = text.replace(kw, "")
        text = text.strip()
        text = re.sub(r'^[:：]\s*', '', text)

        if matched_sheet in ["상담일지", "개인일지", "활동일지"]:
            content = text.strip()
            if not content:
                return jsonify({"message": "저장할 내용이 비어 있습니다."}), 400
            if save_to_sheet(matched_sheet, member_name, content):
                return jsonify({"message": f"{member_name}님의 {matched_sheet} 저장이 완료되었습니다."})

        return jsonify({"message": "처리할 수 없는 시트입니다."})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

✅ 요약

config.py → API 주소 관리

utils/api.py → post_api

utils/member.py → 회원 관련 함수 (update_member_field 등)

parser.py → 파싱/저장 유틸

app.py → Flask 엔드포인트

이제 app.py 에서는 이렇게 호출하면 됩니다:

from parser.member import update_member_field

update_member_field("홍길동", "휴대폰번호", "010-1234-5678")


👉 원하시면 제가 order (제품 주문) 도 이 구조(utils/order.py)에 맞춰 정리해드릴까요?

나의 말:
네
Sheets_ChatGPT의 말:

좋습니다 👍
그럼 order 관련 기능도 지금 구조(utils/order.py)로 정리해드리겠습니다.
즉, 제품 주문 저장/조회 로직을 한 파일에 모아두고, app.py에서 간단히 불러쓸 수 있도록 하는 방식입니다.

📂 프로젝트 구조 (업데이트)
project/
 ├─ app.py
 ├─ parser.py
 ├─ config.py
 └─ utils/
     ├─ __init__.py
     ├─ api.py
     ├─ sheets.py
     ├─ member.py
     └─ order.py   ✅ 추가

📌 utils/order.py
from utils.api import post_api
from utils.sheets import get_order_sheet, safe_update_cell, header_maps
from parser import process_order_date, parse_order_text_rule


def save_order_api(member_name: str, product: str, price: int, pv: int, method: str, delivery: str = ""):
    """
    제품 주문 API 호출 (Flask API 엔드포인트 통해 저장)
    """
    payload = {
        "회원명": member_name,
        "제품명": product,
        "제품가격": price,
        "PV": pv,
        "결재방법": method,
        "배송처": delivery,
    }
    return post_api("order", payload)


def save_order_sheet(member_name: str, product: str, price: int, pv: int, method: str, delivery: str = "", date: str = None):
    """
    제품 주문 Google Sheet에 직접 저장
    """
    sheet = get_order_sheet()
    headers, idx, _ = header_maps(sheet)

    if not date:
        date = process_order_date("오늘")

    row = [date, member_name, product, price, pv, method, delivery]
    sheet.append_row(row)
    return True


def parse_and_save_order(text: str, use_api: bool = True):
    """
    자연어 주문 문장을 파싱하여 저장
    예: "김지연 노니 2개 카드 주문 저장"
    """
    parsed = parse_order_text_rule(text)
    member_name = parsed.get("회원명", "")
    product = parsed.get("제품명", "제품")
    qty = parsed.get("수량", 1)
    method = parsed.get("결재방법", "카드")
    delivery = parsed.get("배송처", "")
    date = parsed.get("주문일자", process_order_date("오늘"))

    product_name = f"{product} x{qty}"
    price = 10000 * qty   # 예시: 단가 1만 원 가정 (실제는 DB 참고해야 함)
    pv = 10 * qty         # 예시: PV 10 가정

    if use_api:
        return save_order_api(member_name, product_name, price, pv, method, delivery)
    else:
        return save_order_sheet(member_name, product_name, price, pv, method, delivery, date)

📌 app.py 에서 사용 예시
from parser.order import parse_and_save_order

@app.route('/add_order', methods=['POST'])
def add_order():
    try:
        data = request.get_json()
        text = data.get("요청문", "")
        res = parse_and_save_order(text, use_api=True)  # API 사용
        return jsonify({"message": "주문 저장 완료", "result": res})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

✅ 장점

API 저장(save_order_api) 과 시트 직접 저장(save_order_sheet) 을 분리 → 상황 따라 선택 가능

parse_and_save_order 로 자연어 입력 → 저장까지 원샷 처리

app.py 에서는 간단히 parse_and_save_order(text) 만 호출하면 됨

👉 원하시면 제가 후원수당 (commission) 도 같은 구조(utils/commission.py)로 정리해드릴까요?

나의 말:
네
Sheets_ChatGPT의 말:

좋습니다 👍
그럼 후원수당 (commission) 기능도 같은 구조(utils/commission.py)로 정리해드리겠습니다.
즉, 후원수당 저장/조회 로직을 한 곳에 모아두고, app.py에서 간단히 불러서 사용할 수 있게 해드립니다.

📂 프로젝트 구조 (업데이트)
project/
 ├─ app.py
 ├─ parser.py
 ├─ config.py
 └─ utils/
     ├─ __init__.py
     ├─ api.py
     ├─ sheets.py
     ├─ member.py
     ├─ order.py
     └─ commission.py   ✅ 추가

📌 utils/commission.py
from utils.api import post_api
from utils.sheets import get_commission_sheet, header_maps
from parser import process_order_date


def save_commission_api(member_name: str, amount: int, note: str = "", date: str = None):
    """
    후원수당 API 호출 (Flask API 엔드포인트 통해 저장)
    """
    if not date:
        date = process_order_date("오늘")

    payload = {
        "회원명": member_name,
        "수당액": amount,
        "비고": note,
        "지급일자": date,
    }
    return post_api("commission", payload)


def save_commission_sheet(member_name: str, amount: int, note: str = "", date: str = None):
    """
    후원수당 Google Sheet에 직접 저장
    """
    sheet = get_commission_sheet()
    headers, idx, _ = header_maps(sheet)

    if not date:
        date = process_order_date("오늘")

    row = [date, member_name, amount, note]
    sheet.append_row(row)
    return True


def find_commission_by_member(member_name: str):
    """
    특정 회원의 후원수당 내역 조회 (시트 기준)
    """
    sheet = get_commission_sheet()
    records = sheet.get_all_records()
    return [row for row in records if (row.get("회원명") or "").strip() == member_name.strip()]

📌 config.py (API_URLS 확장)
API_URLS = {
    "counseling": urljoin(API_BASE, "/add_counseling"),
    "member_update": urljoin(API_BASE, "/updateMember"),
    "order": urljoin(API_BASE, "/save_order"),
    "commission": urljoin(API_BASE, "/save_commission"),  # ✅ 추가
}

📌 app.py 에서 사용 예시
from parser.commission import save_commission_api, find_commission_by_member

@app.route('/add_commission', methods=['POST'])
def add_commission():
    try:
        data = request.get_json()
        member = data.get("회원명")
        amount = int(data.get("수당액", 0))
        note = data.get("비고", "")
        save_commission_api(member, amount, note)
        return jsonify({"message": f"{member}님의 후원수당 {amount}원 저장 완료"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/find_commission', methods=['GET'])
def find_commission():
    try:
        member = request.args.get("회원명")
        records = find_commission_by_member(member)
        return jsonify({"records": records})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

✅ 정리

utils/commission.py

save_commission_api → API 호출 방식

save_commission_sheet → Google Sheet 직접 저장

find_commission_by_member → 특정 회원의 후원수당 조회

config.py 의 API_URLS 에 "commission" 추가

app.py 에서 save_commission_api 와 find_commission_by_member 불러서 라우트 구현

👉 이렇게 되면 회원 / 주문 / 후원수당 / 일지가 전부 분리 관리되면서,
app.py 에서는 불러쓰기만 하면 되는 구조가 완성됩니다. 🚀

원하시면 제가 README.md 형식으로 전체 모듈별 역할 요약 문서도 작성해드릴까요?

나의 말:
네
Sheets_ChatGPT의 말:

좋습니다 👍
이제 전체 프로젝트 구조와 각 모듈별 역할을 정리한 README.md 초안을 만들어드릴게요.

📌 README.md (초안)
# 📑 회원 관리/주문/후원수당/일지 시스템

이 프로젝트는 **Google Sheets** 와 **Flask API** 를 연동하여  
- 회원 정보 관리  
- 제품 주문  
- 후원수당 기록  
- 상담/개인/활동 일지 저장  

등을 처리할 수 있는 통합 관리 시스템입니다.

---

## 📂 프로젝트 구조



project/
├─ app.py # Flask 엔드포인트 (API 라우팅)
├─ parser.py # 자연어 파서 및 일지 저장 유틸
├─ config.py # API 주소, 헤더 설정
└─ utils/ # 유틸리티 모듈 모음
├─ init.py
├─ api.py # post_api() - 공통 API 요청
├─ sheets.py # Google Sheets 관련 함수
├─ member.py # 회원 관련 API/시트 업데이트
├─ order.py # 주문 관련 API/시트 업데이트
└─ commission.py # 후원수당 관련 API/시트 업데이트


---

## ⚙️ 주요 모듈 설명

### 1. `config.py`
- 환경변수(`API_BASE`)를 읽어 API 주소 관리
- `API_URLS` dict 로 모든 엔드포인트 통합 관리
```python
API_URLS = {
    "counseling": urljoin(API_BASE, "/add_counseling"),
    "member_update": urljoin(API_BASE, "/updateMember"),
    "order": urljoin(API_BASE, "/save_order"),
    "commission": urljoin(API_BASE, "/save_commission"),
}

2. utils/api.py

공통 API 요청 함수

from config import API_URLS, HEADERS
def post_api(name: str, payload: dict):
    """사전 정의된 API 엔드포인트로 POST 요청"""

3. utils/sheets.py

Google Sheets 접근 및 업데이트 관련 함수 모음

get_ws, safe_update_cell, get_member_sheet 등 제공

4. utils/member.py

회원 정보 업데이트

API 방식(update_member_field) 과 시트 직접 수정(update_member_field_strict) 지원

5. utils/order.py

주문 저장/조회 로직

자연어 파싱 후 API 저장 or 시트 직접 저장

parse_and_save_order("김지연 노니 2개 카드 주문 저장")

6. utils/commission.py

후원수당 저장/조회 로직

API 저장(save_commission_api) 과 시트 저장(save_commission_sheet) 제공

특정 회원 후원수당 조회 가능

7. parser.py

상담/개인/활동 일지 저장 유틸

자연어 파싱(parse_request_line)

save_to_sheet 함수로 시트에 저장

8. app.py

Flask API 엔드포인트 정의

주요 라우트:

/add_counseling → 상담/개인/활동 일지 저장

/add_order → 제품 주문 저장

/add_commission → 후원수당 저장

/find_commission → 후원수당 조회

🚀 실행 방법

환경변수 설정 (.env)

API_BASE=https://your-api-server.com
GOOGLE_SHEET_TITLE=회원관리시트
GOOGLE_CREDENTIALS_JSON={...}   # 서비스 계정 키 JSON


서버 실행

flask run --host=0.0.0.0 --port=5000


API 호출 예시

curl -X POST http://localhost:5000/add_counseling \
     -H "Content-Type: application/json" \
     -d '{"요청문":"홍길동 상담일지 저장 오늘 미팅 완료"}'

📌 요약

app.py → Flask API 라우팅

parser.py → 일지 파서/저장

utils/ → 기능별 모듈화 (회원, 주문, 후원수당, 시트, API)

config.py → API 주소/헤더 일원화 관리

✅ 이 구조를 따르면 모듈별 역할이 명확해지고,
새로운 기능을 추가할 때도 utils/새기능.py 를 만들고 API_URLS 만 확장하면 됩니다.


---

👉 원하시면 이 README 에 **자연어 입력 예시 모음** (예: `"김지연 노니 2개 카드 주문 저장"`) 섹션도 추가해드릴까요?

나의 말:
이렇게 관리하면 너무 좋은데 나는 코드를 잘 모르는 초보자라서 지금은 코드를 만드는 작업을 하는 중이라서 한가지를 만들어서 추가하려 하면 라우트와 연관되는 모든 파서나 함수의 연결관계를 잘 모르기 때문에 gpt에게 어는 코드를 올려 주고 어디를 수정해야 하는지 물어 볼때 일일히 분야별 모든 코드를 복사해서 붙여 넣어서 물어 봐야 한다는 점이 너무 힘들어 이 부분을 어떻게 해결할 수 있을까? 
Sheets_ChatGPT의 말:

좋은 고민이에요 👍
지금 말씀하신 어려움은 코드 구조가 모듈화돼 있지만, 초보자 입장에서는 "이 기능 추가하려면 어디를 손대야 하지?" 라는 연결관계를 이해하기 어렵다는 점이에요.

이 문제는 많은 초보 개발자들이 겪는 부분인데, 해결할 수 있는 몇 가지 방법을 알려드릴게요.

🔑 해결 전략
1. 의존성 맵(Dependency Map) 만들기

각 라우트(/add_counseling, /add_order, /add_commission 등) 별로 어떤 함수/모듈을 호출하는지 한 장짜리 그림이나 테이블로 만들어두면 좋아요.
예시:

라우트(API)	주요 함수	관련 모듈
/add_counseling	save_to_sheet()	parser.py, utils/sheets.py
/add_order	parse_and_save_order()	utils/order.py, parser.py
/add_commission	save_commission_api()	utils/commission.py

👉 이렇게 문서화해두면, 새 기능을 추가할 때
“어? 이건 주문 관련 기능이니까 utils/order.py에서 함수 만들고, app.py에 라우트 하나 추가하면 되겠네”
라는 흐름을 바로 알 수 있어요.

2. GPT에게 파일 단위로 물어보기

지금처럼 전체 코드를 다 복사할 필요는 없어요.

“나는 /add_order 라우트를 추가하고 싶어. 지금 내 app.py는 이렇게 생겼어.” 라고 하면서 app.py 코드만 올리면 돼요.

GPT가 자동으로 “이건 utils/order.py도 수정해야 돼요” 라고 알려줄 수 있어요.

👉 즉, 현재 작업 중인 파일만 붙여넣기 → GPT가 나머지 필요한 파일까지 알려주는 방식으로 가는 거예요.

3. 파일별 주석에 “수정 포인트” 적어두기

예: app.py 맨 위에 이런 식으로 적어두면 나중에 훨씬 편해집니다.

# 📌 수정 가이드
# - 새로운 API 라우트 추가 → 여기(app.py)에 @app.route 추가
# - 로직/저장 처리 → utils/ 관련 모듈에 함수 추가
# - 시트 접근 → utils/sheets.py 참고
# - API 주소 → config.py (API_URLS dict) 수정


👉 그러면 나중에 열어볼 때 “내가 뭘 고쳐야 하지?” 헷갈리지 않아요.

4. README.md 확장 (개발 가이드 버전)

앞에서 만든 README에다가 “새 기능 추가 방법” 섹션을 넣으면 돼요.
예:

🛠 새 API 추가하는 법

config.py → API_URLS 에 새 엔드포인트 등록

utils/새모듈.py → 기능 함수 작성

app.py → @app.route('/new_feature') 추가 후, utils/새모듈.py 함수 호출

👉 이렇게 단계별로 적어두면, 복잡하게 GPT한테 물어보지 않고도 자기 혼자서 순서대로 추가 가능해집니다.

5. GPT와 대화할 때 팁

"지금 app.py는 이렇게 생겼는데, XXX 기능 추가하려면 어디를 수정해야 해?"

"내가 utils/order.py에 함수 만들었는데, app.py 라우트랑 잘 연결됐는지 확인해줘."

👉 즉, “관련 파일만” 보여주고 물어보면 됩니다. GPT가 “추가로 config.py 도 수정해야 해요” 라고 알려줄 수 있어요.

✅ 요약

의존성 맵 (라우트 ↔ 함수 ↔ 모듈 관계표) 만들어두기

GPT에 물어볼 땐 관련 파일만 올리기 (전체 복붙 필요 없음)

각 파일에 수정 가이드 주석 적어두기

README.md 에 “새 기능 추가 방법” 단계별 가이드 추가

👉 원하시면 제가 지금 만든 README에 “🛠 새 기능 추가 가이드” 섹션을 추가해서, 초보자용 단계별 설명으로 확장해드릴까요?

나의 말:
네
Sheets_ChatGPT의 말:

좋습니다 👍
그럼 아까 만든 README.md 에다가 초보자도 쉽게 따라할 수 있는
🛠 새 기능 추가 가이드 섹션을 추가해서 확장해드리겠습니다.

📌 업데이트된 README.md
# 📑 회원 관리/주문/후원수당/일지 시스템

이 프로젝트는 **Google Sheets** 와 **Flask API** 를 연동하여  
- 회원 정보 관리  
- 제품 주문  
- 후원수당 기록  
- 상담/개인/활동 일지 저장  

등을 처리할 수 있는 통합 관리 시스템입니다.

---

## 📂 프로젝트 구조



project/
├─ app.py # Flask 엔드포인트 (API 라우팅)
├─ parser.py # 자연어 파서 및 일지 저장 유틸
├─ config.py # API 주소, 헤더 설정
└─ utils/ # 유틸리티 모듈 모음
├─ init.py
├─ api.py # post_api() - 공통 API 요청
├─ sheets.py # Google Sheets 관련 함수
├─ member.py # 회원 관련 API/시트 업데이트
├─ order.py # 주문 관련 API/시트 업데이트
└─ commission.py # 후원수당 관련 API/시트 업데이트


---

## ⚙️ 주요 모듈 설명
(📌 기존 설명 생략, 위 내용 동일)

---

## 🚀 실행 방법
(📌 기존 설명 생략, 위 내용 동일)

---

## 🛠 새 기능 추가 가이드

새로운 기능(예: **포인트 적립**, **출석 체크**)을 추가하고 싶을 때는  
아래 단계만 지키면 됩니다.

---

### 1단계. `config.py` 수정
API 주소가 필요하다면 `API_URLS` 에 추가합니다.
```python
API_URLS = {
    "counseling": urljoin(API_BASE, "/add_counseling"),
    "member_update": urljoin(API_BASE, "/updateMember"),
    "order": urljoin(API_BASE, "/save_order"),
    "commission": urljoin(API_BASE, "/save_commission"),
    "point": urljoin(API_BASE, "/save_point"),  # ✅ 새 기능 추가
}

2단계. utils/새모듈.py 생성

새로운 기능 전용 모듈을 만듭니다.
예: utils/point.py

from utils.api import post_api
from utils.sheets import get_ws
from parser import process_order_date

def save_point_api(member_name: str, amount: int, note: str = ""):
    return post_api("point", {
        "회원명": member_name,
        "포인트": amount,
        "비고": note,
        "일자": process_order_date("오늘")
    })

def save_point_sheet(member_name: str, amount: int, note: str = ""):
    sheet = get_ws("포인트")
    sheet.append_row([process_order_date("오늘"), member_name, amount, note])
    return True

3단계. app.py 라우트 추가

Flask 라우트에서 방금 만든 함수를 불러옵니다.

from utils.point import save_point_api

@app.route('/add_point', methods=['POST'])
def add_point():
    try:
        data = request.get_json()
        member = data.get("회원명")
        amount = int(data.get("포인트", 0))
        note = data.get("비고", "")
        save_point_api(member, amount, note)
        return jsonify({"message": f"{member}님 {amount}포인트 적립 완료"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

4단계. 테스트

터미널에서:

curl -X POST http://localhost:5000/add_point \
     -H "Content-Type: application/json" \
     -d '{"회원명":"홍길동","포인트":100,"비고":"출석"}'

✅ 핵심 요약

config.py → API_URLS 에 새 API 추가

utils/새모듈.py → 기능 함수 작성 (API 방식 + 시트 방식)

app.py → Flask 라우트 추가 후 utils 함수 호출

테스트

👉 이 4단계만 지키면, 새로운 기능을 추가할 때도 다른 코드 복사 없이 안전하게 확장할 수 있습니다.


---

✅ 이제 초보자라도 "새 기능 추가" 할 때  
👉 `config.py` → `utils/새모듈.py` → `app.py` → 테스트  
**이 순서만 기억하면 됩니다.**

---

원하시면 제가 이 README 에 **자연어 입력 예시 모음 (상담일지, 주문, 후원수당)** 섹션도 추가해드릴까요?

나의 말:
config.py 는 어느 위치에 만드나? 루트?
Sheets_ChatGPT의 말:

좋은 질문이에요 👍

config.py 는 프로젝트의 전역 설정을 담는 파일이기 때문에,
보통은 루트 디렉토리 (project/) 에 두는 게 가장 깔끔합니다.

📂 위치 예시
project/
 ├─ app.py            # Flask 엔드포인트
 ├─ parser.py         # 일지 파서
 ├─ config.py         # ✅ 전역 설정 (루트에 위치)
 └─ utils/            # 유틸리티 모듈 모음
     ├─ api.py
     ├─ sheets.py
     ├─ member.py
     ├─ order.py
     └─ commission.py

📌 왜 루트에 두나?

모든 모듈이 공통으로 import 할 수 있도록

utils/api.py, app.py, parser.py 모두 from config import API_URLS 처럼 쉽게 가져올 수 있어요.

만약 utils/ 안에 두면, from utils.config import ... 으로 불러야 해서 오히려 길어져요.

환경변수 / 공통 상수 관리 위치는 루트가 직관적

.env 파일도 보통 루트에 놓으니까, 그와 맞춰서 관리하면 편리합니다.

✅ 정리:

config.py 는 루트 디렉토리 (app.py, parser.py 와 같은 레벨) 에 두는 게 맞습니다.

원하시면 제가 config.py 안에 환경변수 기본값 + .env 자동 로드 기능까지 넣어서, 초보자도 환경설정 실수 안 하게 만들어드릴까요?

나의 말:
네
Sheets_ChatGPT의 말:

좋습니다 👍
그럼 초보자도 .env 파일만 만들어두면 자동으로 환경설정이 로드되도록,
config.py 를 조금 더 똑똑하게 만들어드릴게요 🚀

📌 개선된 config.py
# config.py
import os
from urllib.parse import urljoin

# --------------------------------------------------
# 1. .env 자동 로드 (로컬 환경에서만)
# --------------------------------------------------
if os.getenv("RENDER") is None:  # 예: Render 같은 서버환경이면 건너뜀
    try:
        from dotenv import load_dotenv
        if os.path.exists(".env"):
            load_dotenv(".env")
    except Exception:
        pass

# --------------------------------------------------
# 2. 환경변수 기본값 설정
# --------------------------------------------------
API_BASE = os.getenv("API_BASE", "http://localhost:5000")
GOOGLE_SHEET_TITLE = os.getenv("GOOGLE_SHEET_TITLE", "회원관리시트")

# 구글 인증 키 (JSON 문자열 or 파일 경로)
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", None)
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")

# --------------------------------------------------
# 3. 공통 요청 헤더
# --------------------------------------------------
HEADERS = {"Content-Type": "application/json"}

# --------------------------------------------------
# 4. API 엔드포인트 일괄 관리
# --------------------------------------------------
API_URLS = {
    "counseling": urljoin(API_BASE, "/add_counseling"),
    "member_update": urljoin(API_BASE, "/updateMember"),
    "order": urljoin(API_BASE, "/save_order"),
    "commission": urljoin(API_BASE, "/save_commission"),
    # 새 기능이 필요하면 여기만 추가
    # "point": urljoin(API_BASE, "/save_point"),
}

📂 .env 예시 (루트 디렉토리에 생성)
API_BASE=http://localhost:5000
GOOGLE_SHEET_TITLE=회원관리시트
GOOGLE_CREDENTIALS_PATH=credentials.json


※ Render, Railway 같은 클라우드 서버 환경에서는
👉 .env 대신 환경변수 대시보드에 설정하면 자동으로 적용됩니다.

✅ 장점

.env 파일 자동 로드 → 초보자는 .env 에만 값 넣으면 됨

환경변수가 없으면 안전하게 기본값(localhost:5000, credentials.json) 사용

API_URLS 에서 모든 엔드포인트 한눈에 관리

👉 이제 초보자 입장에서는

새 API 추가 → config.py 의 API_URLS 딕셔너리에 한 줄 추가

환경변수 변경 → .env 파일만 수정

하면 끝납니다 🚀

혹시 제가 이 config.py 와 .env 관리 방식을 포함해서,
README.md 에 “환경설정 가이드” 섹션을 추가해드릴까요?

나의 말:
그럼 여기에서 config.py로 옮겨도 되는 부분 알려 주고 app에서는 삭제할 부분을 알려 줘
Sheets_ChatGPT의 말:

네, 정확히 정리해드리겠습니다 👍

📌 현재 app.py 안에 있는 config.py로 옮겨야 할 부분

보통 환경설정값(API_BASE, API_URL, HEADERS)은 config.py로 이동하는 게 맞습니다.

🔴 기존 app.py (삭제 대상)
API_BASE = os.getenv("API_BASE")
API_URL = os.getenv("COUNSELING_API_URL")
HEADERS = {"Content-Type": "application/json"}

📌 config.py 에 옮겨야 할 부분

👉 config.py 안에 이미 기본 구조를 만들었으니, 위의 내용은 다음처럼 들어갑니다.

# config.py

import os
from urllib.parse import urljoin

# --------------------------------------------------
# 환경변수 로드 (.env 지원)
# --------------------------------------------------
if os.getenv("RENDER") is None:
    try:
        from dotenv import load_dotenv
        if os.path.exists(".env"):
            load_dotenv(".env")
    except Exception:
        pass

# --------------------------------------------------
# 환경변수 기본값
# --------------------------------------------------
API_BASE = os.getenv("API_BASE", "http://localhost:5000")
GOOGLE_SHEET_TITLE = os.getenv("GOOGLE_SHEET_TITLE", "회원관리시트")

GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", None)
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")

# --------------------------------------------------
# 공통 헤더
# --------------------------------------------------
HEADERS = {"Content-Type": "application/json"}

# --------------------------------------------------
# API 엔드포인트
# --------------------------------------------------
API_URLS = {
    "counseling": urljoin(API_BASE, "/add_counseling"),
    "member_update": urljoin(API_BASE, "/updateMember"),
    "order": urljoin(API_BASE, "/save_order"),
    "commission": urljoin(API_BASE, "/save_commission"),
}

📌 app.py 수정 후

👉 이제 app.py 에서는 더 이상 환경변수 직접 불러올 필요 없음.
즉, 아래처럼 삭제하고 대신 config.py 또는 utils/api.py 에서 불러옵니다.

🟢 수정된 app.py
import re, traceback
from flask import Flask, request, jsonify

from parser import save_to_sheet
from utils.api import post_api  # post_api는 내부에서 config.py를 불러옴

try:
    app
except NameError:
    app = Flask(__name__)

✅ 정리

app.py 에 있던

API_BASE = os.getenv("API_BASE")
API_URL = os.getenv("COUNSELING_API_URL")
HEADERS = {"Content-Type": "application/json"}


→ 전부 삭제

config.py 에 환경설정만 남기고,

app.py 는 비즈니스 로직(라우트)만 관리

👉 이렇게 하면 app.py 는 깔끔하게 라우팅 전용 파일이 되고,
환경변수 관련된 건 전부 config.py 한 곳에서만 관리하면 됩니다. 🚀

혹시 제가 app.py 전체에서 config 관련 부분 삭제 후 최종 정리본을 직접 만들어드릴까요?

나의 말:
from flask import Flask, request, jsonify, Response
import base64
import requests


import os
import io
import json
import re

from openai import OpenAI
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytz
import uuid
from gspread.utils import rowcol_to_a1
from collections import Counter

import time
from PIL import Image
import mimetypes
import traceback
from urllib.parse import urljoin




from parser import save_to_sheet




API_BASE = os.getenv("API_BASE")
API_URL = os.getenv("COUNSELING_API_URL")
HEADERS = {"Content-Type": "application/json"}





# ✅ 환경 변수 로드
if os.getenv("RENDER") is None:  # 로컬에서 실행 중일 때만
    from dotenv import load_dotenv
    dotenv_path = os.path.abspath('.env')
    if not os.path.exists(dotenv_path):
        raise FileNotFoundError(f".env 파일이 존재하지 않습니다: {dotenv_path}")
    load_dotenv(dotenv_path)

# 환경변수에서 불러오기
prompt_id = os.getenv("PROMPT_ID")
prompt_version = os.getenv("PROMPT_VERSION")

# ✅ OpenAI 클라이언트 초기화
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
GOOGLE_SHEET_TITLE = os.getenv("GOOGLE_SHEET_TITLE")

# OpenAI API 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL")

# ✅ memberslist API 엔드포인트
MEMBERSLIST_API_URL = os.getenv("MEMBERSLIST_API_URL")


# ✅ Google Sheets 클라이언트 생성 함수
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")  # Render에서 환경변수로 넣은 값
    if creds_json:  # Render 환경
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:  # 로컬 개발용 (credentials.json 파일 사용)
        creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)

    return gspread.authorize(creds)



# ✅ 시트 연결
client = get_gspread_client()
SHEET_KEY = os.getenv("GOOGLE_SHEET_KEY")
if not SHEET_KEY:
    raise EnvironmentError("환경변수 GOOGLE_SHEET_KEY가 설정되지 않았습니다.")
spreadsheet = client.open_by_key(SHEET_KEY)
print(f"시트에 연결되었습니다. (ID={SHEET_KEY})")



# ✅ 필수 환경 변수 확인
if not GOOGLE_SHEET_TITLE:
    raise EnvironmentError("환경변수 GOOGLE_SHEET_TITLE이 설정되지 않았습니다.")


# ✅ 날짜 처리
def process_order_date(text):
    if not text:
        return datetime.now().strftime("%Y-%m-%d")
    return text.strip()

# ✅ 한국 시간
def now_kst():
    return datetime.now(pytz.timezone("Asia/Seoul"))

# ✅ Flask 초기화
app = Flask(__name__)






def get_worksheet(sheet_name):
    try:
        worksheets = spreadsheet.worksheets()
        sheet_names = [ws.title for ws in worksheets]
        print("✅ 현재 시트 목록:", sheet_names)

        return spreadsheet.worksheet(sheet_name)
    except Exception as e:
        raise RuntimeError(f"시트 '{sheet_name}'을 열 수 없습니다. "
                           f"(현재 시트 목록: {sheet_names}) 에러: {e}")




















def some_function():
    print("작업 시작")
    time.sleep(1)
    print("작업 완료")


# ✅ 확인용 출력 (선택)
print("✅ GOOGLE_SHEET_TITLE:", os.getenv("GOOGLE_SHEET_TITLE"))
print("✅ GOOGLE_SHEET_KEY 존재 여부:", "Yes" if os.getenv("GOOGLE_SHEET_KEY") else "No")






# 자연어 명령 키워드 매핑
UPDATE_KEYS = {
    "회원": ["회원수정", "회원내용수정", "회원내용을 수정", "회원변경", "회원내용변경", "회원내용을 고쳐", "수정", "변경", "고쳐"],
    "주문": ["주문수정", "주문내용수정", "주문내용을 수정", "주문변경", "주문내용변경", "주문내용을 고쳐"],
    "후원수당": ["후원수당수정", "후원수당내용수정", "후원수당내용을 수정", "후원수당변경", "후원수당내용변경", "후원수당내용을 고쳐"]
}

# ✅ 주문 항목 헤더
ORDER_HEADERS = [
    "주문일자", "회원명", "회원번호", "휴대폰번호", "제품명",
    "제품가격", "PV", "결재방법", "소비자_고객명", "소비자_휴대폰번호",
    "배송처", "수령확인"
]




def parse_request(text):
    result = {"회원명": "", "수정목록": []}

    # 회원명 추출
    name_match = re.search(r"^([가-힣]{2,3})", text)
    if not name_match:
        name_match = re.search(r"([가-힣]{2,3})\s*회원[의은는이가]?", text)
    if name_match:
        result["회원명"] = name_match.group(1)

    # 전체 필드
    필드패턴 = r"(회원명|휴대폰번호|회원번호|특수번호|가입일자|생년월일|통신사|친밀도|근무처|계보도|소개한분|주소|메모|코드|카드사|카드주인|카드번호|유효기간|비번|카드생년월일|분류|회원단계|연령/성별|직업|가족관계|니즈|애용제품|콘텐츠|습관챌린지|비즈니스시스템|GLC프로젝트|리더님)"
    수정_패턴 = re.findall(rf"{필드패턴}\s*(?:은|는|을|를)?\s*([\w가-힣\d\-\.:/@]+)", text)

    for 필드, 값 in 수정_패턴:
        result["수정목록"].append({"필드": 필드, "값": 값})

    return result





@app.route("/")
def home():
    return "Flask 서버가 실행 중입니다."

def get_db_sheet():
    return get_worksheet("DB")

def get_member_sheet():
    return get_worksheet("DB")

def get_product_order_sheet():
    return get_worksheet("제품주문")

def get_add_order_sheet():
    return get_worksheet("제품주문")

def get_save_order_sheet():
    return get_worksheet("제품주문")

def get_delete_order_request_sheet():
    return get_worksheet("제품주문")

def get_delete_order_confirm_sheet():
    return get_worksheet("제품주문")

def get_ss_sheet():
    return get_worksheet("후원수당")

def get_counseling_sheet():
    return get_worksheet("상담일지")

def get_mymemo_sheet():
    return get_worksheet("개인일지")

def get_search_memo_by_tags_sheet():
    return get_worksheet("개인밀지")

def get_dailyrecord_sheet():
    return get_worksheet("활동일지")

def get_product_order_sheet():
    return get_worksheet("제품주문")    

def get_image_sheet():
    return get_worksheet("사진저장")

def get_backup_sheet():
    return get_worksheet("백업")






# ✅ 필드 키워드 → 시트의 실제 컬럼명 매핑
field_map = {
    "휴대폰번호": "휴대폰번호",
    "핸드폰": "휴대폰번호",
    "계보도": "계보도",
    "주소": "주소",
    "회원번호": "회원번호",
    "이름": "회원명",
    "생일": "생년월일",
    "생년월일": "생년월일",
    "특수번호": "특수번호",
    "직업": "근무처",
    "직장": "근무처",
    # 필요한 항목 계속 추가 가능
}



# 🔽 파일 하단에 삽입 예시
def save_member(name):
    print(f"[✅] '{name}' 회원 등록")

def update_member_fields(name, fields):
    print(f"[✏️] '{name}' 필드 업데이트: {fields}")
Sheets_ChatGPT의 말:

좋습니다 👍 올려주신 app.py 내용을 보니까 환경설정 코드(config 관련) 와 Flask 라우트/비즈니스 로직 이 다 섞여 있네요.

제가 config.py로 옮겨야 하는 부분과, app.py에서 삭제할 부분을 정리해드릴게요.

📌 1. config.py 로 옮겨야 하는 부분

환경 변수 / API 설정 / Google Sheet 기본 설정 은 전부 config.py 로 이동하는 게 맞습니다.

👉 옮길 코드:

import os
from urllib.parse import urljoin

# ✅ 환경 변수 로드 (.env 자동 처리)
if os.getenv("RENDER") is None:  # 로컬에서 실행 중일 때만
    from dotenv import load_dotenv
    dotenv_path = os.path.abspath('.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)

# --------------------------------------------------
# 필수 환경 변수
# --------------------------------------------------
API_BASE = os.getenv("API_BASE", "http://localhost:5000")
GOOGLE_SHEET_TITLE = os.getenv("GOOGLE_SHEET_TITLE", "회원관리시트")
SHEET_KEY = os.getenv("GOOGLE_SHEET_KEY")

# --------------------------------------------------
# OpenAI 관련
# --------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL")
PROMPT_ID = os.getenv("PROMPT_ID")
PROMPT_VERSION = os.getenv("PROMPT_VERSION")

# --------------------------------------------------
# Memberslist API
# --------------------------------------------------
MEMBERSLIST_API_URL = os.getenv("MEMBERSLIST_API_URL")

# --------------------------------------------------
# 공통 헤더
# --------------------------------------------------
HEADERS = {"Content-Type": "application/json"}

# --------------------------------------------------
# API 엔드포인트 (Flask API 쪽)
# --------------------------------------------------
API_URLS = {
    "counseling": urljoin(API_BASE, "/add_counseling"),
    "member_update": urljoin(API_BASE, "/updateMember"),
    "order": urljoin(API_BASE, "/save_order"),
    "commission": urljoin(API_BASE, "/save_commission"),
}

📌 2. app.py 에서 삭제할 부분

아래 내용은 환경설정 관련이므로 전부 삭제 가능하고, 필요하면 config.py에서 import 하세요.

API_BASE = os.getenv("API_BASE")
API_URL = os.getenv("COUNSELING_API_URL")
HEADERS = {"Content-Type": "application/json"}

# ✅ 환경 변수 로드
if os.getenv("RENDER") is None:  # 로컬에서 실행 중일 때만
    from dotenv import load_dotenv
    dotenv_path = os.path.abspath('.env')
    if not os.path.exists(dotenv_path):
        raise FileNotFoundError(f".env 파일이 존재하지 않습니다: {dotenv_path}")
    load_dotenv(dotenv_path)

# 환경변수에서 불러오기
prompt_id = os.getenv("PROMPT_ID")
prompt_version = os.getenv("PROMPT_VERSION")

# ✅ OpenAI 클라이언트 초기화
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
GOOGLE_SHEET_TITLE = os.getenv("GOOGLE_SHEET_TITLE")

# OpenAI API 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL")

# ✅ memberslist API 엔드포인트
MEMBERSLIST_API_URL = os.getenv("MEMBERSLIST_API_URL")

SHEET_KEY = os.getenv("GOOGLE_SHEET_KEY")
if not SHEET_KEY:
    raise EnvironmentError("환경변수 GOOGLE_SHEET_KEY가 설정되지 않았습니다.")

# ✅ 필수 환경 변수 확인
if not GOOGLE_SHEET_TITLE:
    raise EnvironmentError("환경변수 GOOGLE_SHEET_TITLE이 설정되지 않았습니다.")

📌 3. app.py 에 남겨야 할 부분

Flask 앱 초기화

라우트(/, /add_counseling, /add_order, …)

parse_request, save_to_sheet 등 비즈니스 로직 함수

즉, app.py는 “서버 라우트 전용” 으로 가볍게 두고,
환경변수/설정은 전부 config.py에서 import 해서 씁니다.

예시:

from flask import Flask, request, jsonify
from config import API_URLS, HEADERS, GOOGLE_SHEET_TITLE, SHEET_KEY
from parser import save_to_sheet

app = Flask(__name__)

✅ 정리

config.py : 환경 변수, API 주소, Google Sheet 키 같은 설정값

app.py : Flask 서버 라우트와 비즈니스 로직

👉 원하시면 제가 지금 올려주신 app.py를 환경설정 부분 삭제 후 깔끔하게 정리한 최종본으로 다시 만들어드릴까요?

나의 말:
네
Sheets_ChatGPT의 말:

좋습니다 👍
그럼 지금 올려주신 app.py 에서 환경설정 관련 부분을 모두 config.py로 이동하고,
app.py 는 Flask 라우트와 비즈니스 로직만 남긴 최종 정리본을 만들어드리겠습니다.

🟢 최종 정리된 app.py
from flask import Flask, request, jsonify, Response
import base64
import requests
import os
import io
import json
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, timezone
import pandas as pd
import pytz
import uuid
from gspread.utils import rowcol_to_a1
from collections import Counter
import time
from PIL import Image
import mimetypes
import traceback

# ✅ 우리 프로젝트 모듈
from parser import save_to_sheet
from config import API_URLS, HEADERS, GOOGLE_SHEET_TITLE, SHEET_KEY, OPENAI_API_KEY, MEMBERSLIST_API_URL

# ✅ Flask 초기화
app = Flask(__name__)


# ✅ Google Sheets 클라이언트 생성 함수
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")  # Render 환경 (JSON 문자열)
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:  # 로컬 개발용 (credentials.json 파일 사용)
        creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)

    return gspread.authorize(creds)


# ✅ 시트 연결
client = get_gspread_client()
spreadsheet = client.open_by_key(SHEET_KEY)
print(f"시트에 연결되었습니다. (ID={SHEET_KEY})")


# ✅ 날짜 처리
def process_order_date(text):
    if not text:
        return datetime.now().strftime("%Y-%m-%d")
    return text.strip()


# ✅ 한국 시간
def now_kst():
    return datetime.now(pytz.timezone("Asia/Seoul"))


def get_worksheet(sheet_name):
    try:
        worksheets = spreadsheet.worksheets()
        sheet_names = [ws.title for ws in worksheets]
        print("✅ 현재 시트 목록:", sheet_names)

        return spreadsheet.worksheet(sheet_name)
    except Exception as e:
        raise RuntimeError(f"시트 '{sheet_name}'을 열 수 없습니다. "
                           f"(현재 시트 목록: {sheet_names}) 에러: {e}")


# ✅ 홈 라우트
@app.route("/")
def home():
    return "Flask 서버가 실행 중입니다."


# ✅ DB/일지 시트 접근 함수
def get_db_sheet():
    return get_worksheet("DB")

def get_member_sheet():
    return get_worksheet("DB")

def get_product_order_sheet():
    return get_worksheet("제품주문")

def get_ss_sheet():
    return get_worksheet("후원수당")

def get_counseling_sheet():
    return get_worksheet("상담일지")

def get_mymemo_sheet():
    return get_worksheet("개인일지")

def get_dailyrecord_sheet():
    return get_worksheet("활동일지")

def get_image_sheet():
    return get_worksheet("사진저장")

def get_backup_sheet():
    return get_worksheet("백업")


# ✅ 자연어 명령 키워드 매핑
UPDATE_KEYS = {
    "회원": ["회원수정", "회원내용수정", "회원내용을 수정", "회원변경", "회원내용변경", "회원내용을 고쳐", "수정", "변경", "고쳐"],
    "주문": ["주문수정", "주문내용수정", "주문내용을 수정", "주문변경", "주문내용변경", "주문내용을 고쳐"],
    "후원수당": ["후원수당수정", "후원수당내용수정", "후원수당내용을 수정", "후원수당변경", "후원수당내용변경", "후원수당내용을 고쳐"]
}

# ✅ 주문 항목 헤더
ORDER_HEADERS = [
    "주문일자", "회원명", "회원번호", "휴대폰번호", "제품명",
    "제품가격", "PV", "결재방법", "소비자_고객명", "소비자_휴대폰번호",
    "배송처", "수령확인"
]


# ✅ 자연어 요청 파싱
def parse_request(text):
    result = {"회원명": "", "수정목록": []}

    # 회원명 추출
    name_match = re.search(r"^([가-힣]{2,3})", text)
    if not name_match:
        name_match = re.search(r"([가-힣]{2,3})\s*회원[의은는이가]?", text)
    if name_match:
        result["회원명"] = name_match.group(1)

    # 전체 필드
    필드패턴 = r"(회원명|휴대폰번호|회원번호|특수번호|가입일자|생년월일|통신사|친밀도|근무처|계보도|소개한분|주소|메모|코드|카드사|카드주인|카드번호|유효기간|비번|카드생년월일|분류|회원단계|연령/성별|직업|가족관계|니즈|애용제품|콘텐츠|습관챌린지|비즈니스시스템|GLC프로젝트|리더님)"
    수정_패턴 = re.findall(rf"{필드패턴}\s*(?:은|는|을|를)?\s*([\w가-힣\d\-\.:/@]+)", text)

    for 필드, 값 in 수정_패턴:
        result["수정목록"].append({"필드": 필드, "값": 값})

    return result


# ✅ 필드 키워드 → 시트 컬럼명 매핑
field_map = {
    "휴대폰번호": "휴대폰번호",
    "핸드폰": "휴대폰번호",
    "계보도": "계보도",
    "주소": "주소",
    "회원번호": "회원번호",
    "이름": "회원명",
    "생일": "생년월일",
    "생년월일": "생년월일",
    "특수번호": "특수번호",
    "직업": "근무처",
    "직장": "근무처",
}


# ✅ 회원 관련 더미 함수 (실제 구현 필요)
def save_member(name):
    print(f"[✅] '{name}' 회원 등록")

def update_member_fields(name, fields):
    print(f"[✏️] '{name}' 필드 업데이트: {fields}")

📌 정리

app.py → Flask 서버, 라우트, 시트 접근 함수, 파싱 로직 만 유지

config.py → 환경변수, API 주소, 키 값, 헤더 등 설정 전용

👉 이제 app.py 를 실행하면 환경설정은 전부 config.py에서 가져오게 됩니다.
원하시면 제가 app.py 안에 예시 라우트 (예: /add_counseling) 도 추가해서 완전 동작 확인 가능한 버전으로 만들어드릴까요?

나의 말:
API_BASE = os.getenv("API_BASE")
API_URL = os.getenv("COUNSELING_API_URL")
HEADERS = {"Content-Type": "application/json"}


이건 두군데 다 없네
Sheets_ChatGPT의 말:

네 맞습니다 👍
올려주신 최신 app.py 에서는

API_BASE = os.getenv("API_BASE")
API_URL = os.getenv("COUNSELING_API_URL")
HEADERS = {"Content-Type": "application/json"}


이 세 줄이 실제 코드에서는 안 쓰이고 있었습니다.

📌 이유

API_BASE

과거 버전에서는 _post() 같은 함수에서 urljoin(API_BASE, path) 형태로 쓰였지만,

지금 app.py 안에는 _post 호출이 없고, 대신 Google Sheets 직접 연동 코드 (gspread) 만 있습니다.

API_URL (COUNSELING_API_URL)

특정 상담일지 API 엔드포인트를 직접 호출하려던 흔적이지만,

현재는 사용되지 않고 있음. (requests.post(API_URL, ...) 같은 코드 없음)

HEADERS

마찬가지로, API 호출을 위해 기본 헤더를 지정했지만,

지금 app.py 는 Flask 서버 + Google Sheets 연동만 하고 있어서 필요 없음.

✅ 결론

API_BASE, API_URL, HEADERS → config.py에도, app.py에도 둘 필요 없음

만약 나중에 외부 API 호출 기능이 필요하면, config.py에 다시 정의해서 쓰면 됩니다.

👉 정리하면:

지금은 삭제해도 무방합니다.

추후 API 호출이 필요하다면 → config.py에

API_BASE = os.getenv("API_BASE")
HEADERS = {"Content-Type": "application/json"}
API_URLS = {"counseling": urljoin(API_BASE, "/add_counseling")}


이런 식으로 다시 넣으시면 됩니다.

원하시면 제가 현재 구조에서는 어떤 설정이 config.py에 꼭 필요하고, 어떤 건 빼도 되는지 체크리스트를 정리해드릴까요?

나의 말:


# ✅ 필수 환경 변수 확인
if not GOOGLE_SHEET_TITLE:
    raise EnvironmentError("환경변수 GOOGLE_SHEET_TITLE이 설정되지 않았습니다.")


def some_function():
    print("작업 시작")
    time.sleep(1)
    print("작업 완료")


# ✅ 확인용 출력 (선택)
print("✅ GOOGLE_SHEET_TITLE:", os.getenv("GOOGLE_SHEET_TITLE"))
print("✅ GOOGLE_SHEET_KEY 존재 여부:", "Yes" if os.getenv("GOOGLE_SHEET_KEY") else "No")


# 🔽 파일 하단에 삽입 예시
def save_member(name):
    print(f"[✅] '{name}' 회원 등록")

def update_member_fields(name, fields):
    print(f"[✏️] '{name}' 필드 업데이트: {fields}")



이 코드는 없어도 되나?
Sheets_ChatGPT의 말:

네, 올려주신 코드 블록은 대부분 개발 중 디버깅용이거나 예시 함수라서, 실제 운영에는 없어도 됩니다.

📌 코드별로 필요 여부 정리
1. 필수 환경 변수 확인
if not GOOGLE_SHEET_TITLE:
    raise EnvironmentError("환경변수 GOOGLE_SHEET_TITLE이 설정되지 않았습니다.")


✅ 유지 추천

이유: 실행 시 환경변수 누락을 바로 알 수 있음 → 에러 디버깅이 쉬워짐.

다만, 이건 config.py 로 옮기는 게 더 적절합니다.

2. some_function()
def some_function():
    print("작업 시작")
    time.sleep(1)
    print("작업 완료")


❌ 삭제 가능

그냥 테스트용 함수 → 실제 로직과 무관.

3. 확인용 출력
print("✅ GOOGLE_SHEET_TITLE:", os.getenv("GOOGLE_SHEET_TITLE"))
print("✅ GOOGLE_SHEET_KEY 존재 여부:", "Yes" if os.getenv("GOOGLE_SHEET_KEY") else "No")


⚠️ 개발 중에는 유용하지만, 운영 코드에서는 불필요.

선택:

디버깅 필요 → logging 모듈로 바꾸는 게 좋음

아니면 삭제해도 무방

4. 예시 함수 (save_member, update_member_fields)
def save_member(name):
    print(f"[✅] '{name}' 회원 등록")

def update_member_fields(name, fields):
    print(f"[✏️] '{name}' 필드 업데이트: {fields}")


❌ 삭제 가능

단순 출력용 더미 함수.

실제 utils/member.py 에서 구현한 update_member_field, update_member_field_strict 가 있으므로 중복.

✅ 정리

유지: 환경변수 체크 (GOOGLE_SHEET_TITLE) → 단, config.py로 옮기는 게 맞음.

삭제 가능: some_function, 확인용 print, 예시 함수(save_member, update_member_fields).

👉 원하시면 제가 이 부분을 반영해서, app.py 와 config.py 최종 정리본을 만들어드릴까요?

나의 말:
디버깅 필요 → logging 모듈로 바꾸는 게 좋음
Sheets_ChatGPT의 말:

맞습니다 👍
print() 대신 logging 모듈을 쓰면

로그 레벨(DEBUG, INFO, WARNING, ERROR, CRITICAL) 구분 가능

개발/운영 환경에 맞게 출력 위치(콘솔, 파일 등) 바꾸기 쉬움

나중에 에러 추적도 더 편해집니다.

📌 logging 적용 예시
1. app.py 상단에 추가
import logging

# ✅ 기본 로그 설정
logging.basicConfig(
    level=logging.INFO,  # DEBUG로 바꾸면 상세 로그 확인 가능
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

2. 기존 print() → logger 변경
# 기존
print(f"시트에 연결되었습니다. (ID={SHEET_KEY})")

# 변경
logger.info(f"시트에 연결되었습니다. (ID={SHEET_KEY})")

# 기존
print("✅ GOOGLE_SHEET_TITLE:", os.getenv("GOOGLE_SHEET_TITLE"))
print("✅ GOOGLE_SHEET_KEY 존재 여부:", "Yes" if os.getenv("GOOGLE_SHEET_KEY") else "No")

# 변경
logger.debug(f"GOOGLE_SHEET_TITLE: {os.getenv('GOOGLE_SHEET_TITLE')}")
logger.debug(f"GOOGLE_SHEET_KEY 존재 여부: {'Yes' if os.getenv('GOOGLE_SHEET_KEY') else 'No'}")

3. 함수 내부도 변경 가능
def save_member(name):
    logger.info(f"[✅] '{name}' 회원 등록")

def update_member_fields(name, fields):
    logger.info(f"[✏️] '{name}' 필드 업데이트: {fields}")

📌 실행 시 로그 예시
2025-08-28 11:22:33 [INFO] 시트에 연결되었습니다. (ID=abcd1234)
2025-08-28 11:22:33 [DEBUG] GOOGLE_SHEET_TITLE: 회원관리시트
2025-08-28 11:22:33 [INFO] '홍길동' 회원 등록


✅ 요약:

print() → logger.info() (중요 로그)

print() → logger.debug() (디버깅용 로그)

필요할 때 logger.error(), logger.warning() 으로 세분화 가능

👉 원하시면 제가 지금 app.py 전체에서 print → logging 교체 버전을 만들어드릴까요?

나의 말:
project/
 ├─ app.py
 ├─ parser.py
 ├─ config.py
 └─ utils/
     ├─ __init__.py
     ├─ api.py
     ├─ sheets.py
     ├─ member.py
     ├─ order.py
     └─ commission.py   ✅ 추가

이 구조로 모두 조정할게 알려 줘
회원 조회부터
# ✅ 회원 조회
@app.route("/find_member", methods=["POST"])
def find_member():
    try:
        data = request.get_json()
        name = data.get("회원명", "").strip()
        number = data.get("회원번호", "").strip()

        if not name and not number:
            return jsonify({"error": "회원명 또는 회원번호를 입력해야 합니다."}), 400

        sheet = get_member_sheet()
        db = sheet.get_all_values()
        headers, rows = db[0], db[1:]

        matched = []
        for row in rows:
            row_dict = dict(zip(headers, row))
            if name and row_dict.get("회원명") == name:
                matched.append(row_dict)
            elif number and row_dict.get("회원번호") == number:
                matched.append(row_dict)

        if not matched:
            return jsonify({"error": "해당 회원 정보를 찾을 수 없습니다."}), 404

        def clean_data(member):
            # 빈 값 제거 + 주요 필드만 필터링
            important_keys = [
                "회원명", "회원번호", "휴대폰번호", "특수번호",
                "가입일자", "생년월일", "근무처", "계보도", "소개한분", "주소"
            ]
            return {k: v for k, v in member.items() if v.strip() and k in important_keys}

        if len(matched) == 1:
            return jsonify(clean_data(matched[0])), 200

        result = []
        for idx, member in enumerate(matched, start=1):
            result.append(clean_data(member))
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
Sheets_ChatGPT의 말:

좋습니다 👍 지금 프로젝트 구조(app.py, parser.py, config.py, utils/) 에 맞춰서 회원 조회 기능을 분리해드리겠습니다.

📂 구조 (회원 조회 추가)
project/
 ├─ app.py              # Flask 라우팅
 ├─ parser.py           # (일지 관련 파서 유지)
 ├─ config.py           # 환경설정
 └─ utils/
     ├─ __init__.py
     ├─ api.py
     ├─ sheets.py       # 구글 시트 공통 접근
     ├─ member.py       # ✅ 회원 관련 기능 (조회/등록/수정/삭제)
     ├─ order.py
     └─ commission.py

📌 utils/member.py (회원 조회 기능 추가)
from utils.sheets import get_member_sheet

def find_member(name: str = "", number: str = "") -> list[dict]:
    """
    회원명 또는 회원번호로 DB 시트에서 회원 조회
    """
    sheet = get_member_sheet()
    db = sheet.get_all_values()
    if not db or len(db) < 2:
        return []

    headers, rows = db[0], db[1:]

    matched = []
    for row in rows:
        row_dict = dict(zip(headers, row))
        if name and row_dict.get("회원명") == name.strip():
            matched.append(row_dict)
        elif number and row_dict.get("회원번호") == number.strip():
            matched.append(row_dict)

    return matched


def clean_member_data(member: dict) -> dict:
    """
    빈 값 제거 + 주요 필드만 필터링
    """
    important_keys = [
        "회원명", "회원번호", "휴대폰번호", "특수번호",
        "가입일자", "생년월일", "근무처", "계보도", "소개한분", "주소"
    ]
    return {k: v for k, v in member.items() if v.strip() and k in important_keys}

📌 app.py (라우트에서 utils 호출)
from flask import Flask, request, jsonify
from utils.member import find_member, clean_member_data

app = Flask(__name__)

# ✅ 회원 조회
@app.route("/find_member", methods=["POST"])
def find_member_route():
    try:
        data = request.get_json()
        name = data.get("회원명", "").strip()
        number = data.get("회원번호", "").strip()

        if not name and not number:
            return jsonify({"error": "회원명 또는 회원번호를 입력해야 합니다."}), 400

        matched = find_member(name, number)

        if not matched:
            return jsonify({"error": "해당 회원 정보를 찾을 수 없습니다."}), 404

        if len(matched) == 1:
            return jsonify(clean_member_data(matched[0])), 200

        result = [clean_member_data(m) for m in matched]
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

✅ 요약

utils/member.py

find_member(name, number) → DB 시트에서 조회

clean_member_data(member) → 필요한 필드만 반환

app.py

라우트(/find_member) 에서는 utils 함수만 호출

Flask 라우트는 최대한 얇게 유지

👉 이제 같은 방식으로 회원 등록 / 수정 / 삭제 도 utils/member.py 안에 정리하고,
app.py 에는 라우트만 추가하면 됩니다.

원하시면 제가 회원 등록 도 지금 구조에 맞게 추가해서 보여드릴까요?

나의 말:
회원 등록 도 지금 구조에 맞게 추가
Sheets_ChatGPT의 말:

좋습니다 👍 그럼 지금 구조에 맞춰서 회원 등록 기능을 추가해드리겠습니다.

📂 구조 업데이트
project/
 ├─ app.py              # Flask 라우팅
 ├─ parser.py           
 ├─ config.py           
 └─ utils/
     ├─ __init__.py
     ├─ api.py
     ├─ sheets.py
     ├─ member.py       # ✅ 회원 조회 + 등록
     ├─ order.py
     └─ commission.py

📌 utils/member.py (회원 등록 추가)
from utils.sheets import get_member_sheet

def find_member(name: str = "", number: str = "") -> list[dict]:
    """회원명 또는 회원번호로 DB 시트에서 회원 조회"""
    sheet = get_member_sheet()
    db = sheet.get_all_values()
    if not db or len(db) < 2:
        return []

    headers, rows = db[0], db[1:]
    matched = []
    for row in rows:
        row_dict = dict(zip(headers, row))
        if name and row_dict.get("회원명") == name.strip():
            matched.append(row_dict)
        elif number and row_dict.get("회원번호") == number.strip():
            matched.append(row_dict)

    return matched


def clean_member_data(member: dict) -> dict:
    """빈 값 제거 + 주요 필드만 필터링"""
    important_keys = [
        "회원명", "회원번호", "휴대폰번호", "특수번호",
        "가입일자", "생년월일", "근무처", "계보도", "소개한분", "주소"
    ]
    return {k: v for k, v in member.items() if v.strip() and k in important_keys}


def register_member(name: str, number: str = "", phone: str = "") -> bool:
    """
    회원 등록 - DB 시트에 새로운 회원 추가
    """
    sheet = get_member_sheet()
    headers = sheet.row_values(1)

    if "회원명" not in headers:
        raise RuntimeError("DB 시트에 '회원명' 헤더가 없습니다.")

    # 중복 체크
    existing = find_member(name, number)
    if existing:
        raise ValueError(f"이미 등록된 회원입니다: {name} / {number}")

    row = {}
    for h in headers:
        row[h] = ""

    row["회원명"] = name.strip()
    if number:
        row["회원번호"] = number.strip()
    if phone:
        row["휴대폰번호"] = phone.strip()

    # 시트에 추가
    values = [row.get(h, "") for h in headers]
    sheet.append_row(values)
    return True

📌 app.py (회원 등록 라우트 추가)
from flask import Flask, request, jsonify
from utils.member import find_member, clean_member_data, register_member

app = Flask(__name__)

# ✅ 회원 등록
@app.route("/register_member", methods=["POST"])
def register_member_route():
    try:
        data = request.get_json()
        name = data.get("회원명", "").strip()
        number = data.get("회원번호", "").strip()
        phone = data.get("휴대폰번호", "").strip()

        if not name:
            return jsonify({"error": "회원명은 필수 입력 항목입니다."}), 400

        register_member(name, number, phone)
        return jsonify({"message": f"{name}님이 성공적으로 등록되었습니다."}), 201

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

✅ 사용 예시
회원 등록 요청
curl -X POST http://localhost:5000/register_member \
     -H "Content-Type: application/json" \
     -d '{"회원명":"홍길동","회원번호":"123456","휴대폰번호":"010-1234-5678"}'

응답
{
  "message": "홍길동님이 성공적으로 등록되었습니다."
}

🚀 정리

utils/member.py

register_member() : DB 시트에 신규 회원 추가

중복 방지 (이름/회원번호 체크)

app.py

/register_member : 회원 등록 API

👉 원하시면 제가 회원 수정도 같은 구조(utils/member.py + app.py 라우트)로 정리해드릴까요?

나의 말:
회원 수정도 같은 구조
Sheets_ChatGPT의 말:

좋습니다 👍
그럼 이번에는 회원 수정 기능을 utils/member.py 와 app.py 에 맞게 정리해드리겠습니다.

📂 구조 (회원 수정 추가)
project/
 ├─ app.py
 ├─ parser.py
 ├─ config.py
 └─ utils/
     ├─ __init__.py
     ├─ api.py
     ├─ sheets.py
     ├─ member.py   # ✅ 회원 조회 + 등록 + 수정
     ├─ order.py
     └─ commission.py

📌 utils/member.py (회원 수정 추가)
from utils.sheets import get_member_sheet, safe_update_cell

def find_member(name: str = "", number: str = "") -> list[dict]:
    """회원명 또는 회원번호로 DB 시트에서 회원 조회"""
    sheet = get_member_sheet()
    db = sheet.get_all_values()
    if not db or len(db) < 2:
        return []

    headers, rows = db[0], db[1:]
    matched = []
    for row in rows:
        row_dict = dict(zip(headers, row))
        if name and row_dict.get("회원명") == name.strip():
            matched.append(row_dict)
        elif number and row_dict.get("회원번호") == number.strip():
            matched.append(row_dict)

    return matched


def clean_member_data(member: dict) -> dict:
    """빈 값 제거 + 주요 필드만 필터링"""
    important_keys = [
        "회원명", "회원번호", "휴대폰번호", "특수번호",
        "가입일자", "생년월일", "근무처", "계보도", "소개한분", "주소"
    ]
    return {k: v for k, v in member.items() if v.strip() and k in important_keys}


def register_member(name: str, number: str = "", phone: str = "") -> bool:
    """회원 등록 - DB 시트에 새로운 회원 추가"""
    sheet = get_member_sheet()
    headers = sheet.row_values(1)

    if "회원명" not in headers:
        raise RuntimeError("DB 시트에 '회원명' 헤더가 없습니다.")

    # 중복 체크
    existing = find_member(name, number)
    if existing:
        raise ValueError(f"이미 등록된 회원입니다: {name} / {number}")

    row = {h: "" for h in headers}
    row["회원명"] = name.strip()
    if number:
        row["회원번호"] = number.strip()
    if phone:
        row["휴대폰번호"] = phone.strip()

    values = [row.get(h, "") for h in headers]
    sheet.append_row(values)
    return True


def update_member(name: str, updates: dict) -> bool:
    """
    회원 수정 - 특정 회원의 필드를 업데이트
    updates: {"휴대폰번호": "010-1234-5678", "주소": "서울시 강남구"}
    """
    sheet = get_member_sheet()
    headers = sheet.row_values(1)

    if "회원명" not in headers:
        raise RuntimeError("DB 시트에 '회원명' 헤더가 없습니다.")

    values = sheet.get_all_values()
    member_col = headers.index("회원명") + 1
    target_row = None

    for i, row in enumerate(values[1:], start=2):
        if len(row) >= member_col and row[member_col - 1] == name.strip():
            target_row = i
            break

    if not target_row:
        raise ValueError(f"'{name}' 회원을 찾을 수 없습니다.")

    for field, value in updates.items():
        if field not in headers:
            continue  # 없는 필드는 무시
        col = headers.index(field) + 1
        safe_update_cell(sheet, target_row, col, value, clear_first=True)

    return True

📌 app.py (회원 수정 라우트 추가)
from flask import Flask, request, jsonify
from utils.member import find_member, clean_member_data, register_member, update_member

app = Flask(__name__)

# ✅ 회원 수정
@app.route("/update_member", methods=["POST"])
def update_member_route():
    try:
        data = request.get_json()
        name = data.get("회원명", "").strip()
        updates = data.get("수정목록", {})

        if not name:
            return jsonify({"error": "회원명은 필수 입력 항목입니다."}), 400
        if not isinstance(updates, dict) or not updates:
            return jsonify({"error": "수정할 필드를 지정해야 합니다."}), 400

        update_member(name, updates)
        return jsonify({"message": f"{name}님의 정보가 성공적으로 수정되었습니다."}), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

✅ 사용 예시
회원 수정 요청
curl -X POST http://localhost:5000/update_member \
     -H "Content-Type: application/json" \
     -d '{
           "회원명": "홍길동",
           "수정목록": {
               "휴대폰번호": "010-9999-8888",
               "주소": "서울시 서초구"
           }
         }'

응답
{
  "message": "홍길동님의 정보가 성공적으로 수정되었습니다."
}

🚀 정리

utils/member.py

update_member(name, updates) → 시트에서 해당 회원 행 찾아 특정 필드 수정

app.py

/update_member 라우트 → JSON 입력 받아 utils 함수 호출

👉 다음 단계로 회원 삭제도 같은 구조(utils/member.py + app.py)로 정리해드릴까요?

나의 말:
회원 삭제도 같은 구조
Sheets_ChatGPT의 말:

좋습니다 👍
이번에는 회원 삭제 기능을 utils/member.py 와 app.py 에 같은 구조로 정리해드리겠습니다.

📂 구조 (회원 삭제 추가)
project/
 ├─ app.py
 ├─ parser.py
 ├─ config.py
 └─ utils/
     ├─ __init__.py
     ├─ api.py
     ├─ sheets.py
     ├─ member.py   # ✅ 조회 + 등록 + 수정 + 삭제
     ├─ order.py
     └─ commission.py

📌 utils/member.py (회원 삭제 추가)
from utils.sheets import get_member_sheet, safe_update_cell

def find_member(name: str = "", number: str = "") -> list[dict]:
    """회원명 또는 회원번호로 DB 시트에서 회원 조회"""
    sheet = get_member_sheet()
    db = sheet.get_all_values()
    if not db or len(db) < 2:
        return []

    headers, rows = db[0], db[1:]
    matched = []
    for row in rows:
        row_dict = dict(zip(headers, row))
        if name and row_dict.get("회원명") == name.strip():
            matched.append(row_dict)
        elif number and row_dict.get("회원번호") == number.strip():
            matched.append(row_dict)
    return matched


def clean_member_data(member: dict) -> dict:
    """빈 값 제거 + 주요 필드만 필터링"""
    important_keys = [
        "회원명", "회원번호", "휴대폰번호", "특수번호",
        "가입일자", "생년월일", "근무처", "계보도", "소개한분", "주소"
    ]
    return {k: v for k, v in member.items() if v.strip() and k in important_keys}


def register_member(name: str, number: str = "", phone: str = "") -> bool:
    """회원 등록 - DB 시트에 새로운 회원 추가"""
    sheet = get_member_sheet()
    headers = sheet.row_values(1)

    if "회원명" not in headers:
        raise RuntimeError("DB 시트에 '회원명' 헤더가 없습니다.")

    # 중복 체크
    existing = find_member(name, number)
    if existing:
        raise ValueError(f"이미 등록된 회원입니다: {name} / {number}")

    row = {h: "" for h in headers}
    row["회원명"] = name.strip()
    if number:
        row["회원번호"] = number.strip()
    if phone:
        row["휴대폰번호"] = phone.strip()

    values = [row.get(h, "") for h in headers]
    sheet.append_row(values)
    return True


def update_member(name: str, updates: dict) -> bool:
    """회원 수정 - 특정 회원의 필드를 업데이트"""
    sheet = get_member_sheet()
    headers = sheet.row_values(1)

    if "회원명" not in headers:
        raise RuntimeError("DB 시트에 '회원명' 헤더가 없습니다.")

    values = sheet.get_all_values()
    member_col = headers.index("회원명") + 1
    target_row = None

    for i, row in enumerate(values[1:], start=2):
        if len(row) >= member_col and row[member_col - 1] == name.strip():
            target_row = i
            break

    if not target_row:
        raise ValueError(f"'{name}' 회원을 찾을 수 없습니다.")

    for field, value in updates.items():
        if field not in headers:
            continue  # 없는 필드는 무시
        col = headers.index(field) + 1
        safe_update_cell(sheet, target_row, col, value, clear_first=True)

    return True


def delete_member(name: str) -> bool:
    """
    회원 삭제 - DB 시트에서 해당 회원 행 제거
    """
    sheet = get_member_sheet()
    headers = sheet.row_values(1)

    if "회원명" not in headers:
        raise RuntimeError("DB 시트에 '회원명' 헤더가 없습니다.")

    values = sheet.get_all_values()
    member_col = headers.index("회원명") + 1
    target_row = None

    for i, row in enumerate(values[1:], start=2):
        if len(row) >= member_col and row[member_col - 1] == name.strip():
            target_row = i
            break

    if not target_row:
        raise ValueError(f"'{name}' 회원을 찾을 수 없습니다.")

    sheet.delete_rows(target_row)
    return True

📌 app.py (회원 삭제 라우트 추가)
from flask import Flask, request, jsonify
from parser.member import (
    find_member, clean_member_data,
    register_member, update_member, delete_member
)

app = Flask(__name__)

# ✅ 회원 삭제
@app.route("/delete_member", methods=["POST"])
def delete_member_route():
    try:
        data = request.get_json()
        name = data.get("회원명", "").strip()

        if not name:
            return jsonify({"error": "회원명은 필수 입력 항목입니다."}), 400

        delete_member(name)
        return jsonify({"message": f"{name}님이 성공적으로 삭제되었습니다."}), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

✅ 사용 예시
회원 삭제 요청
curl -X POST http://localhost:5000/delete_member \
     -H "Content-Type: application/json" \
     -d '{"회원명":"홍길동"}'

응답
{
  "message": "홍길동님이 성공적으로 삭제되었습니다."
}

🚀 정리

utils/member.py

delete_member(name) → DB 시트에서 해당 회원 행 찾아 삭제

app.py

/delete_member 라우트 → JSON 입력 받아 utils 함수 호출

👉 이제 회원 관련해서 조회 / 등록 / 수정 / 삭제 (CRUD) 가 전부 완성됐습니다.
원하시면 제가 order.py 도 같은 구조로 CRUD 정리해드릴까요?

나의 말:
order.py 도 같은 구조
Sheets_ChatGPT의 말:

좋습니다 👍
이번에는 주문(제품주문) 관리를 order.py + app.py 구조로 CRUD 형태로 정리해드리겠습니다.

📂 프로젝트 구조 (주문 CRUD 추가)
project/
 ├─ app.py
 ├─ parser.py
 ├─ config.py
 └─ utils/
     ├─ __init__.py
     ├─ api.py
     ├─ sheets.py
     ├─ member.py
     ├─ order.py       # ✅ 주문 CRUD
     └─ commission.py

📌 utils/order.py (주문 CRUD)
from utils.sheets import get_order_sheet, safe_update_cell
from parser import process_order_date


def find_order(member_name: str = "", product: str = "") -> list[dict]:
    """회원명 또는 제품명으로 주문 조회"""
    sheet = get_order_sheet()
    db = sheet.get_all_values()
    if not db or len(db) < 2:
        return []

    headers, rows = db[0], db[1:]
    matched = []
    for row in rows:
        row_dict = dict(zip(headers, row))
        if member_name and row_dict.get("회원명") == member_name.strip():
            matched.append(row_dict)
        elif product and product in row_dict.get("제품명", ""):
            matched.append(row_dict)

    return matched


def clean_order_data(order: dict) -> dict:
    """빈 값 제거 + 주요 필드만 반환"""
    important_keys = [
        "주문일자", "회원명", "회원번호", "휴대폰번호",
        "제품명", "제품가격", "PV", "결재방법",
        "소비자_고객명", "소비자_휴대폰번호",
        "배송처", "수령확인"
    ]
    return {k: v for k, v in order.items() if v.strip() and k in important_keys}


def register_order(member_name: str, product: str, price: str, pv: str,
                   method: str, delivery: str = "", date: str = None) -> bool:
    """신규 주문 등록"""
    sheet = get_order_sheet()
    headers = sheet.row_values(1)

    row = {h: "" for h in headers}
    row["주문일자"] = date or process_order_date("오늘")
    row["회원명"] = member_name.strip()
    row["제품명"] = product.strip()
    row["제품가격"] = price
    row["PV"] = pv
    row["결재방법"] = method
    row["배송처"] = delivery

    values = [row.get(h, "") for h in headers]
    sheet.append_row(values)
    return True


def update_order(member_name: str, product: str, updates: dict) -> bool:
    """특정 회원 + 제품 기준으로 주문 수정"""
    sheet = get_order_sheet()
    headers = sheet.row_values(1)

    values = sheet.get_all_values()
    member_col = headers.index("회원명") + 1
    product_col = headers.index("제품명") + 1
    target_row = None

    for i, row in enumerate(values[1:], start=2):
        if (len(row) >= member_col and row[member_col - 1] == member_name.strip() and
                len(row) >= product_col and product in row[product_col - 1]):
            target_row = i
            break

    if not target_row:
        raise ValueError(f"'{member_name}'님의 '{product}' 주문을 찾을 수 없습니다.")

    for field, value in updates.items():
        if field not in headers:
            continue
        col = headers.index(field) + 1
        safe_update_cell(sheet, target_row, col, value, clear_first=True)

    return True


def delete_order(member_name: str, product: str) -> bool:
    """특정 회원 + 제품 주문 삭제"""
    sheet = get_order_sheet()
    headers = sheet.row_values(1)

    values = sheet.get_all_values()
    member_col = headers.index("회원명") + 1
    product_col = headers.index("제품명") + 1
    target_row = None

    for i, row in enumerate(values[1:], start=2):
        if (len(row) >= member_col and row[member_col - 1] == member_name.strip() and
                len(row) >= product_col and product in row[product_col - 1]):
            target_row = i
            break

    if not target_row:
        raise ValueError(f"'{member_name}'님의 '{product}' 주문을 찾을 수 없습니다.")

    sheet.delete_rows(target_row)
    return True

📌 app.py (주문 CRUD 라우트 추가)
from flask import Flask, request, jsonify
from parser.order import (
    find_order, clean_order_data,
    register_order, update_order, delete_order
)

app = Flask(__name__)

# ✅ 주문 조회
@app.route("/find_order", methods=["POST"])
def find_order_route():
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


# ✅ 주문 등록
@app.route("/register_order", methods=["POST"])
def register_order_route():
    try:
        data = request.get_json()
        member = data.get("회원명", "").strip()
        product = data.get("제품명", "").strip()
        price = data.get("제품가격", "").strip()
        pv = data.get("PV", "").strip()
        method = data.get("결재방법", "").strip()
        delivery = data.get("배송처", "").strip()
        date = data.get("주문일자", "").strip()

        if not member or not product:
            return jsonify({"error": "회원명과 제품명은 필수 입력 항목입니다."}), 400

        register_order(member, product, price, pv, method, delivery, date)
        return jsonify({"message": f"{member}님의 '{product}' 주문이 등록되었습니다."}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ 주문 수정
@app.route("/update_order", methods=["POST"])
def update_order_route():
    try:
        data = request.get_json()
        member = data.get("회원명", "").strip()
        product = data.get("제품명", "").strip()
        updates = data.get("수정목록", {})

        if not member or not product:
            return jsonify({"error": "회원명과 제품명은 필수 입력 항목입니다."}), 400
        if not isinstance(updates, dict) or not updates:
            return jsonify({"error": "수정할 필드를 지정해야 합니다."}), 400

        update_order(member, product, updates)
        return jsonify({"message": f"{member}님의 '{product}' 주문이 수정되었습니다."}), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ 주문 삭제
@app.route("/delete_order", methods=["POST"])
def delete_order_route():
    try:
        data = request.get_json()
        member = data.get("회원명", "").strip()
        product = data.get("제품명", "").strip()

        if not member or not product:
            return jsonify({"error": "회원명과 제품명은 필수 입력 항목입니다."}), 400

        delete_order(member, product)
        return jsonify({"message": f"{member}님의 '{product}' 주문이 삭제되었습니다."}), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

✅ 사용 예시
주문 등록
curl -X POST http://localhost:5000/register_order \
     -H "Content-Type: application/json" \
     -d '{"회원명":"김지연","제품명":"노니","제품가격":"30000","PV":"30","결재방법":"카드","배송처":"서울"}'

주문 조회
curl -X POST http://localhost:5000/find_order \
     -H "Content-Type: application/json" \
     -d '{"회원명":"김지연"}'

주문 수정
curl -X POST http://localhost:5000/update_order \
     -H "Content-Type: application/json" \
     -d '{"회원명":"김지연","제품명":"노니","수정목록":{"결재방법":"현금"}}'

주문 삭제
curl -X POST http://localhost:5000/delete_order \
     -H "Content-Type: application/json" \
     -d '{"회원명":"김지연","제품명":"노니"}'

🚀 정리

utils/order.py

find_order, register_order, update_order, delete_order → 주문 CRUD

app.py

/find_order, /register_order, /update_order, /delete_order 라우트

👉 이제 회원 + 주문 모두 CRUD 완성됐습니다.
원하시면 제가 commission.py (후원수당) 도 같은 구조로 CRUD 정리해드릴까요?

나의 말:
네
Sheets_ChatGPT의 말:

좋습니다 👍
이제 후원수당(commission) 도 같은 구조로 CRUD 정리해드리겠습니다.

📂 프로젝트 구조 (후원수당 CRUD 추가)
project/
 ├─ app.py
 ├─ parser.py
 ├─ config.py
 └─ utils/
     ├─ __init__.py
     ├─ api.py
     ├─ sheets.py
     ├─ member.py
     ├─ order.py
     └─ commission.py   # ✅ 후원수당 CRUD

📌 utils/commission.py (후원수당 CRUD)
from utils.sheets import get_commission_sheet, safe_update_cell
from parser import process_order_date


def find_commission(member_name: str = "") -> list[dict]:
    """회원명으로 후원수당 조회"""
    sheet = get_commission_sheet()
    db = sheet.get_all_values()
    if not db or len(db) < 2:
        return []

    headers, rows = db[0], db[1:]
    matched = []
    for row in rows:
        row_dict = dict(zip(headers, row))
        if member_name and row_dict.get("회원명") == member_name.strip():
            matched.append(row_dict)

    return matched


def clean_commission_data(commission: dict) -> dict:
    """빈 값 제거 + 주요 필드만 반환"""
    important_keys = [
        "지급일자", "회원명", "회원번호", "후원수당", "비고"
    ]
    return {k: v for k, v in commission.items() if v.strip() and k in important_keys}


def register_commission(member_name: str, amount: str, note: str = "", date: str = None) -> bool:
    """신규 후원수당 등록"""
    sheet = get_commission_sheet()
    headers = sheet.row_values(1)

    row = {h: "" for h in headers}
    row["지급일자"] = date or process_order_date("오늘")
    row["회원명"] = member_name.strip()
    row["후원수당"] = amount
    row["비고"] = note

    values = [row.get(h, "") for h in headers]
    sheet.append_row(values)
    return True


def update_commission(member_name: str, date: str, updates: dict) -> bool:
    """특정 회원 + 지급일자 기준 후원수당 수정"""
    sheet = get_commission_sheet()
    headers = sheet.row_values(1)

    values = sheet.get_all_values()
    member_col = headers.index("회원명") + 1
    date_col = headers.index("지급일자") + 1
    target_row = None

    for i, row in enumerate(values[1:], start=2):
        if (len(row) >= member_col and row[member_col - 1] == member_name.strip() and
                len(row) >= date_col and row[date_col - 1] == date.strip()):
            target_row = i
            break

    if not target_row:
        raise ValueError(f"'{member_name}'님의 '{date}' 후원수당을 찾을 수 없습니다.")

    for field, value in updates.items():
        if field not in headers:
            continue
        col = headers.index(field) + 1
        safe_update_cell(sheet, target_row, col, value, clear_first=True)

    return True


def delete_commission(member_name: str, date: str) -> bool:
    """특정 회원 + 지급일자 후원수당 삭제"""
    sheet = get_commission_sheet()
    headers = sheet.row_values(1)

    values = sheet.get_all_values()
    member_col = headers.index("회원명") + 1
    date_col = headers.index("지급일자") + 1
    target_row = None

    for i, row in enumerate(values[1:], start=2):
        if (len(row) >= member_col and row[member_col - 1] == member_name.strip() and
                len(row) >= date_col and row[date_col - 1] == date.strip()):
            target_row = i
            break

    if not target_row:
        raise ValueError(f"'{member_name}'님의 '{date}' 후원수당을 찾을 수 없습니다.")

    sheet.delete_rows(target_row)
    return True

📌 app.py (후원수당 CRUD 라우트 추가)
from flask import Flask, request, jsonify
from parser.commission import (
    find_commission, clean_commission_data,
    register_commission, update_commission, delete_commission
)

app = Flask(__name__)

# ✅ 후원수당 조회
@app.route("/find_commission", methods=["POST"])
def find_commission_route():
    try:
        data = request.get_json()
        member = data.get("회원명", "").strip()

        if not member:
            return jsonify({"error": "회원명은 필수 입력 항목입니다."}), 400

        matched = find_commission(member)
        if not matched:
            return jsonify({"error": "해당 회원의 후원수당을 찾을 수 없습니다."}), 404

        if len(matched) == 1:
            return jsonify(clean_commission_data(matched[0])), 200

        return jsonify([clean_commission_data(c) for c in matched]), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ 후원수당 등록
@app.route("/register_commission", methods=["POST"])
def register_commission_route():
    try:
        data = request.get_json()
        member = data.get("회원명", "").strip()
        amount = data.get("후원수당", "").strip()
        note = data.get("비고", "").strip()
        date = data.get("지급일자", "").strip()

        if not member or not amount:
            return jsonify({"error": "회원명과 후원수당은 필수 입력 항목입니다."}), 400

        register_commission(member, amount, note, date)
        return jsonify({"message": f"{member}님의 후원수당 {amount}원이 등록되었습니다."}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ 후원수당 수정
@app.route("/update_commission", methods=["POST"])
def update_commission_route():
    try:
        data = request.get_json()
        member = data.get("회원명", "").strip()
        date = data.get("지급일자", "").strip()
        updates = data.get("수정목록", {})

        if not member or not date:
            return jsonify({"error": "회원명과 지급일자는 필수 입력 항목입니다."}), 400
        if not isinstance(updates, dict) or not updates:
            return jsonify({"error": "수정할 필드를 지정해야 합니다."}), 400

        update_commission(member, date, updates)
        return jsonify({"message": f"{member}님의 {date} 후원수당이 수정되었습니다."}), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ 후원수당 삭제
@app.route("/delete_commission", methods=["POST"])
def delete_commission_route():
    try:
        data = request.get_json()
        member = data.get("회원명", "").strip()
        date = data.get("지급일자", "").strip()

        if not member or not date:
            return jsonify({"error": "회원명과 지급일자는 필수 입력 항목입니다."}), 400

        delete_commission(member, date)
        return jsonify({"message": f"{member}님의 {date} 후원수당이 삭제되었습니다."}), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

✅ 사용 예시
후원수당 등록
curl -X POST http://localhost:5000/register_commission \
     -H "Content-Type: application/json" \
     -d '{"회원명":"이태수","후원수당":"50000","비고":"추천 보너스","지급일자":"2025-08-28"}'

후원수당 조회
curl -X POST http://localhost:5000/find_commission \
     -H "Content-Type: application/json" \
     -d '{"회원명":"이태수"}'

후원수당 수정
curl -X POST http://localhost:5000/update_commission \
     -H "Content-Type: application/json" \
     -d '{"회원명":"이태수","지급일자":"2025-08-28","수정목록":{"비고":"수정된 보너스"}}'

후원수당 삭제
curl -X POST http://localhost:5000/delete_commission \
     -H "Content-Type: application/json" \
     -d '{"회원명":"이태수","지급일자":"2025-08-28"}'

🚀 정리

utils/commission.py

find_commission, register_commission, update_commission, delete_commission → 후원수당 CRUD

app.py

/find_commission, /register_commission, /update_commission, /delete_commission 라우트

👉 이제 회원 / 주문 / 후원수당 전부 CRUD 구조로 통일됐습니다.
원하시면 상담/개인/활동 일지 (counseling, memo, activity) 도 같은 구조로 정리해드릴까요?

나의 말:
네
Sheets_ChatGPT의 말:

좋습니다 👍
이제 마지막으로 일지(상담/개인/활동) 도 utils/ 모듈과 app.py 라우트로 분리해 정리해드리겠습니다.

📂 프로젝트 구조 (일지 관리 추가)
project/
 ├─ app.py
 ├─ parser.py
 ├─ config.py
 └─ utils/
     ├─ __init__.py
     ├─ api.py
     ├─ sheets.py
     ├─ member.py
     ├─ order.py
     ├─ commission.py
     └─ memo.py        # ✅ 상담/개인/활동 일지 관리

📌 utils/memo.py (일지 CRUD)
from utils.sheets import get_counseling_sheet, get_personal_memo_sheet, get_activity_log_sheet
from parser import now_kst


def save_memo(sheet_name: str, member_name: str, content: str) -> bool:
    """
    상담일지 / 개인일지 / 활동일지 저장
    """
    if not member_name or not content:
        raise ValueError("회원명과 내용은 필수 입력 항목입니다.")

    if sheet_name == "상담일지":
        sheet = get_counseling_sheet()
    elif sheet_name == "개인일지":
        sheet = get_personal_memo_sheet()
    elif sheet_name == "활동일지":
        sheet = get_activity_log_sheet()
    else:
        raise ValueError(f"지원하지 않는 일지 종류: {sheet_name}")

    ts = now_kst().strftime("%Y-%m-%d %H:%M")
    sheet.insert_row([ts, member_name.strip(), content.strip()], index=2)
    return True


def find_memo(sheet_name: str, member_name: str) -> list[dict]:
    """
    특정 회원의 일지 조회
    """
    if sheet_name == "상담일지":
        sheet = get_counseling_sheet()
    elif sheet_name == "개인일지":
        sheet = get_personal_memo_sheet()
    elif sheet_name == "활동일지":
        sheet = get_activity_log_sheet()
    else:
        raise ValueError(f"지원하지 않는 일지 종류: {sheet_name}")

    db = sheet.get_all_values()
    if not db or len(db) < 2:
        return []

    headers, rows = db[0], db[1:]
    matched = []
    for row in rows:
        row_dict = dict(zip(headers, row))
        if member_name and row_dict.get("회원명") == member_name.strip():
            matched.append(row_dict)

    return matched

📌 app.py (일지 라우트 추가)
from flask import Flask, request, jsonify
from parser.memo import save_memo, find_memo

app = Flask(__name__)

# ✅ 일지 저장
@app.route("/save_memo", methods=["POST"])
def save_memo_route():
    try:
        data = request.get_json()
        sheet_name = data.get("일지종류", "").strip()
        member = data.get("회원명", "").strip()
        content = data.get("내용", "").strip()

        if not sheet_name or not member or not content:
            return jsonify({"error": "일지종류, 회원명, 내용은 필수 입력 항목입니다."}), 400

        save_memo(sheet_name, member, content)
        return jsonify({"message": f"{member}님의 {sheet_name} 저장 완료"}), 201

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ 일지 조회
@app.route("/find_memo", methods=["POST"])
def find_memo_route():
    try:
        data = request.get_json()
        sheet_name = data.get("일지종류", "").strip()
        member = data.get("회원명", "").strip()

        if not sheet_name or not member:
            return jsonify({"error": "일지종류와 회원명은 필수 입력 항목입니다."}), 400

        matched = find_memo(sheet_name, member)
        if not matched:
            return jsonify({"error": "해당 일지를 찾을 수 없습니다."}), 404

        return jsonify(matched), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

✅ 사용 예시
상담일지 저장
curl -X POST http://localhost:5000/save_memo \
     -H "Content-Type: application/json" \
     -d '{"일지종류":"상담일지","회원명":"김지연","내용":"첫 상담 완료"}'

상담일지 조회
curl -X POST http://localhost:5000/find_memo \
     -H "Content-Type: application/json" \
     -d '{"일지종류":"상담일지","회원명":"김지연"}'

🚀 최종 정리

이제 프로젝트 전체 CRUD 구조:

회원 (member.py) → /find_member, /register_member, /update_member, /delete_member

주문 (order.py) → /find_order, /register_order, /update_order, /delete_order

후원수당 (commission.py) → /find_commission, /register_commission, /update_commission, /delete_commission

일지 (memo.py) → /save_memo, /find_memo

👉 원하시면 제가 여기까지 만든 전체 라우트 목록(API 문서) 을 정리해드릴까요?

나의 말:
메모검색도
Sheets_ChatGPT의 말:

좋습니다 👍
그럼 메모 검색(상담/개인/활동 일지 전체에서 키워드 검색) 기능도 추가해드리겠습니다.

📂 프로젝트 구조 (메모 검색 추가)
project/
 ├─ app.py
 ├─ parser.py
 ├─ config.py
 └─ utils/
     ├─ __init__.py
     ├─ api.py
     ├─ sheets.py
     ├─ member.py
     ├─ order.py
     ├─ commission.py
     └─ memo.py       # ✅ 메모 CRUD + 검색

📌 utils/memo.py (검색 기능 추가)
from utils.sheets import get_counseling_sheet, get_personal_memo_sheet, get_activity_log_sheet
from parser import now_kst

def save_memo(sheet_name: str, member_name: str, content: str) -> bool:
    """상담일지 / 개인일지 / 활동일지 저장"""
    if not member_name or not content:
        raise ValueError("회원명과 내용은 필수 입력 항목입니다.")

    if sheet_name == "상담일지":
        sheet = get_counseling_sheet()
    elif sheet_name == "개인일지":
        sheet = get_personal_memo_sheet()
    elif sheet_name == "활동일지":
        sheet = get_activity_log_sheet()
    else:
        raise ValueError(f"지원하지 않는 일지 종류: {sheet_name}")

    ts = now_kst().strftime("%Y-%m-%d %H:%M")
    sheet.insert_row([ts, member_name.strip(), content.strip()], index=2)
    return True


def find_memo(sheet_name: str, member_name: str) -> list[dict]:
    """특정 회원의 일지 조회"""
    if sheet_name == "상담일지":
        sheet = get_counseling_sheet()
    elif sheet_name == "개인일지":
        sheet = get_personal_memo_sheet()
    elif sheet_name == "활동일지":
        sheet = get_activity_log_sheet()
    else:
        raise ValueError(f"지원하지 않는 일지 종류: {sheet_name}")

    db = sheet.get_all_values()
    if not db or len(db) < 2:
        return []

    headers, rows = db[0], db[1:]
    matched = []
    for row in rows:
        row_dict = dict(zip(headers, row))
        if member_name and row_dict.get("회원명") == member_name.strip():
            matched.append(row_dict)

    return matched


def search_memo(keywords: list[str], sheet_name: str = "전체") -> list[dict]:
    """
    키워드로 메모 검색
    - sheet_name = 전체 / 상담일지 / 개인일지 / 활동일지
    - keywords: 검색할 키워드 리스트
    """
    results = []

    # 시트 선택
    def _get_sheet(name):
        if name == "상담일지":
            return get_counseling_sheet()
        elif name == "개인일지":
            return get_personal_memo_sheet()
        elif name == "활동일지":
            return get_activity_log_sheet()
        else:
            return None

    sheets = []
    if sheet_name == "전체":
        sheets = [
            ("상담일지", get_counseling_sheet()),
            ("개인일지", get_personal_memo_sheet()),
            ("활동일지", get_activity_log_sheet()),
        ]
    else:
        s = _get_sheet(sheet_name)
        if not s:
            raise ValueError(f"지원하지 않는 일지 종류: {sheet_name}")
        sheets = [(sheet_name, s)]

    # 검색 실행
    for name, sheet in sheets:
        db = sheet.get_all_values()
        if not db or len(db) < 2:
            continue
        headers, rows = db[0], db[1:]

        for row in rows:
            row_dict = dict(zip(headers, row))
            text = " ".join(row).lower()
            if all(kw.lower() in text for kw in keywords):
                row_dict["일지종류"] = name
                results.append(row_dict)

    return results

📌 app.py (검색 라우트 추가)
from flask import Flask, request, jsonify
from parser.memo import save_memo, find_memo, search_memo

app = Flask(__name__)

# ✅ 메모 검색
@app.route("/search_memo", methods=["POST"])
def search_memo_route():
    try:
        data = request.get_json()
        keywords = data.get("키워드", [])
        sheet_name = data.get("일지종류", "전체").strip()

        if not keywords or not isinstance(keywords, list):
            return jsonify({"error": "검색할 키워드 리스트를 입력해야 합니다."}), 400

        results = search_memo(keywords, sheet_name)
        if not results:
            return jsonify({"error": "검색 결과가 없습니다."}), 404

        return jsonify(results), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

✅ 사용 예시
상담일지 검색
curl -X POST http://localhost:5000/search_memo \
     -H "Content-Type: application/json" \
     -d '{"키워드":["상담","노니"],"일지종류":"상담일지"}'

전체 메모 검색
curl -X POST http://localhost:5000/search_memo \
     -H "Content-Type: application/json" \
     -d '{"키워드":["김지연"]}'

🚀 정리

utils/memo.py

save_memo() → 메모 저장

find_memo() → 특정 회원 메모 조회

search_memo() → 키워드 검색 (상담/개인/활동/전체 지원)

app.py

/save_memo → 메모 저장

/find_memo → 회원별 메모 조회

/search_memo → 키워드 검색

👉 이렇게 하면 회원 / 주문 / 후원수당 / 메모 까지 CRUD + 검색이 완성됩니다.
원하시면 제가 여기까지 만든 API 전체를 하나의 README.md 문서로 정리해드릴까요?

나의 말:
네
Sheets_ChatGPT의 말:

좋습니다 🙌
이제까지 만든 회원 / 주문 / 후원수당 / 메모 API 전체를 정리한 README.md 문서를 드리겠습니다.
이 문서를 project/README.md 에 두시면, 프로젝트 구조와 API 사용법을 한눈에 볼 수 있어요.

📌 README.md (API 문서)
# 📊 Member & Order Management API

Flask + Google Sheets 기반의 **회원 / 주문 / 후원수당 / 메모 관리 API** 입니다.  
CRUD 및 검색 기능을 지원합니다.

---

## 📂 프로젝트 구조



project/
├─ app.py # Flask 서버 라우트
├─ parser.py # 일지 파서/시간 처리 등
├─ config.py # 환경 변수 설정
└─ utils/
├─ init.py
├─ api.py
├─ sheets.py # Google Sheets 공통 모듈
├─ member.py # 회원 CRUD
├─ order.py # 주문 CRUD
├─ commission.py # 후원수당 CRUD
└─ memo.py # 상담/개인/활동 일지 CRUD + 검색


---

## 🚀 API 목록

### 📌 회원(Member)

#### 1. 회원 조회
`POST /find_member`

```json
{
  "회원명": "홍길동"
}

2. 회원 등록

POST /register_member

{
  "회원명": "홍길동",
  "회원번호": "123456",
  "휴대폰번호": "010-1234-5678"
}

3. 회원 수정

POST /update_member

{
  "회원명": "홍길동",
  "수정목록": {
    "휴대폰번호": "010-9999-8888",
    "주소": "서울시 서초구"
  }
}

4. 회원 삭제

POST /delete_member

{
  "회원명": "홍길동"
}

📌 주문(Order)
1. 주문 조회

POST /find_order

{
  "회원명": "김지연"
}

2. 주문 등록

POST /register_order

{
  "회원명": "김지연",
  "제품명": "노니",
  "제품가격": "30000",
  "PV": "30",
  "결재방법": "카드",
  "배송처": "서울"
}

3. 주문 수정

POST /update_order

{
  "회원명": "김지연",
  "제품명": "노니",
  "수정목록": {
    "결재방법": "현금"
  }
}

4. 주문 삭제

POST /delete_order

{
  "회원명": "김지연",
  "제품명": "노니"
}

📌 후원수당(Commission)
1. 후원수당 조회

POST /find_commission

{
  "회원명": "이태수"
}

2. 후원수당 등록

POST /register_commission

{
  "회원명": "이태수",
  "후원수당": "50000",
  "비고": "추천 보너스",
  "지급일자": "2025-08-28"
}

3. 후원수당 수정

POST /update_commission

{
  "회원명": "이태수",
  "지급일자": "2025-08-28",
  "수정목록": {
    "비고": "수정된 보너스"
  }
}

4. 후원수당 삭제

POST /delete_commission

{
  "회원명": "이태수",
  "지급일자": "2025-08-28"
}

📌 메모(Memo: 상담/개인/활동 일지)
1. 메모 저장

POST /save_memo

{
  "일지종류": "상담일지",
  "회원명": "김지연",
  "내용": "첫 상담 완료"
}

2. 메모 조회

POST /find_memo

{
  "일지종류": "상담일지",
  "회원명": "김지연"
}

3. 메모 검색

POST /search_memo

{
  "키워드": ["상담", "노니"],
  "일지종류": "상담일지"   // 또는 "개인일지", "활동일지", "전체"
}

🛠️ 환경 변수 (.env 예시)
GOOGLE_SHEET_TITLE=회원관리시트
GOOGLE_SHEET_KEY=your-google-sheet-id
GOOGLE_CREDENTIALS_PATH=credentials.json
OPENAI_API_KEY=your-openai-key

📌 실행 방법
# 1. 가상환경 생성 & 활성화
python -m venv venv
source venv/bin/activate   # (윈도우: venv\Scripts\activate)

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 서버 실행
python app.py


서버 실행 후, API는 기본적으로 http://localhost:5000 에서 사용 가능합니다 🚀


---

✅ 이제 이 README.md 하나만 있으면,  
누구든지 프로젝트 구조 + API 기능 + 실행 방법을 바로 이해할 수 있습니다.  

👉 원하시면 제가 `requirements.txt` (Flask + gspread 등 필요한 라이브러리 목록)도 정리해드릴까요?
