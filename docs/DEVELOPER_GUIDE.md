# 📑 Parser ↔ Route 매핑 & 개발 가이드 (풀 버전)

이 문서는 `app.py` 와 `parser/` 모듈 연결 관계,  
그리고 각 API 라우트의 **입력(JSON Request) / 출력(Response)** 예시를 포함합니다.  

---

## 1. Parser ↔ app.py Route 매핑표

| Parser 함수 | 사용 라우트(API) | 설명 |
|-------------|-----------------|------|
| **parse_registration** | `/save_member`, `/register_member` | 요청문에서 회원명/회원번호/휴대폰/계보도 추출 |
| **parse_request_and_update** | `/update_member` | 자연어 문장을 `{필드: 값}` dict 로 변환 후 회원 수정 |
| **parse_deletion_request** | `/delete_member_field_nl` | “회원명 + 필드 삭제” 요청 파싱 |
| **parse_order_text_rule** | `/parse_and_save_order` | 자연어 주문 문장을 JSON 으로 변환 |
| **guess_intent** | 내부 로직 | 사용자의 의도를 분류 |
| **parse_natural_query** | `/members/search-nl` | 자연어 검색 문장에서 (검색 필드, 키워드) 추출 |
| **parse_request_line** | `/add_counseling` | 상담/개인/활동 일지 입력 파서 |
| **parse_counseling/parse_personal/parse_activity** | `/add_counseling` | 각 일지 저장용 파서 |
| **parse_commission_text** | `/register_commission`, `/update_commission` | 후원수당 등록/수정 문장 파서 |
| **ensure_orders_list** | `/upload_order_ipad`, `/upload_order_pc` | 단일 주문도 리스트로 변환 |
| **now_kst** | `/upload_order_ipad`, `/upload_order_pc` | 주문일자 기록 시 현재 시간 (KST) 사용 |
| **process_order_date** | `/register_order` | “오늘/어제/2025-08-29” 표현을 YYYY-MM-DD 로 변환 |
| **clean_tail_command** | (공통 유틸) | “~저장해줘”, “~삭제해줘” 꼬리문구 제거 |
| **parse_korean_phone** | `/save_member`, `/update_member` | 한국식 휴대폰 번호 인식/정제 |
| **parse_member_number** | `/save_member`, `/update_member` | 숫자만 있으면 회원번호로 판별 |
| **infer_field_from_value** | `/update_member` | 값이 어떤 필드(주소, 번호, 계보도 등)인지 추론 |

---

## 2. 회원(Member) 흐름도

flowchart TD
    A[사용자 요청] --> B[guess_intent]

    %% 회원 등록
    B -->|회원 등록| C1[parse_registration]
    C1 --> C2[save_member / register_member → DB 시트 저장]

    %% 회원 수정
    B -->|회원 수정| D1[parse_request_and_update]
    D1 --> D2[update_member → DB 시트 갱신]

    %% 회원 삭제
    B -->|회원 삭제| E1[parse_deletion_request]
    E1 --> E2[delete_member_field_nl → DB 시트 수정]

    %% 회원 검색
    B -->|회원 검색| F1[parse_natural_query]
    F1 --> F2[members/search-nl → DB 시트 조회]
    F2 --> F3[remove_josa → 출력 포맷팅]

flowchart TD
    A[사용자 요청] --> B[guess_intent]

    %% 주문 저장
    B -->|자연어 주문| G1[parse_order_text_rule]
    G1 --> G2[parse_and_save_order → 제품주문 시트 저장]

    %% 주문 업로드 (이미지)
    B -->|iPad/PC 업로드| H1[extract_order_from_uploaded_image]
    H1 --> H2[upload_order_ipad / upload_order_pc → addOrders → 제품주문 시트 저장]

    %% 주문 조회
    B -->|주문 조회| I1[find_order]
    I1 --> I2[find_order_route → 제품주문 시트 검색]

    %% 주문 수정/삭제
    B -->|주문 수정| J1[update_order]
    B -->|주문 삭제| J2[delete_order]

    
flowchart TD
    A[사용자 요청] --> B[guess_intent]

    %% 메모 저장
    B -->|상담/개인/활동 저장| K1[parse_counseling / parse_personal / parse_activity]
    K1 --> K2[add_counseling → 해당 시트 저장]

    %% 메모 검색
    B -->|검색| L1[parse_request_line]
    L1 --> L2[search_memo / search_memo_from_text → 시트 조회]

    

flowchart TD
    A[사용자 요청] --> B[guess_intent]

    %% 후원수당 등록
    B -->|등록| M1[parse_commission_text]
    M1 --> M2[register_commission → 후원수당 시트 저장]

    %% 후원수당 수정
    B -->|수정| N1[parse_commission_text]
    N1 --> N2[update_commission → 후원수당 시트 갱신]

    %% 후원수당 조회
    B -->|조회| O1[find_commission]
    O1 --> O2[find_commission_route → 후원수당 시트 검색]



### 2-1. 회원(Member)
flowchart TD
    A[사용자 요청] --> B[guess_intent]

    B -->|회원 등록| C1[parse_registration]
    C1 --> C2[/save_member, /register_member → DB 저장]

    B -->|회원 수정| D1[parse_request_and_update]
    D1 --> D2[/update_member → DB 수정]

    B -->|회원 삭제| E1[parse_deletion_request]
    E1 --> E2[/delete_member_field_nl → DB 수정]

    B -->|회원 검색| F1[parse_natural_query]
    F1 --> F2[/members/search-nl → DB 조회]
  


### 2-2. 주문(Order)
flowchart TD
    A[사용자 요청] --> B[guess_intent]

    B -->|자연어 주문| G1[parse_order_text_rule]
    G1 --> G2[/parse_and_save_order → 제품주문 시트 저장]

    B -->|이미지 업로드| H1[extract_order_from_uploaded_image]
    H1 --> H2[/upload_order_ipad, /upload_order_pc → addOrders → 시트 저장]

    B -->|주문 조회| I1[/find_order]

    B -->|주문 수정| J1[/update_order]
    B -->|주문 삭제| J2[/delete_order, /delete_order_request, /delete_order_confirm]



2-3. 메모(Memo)
flowchart TD
    A[사용자 요청] --> B[guess_intent]

    B -->|저장| K1[parse_counseling / parse_personal / parse_activity]
    K1 --> K2[/add_counseling → 시트 저장]

    B -->|검색| L1[parse_request_line]
    L1 --> L2[/search_memo, /search_memo_from_text → 시트 조회]

    B -->|조회| M1[/find_memo]
    B -->|저장(JSON)| M2[/save_memo]
    


2-4. 후원수당(Commission)
flowchart TD
    A[사용자 요청] --> B[guess_intent]

    B -->|등록| N1[parse_commission_text]
    N1 --> N2[/register_commission → 후원수당 시트 저장]

    B -->|수정| O1[parse_commission_text]
    O1 --> O2[/update_commission → 후원수당 시트 수정]

    B -->|조회| P1[/find_commission]


    
## 포함될 주요 범위
- **회원(Member)**
  - `/save_member`
  - `/register_member`
  - `/update_member`, `/updateMember`
  - `/delete_member`
  - `/delete_member_field_nl`
  - `/find_member`
  - `/members/search-nl`

- **주문(Order)**
  - `/upload_order_ipad`, `/upload_order_pc`, `/upload_order`
  - `/upload_order_text`
  - `/add_orders`
  - `/save_order_from_json`
  - `/saveOrder`, `/save_Order`
  - `/parse_and_save_order`
  - `/find_order`
  - `/register_order`
  - `/update_order`
  - `/delete_order`
  - `/delete_order_request`
  - `/delete_order_confirm`

- **메모(Memo)**
  - `/add_counseling`
  - `/search_memo`
  - `/search_memo_from_text`
  - `/find_memo`
  - `/save_memo`

- **후원수당(Commission)**
  - `/find_commission`
  - `/update_commission`
  - `/register_commission`


  

1. 회원(Member) 

🔹 /register_member

입력 예시

{ "회원명": "홍길동", "회원번호": "12345", "휴대폰번호": "010-1111-2222" }


출력 예시

{ "message": "홍길동님이 성공적으로 등록되었습니다." }


🔹 /update_member

설명: 자연어 요청문 기반 회원 수정

입력 예시

{ "요청문": "홍길동 주소 부산 해운대구로 변경" }


출력 예시

{ "message": "홍길동 기존 회원 정보 수정 완료" }

🔹 /delete_member

설명: 회원 전체 삭제

입력 예시

{ "회원명": "이판주" }


출력 예시

{ "message": "이판주 회원 삭제 완료" }

🔹 /delete_member_field_nl

설명: 자연어로 특정 필드만 삭제

입력 예시

{ "요청문": "이판여 휴대폰번호 삭제" }


출력 예시

{ "message": "이판여 회원의 휴대폰번호 필드가 삭제되었습니다." }

🔹 /find_member

입력 예시

{ "회원명": "신금자" }


출력 예시

{ "회원명": "신금자", "회원번호": "41474404", "계보도": "장천수 우측" }

🔹 /members/search-nl

입력 예시

{ "query": "계보도 장천수 우측" }


출력 예시

장미 (회원번호: 41474404, 연락처: 010-1234-5678)
신금자 (회원번호: 88889999, 연락처: 010-2222-3333)
--- 다음 있음 ---






2. 주문(Order)

🔹 /upload_order_ipad

입력 예시: multipart/form-data

회원명=이태수
message=이태수 제품주문 저장
image=order.jpg


출력 예시

{
  "status": "success",
  "추출된_JSON": [
    { "제품명": "홍삼", "제품가격": "50000", "PV": "10", "주문자_고객명": "홍길동", "배송처": "서울" }
  ]
}

🔹 /upload_order_text

입력 예시

{ "message": "김지연 노니 2개 카드 주문 저장" }


출력 예시

{
  "status": "success",
  "회원명": "김지연",
  "추출된_JSON": [
    { "제품명": "노니", "수량": 2, "결제방법": "카드" }
  ]
}

🔹 /find_order

입력 예시

{ "회원명": "김상민", "제품명": "헤모힘" }


출력 예시

{ "회원명": "김상민", "제품명": "헤모힘", "제품가격": "150000", "PV": "20" }

🔹 /delete_order_request

출력 예시

{
  "message": "📌 최근 주문 내역 3건입니다. 삭제할 번호(1~3)를 선택해 주세요.",
  "주문목록": [
    { "번호(행번호)": "1 (행:2)", "회원명": "홍길동", "제품명": "홍삼", "가격": "50000" },
    { "번호(행번호)": "2 (행:3)", "회원명": "김지연", "제품명": "노니", "가격": "40000" }
  ]
}

🔹 /delete_order_confirm

입력 예시

{ "삭제번호": "1,2" }


출력 예시

{ "message": "✅ 1, 2번 주문이 삭제되었습니다." }






3. 메모(Memo)

🔹 /add_counseling

입력 예시

{ "요청문": "김기범 상담일지 저장 헤모힘 24박스를 택배 발송함." }


출력 예시

{ "message": "김기범님의 상담일지 저장 완료" }

🔹 /search_memo

입력 예시

{
  "keywords": ["중국", "공항"],
  "mode": "전체",
  "search_mode": "동시검색",
  "limit": 10
}


출력 예시

{
  "status": "success",
  "results": {
    "개인": [ { "날짜": "2025-08-27", "회원명": "이태수", "내용": "자동차 엔진오일 교환" } ],
    "상담": [],
    "활동": []
  }
}






4. 후원수당(Commission)

🔹 /find_commission

입력 예시

{ "회원명": "홍길동" }


출력 예시

{
  "회원명": "홍길동",
  "기준일자": "2025-08-29",
  "합계_좌": 200000,
  "합계_우": 150000
}

🔹 /register_commission

입력 예시

{ "회원명": "홍길동", "후원수당": "100000", "비고": "월간 정산", "지급일자": "2025-08-29" }


출력 예시

{ "message": "홍길동님의 후원수당 100000원이 등록되었습니다." }





5. Flowchart 요약

flowchart TD

    subgraph 회원
    A1[save_member] --> DB
    A2[update_member] --> DB
    A3[delete_member] --> DB
    A4[find_member] --> DB
    end

    subgraph 주문
    B1[upload_order_ipad/pc] --> Sheet
    B2[upload_order_text] --> API
    B3[find_order] --> Sheet
    B4[delete_order] --> Sheet
    end

    subgraph 메모
    C1[add_counseling] --> Sheet
    C2[search_memo] --> Sheet
    C3[save_memo] --> Sheet
    end

    subgraph 후원수당
    D1[find_commission] --> Sheet
    D2[register_commission] --> Sheet
    end



3. 라우트별 Request / Response 예시

🔹 /save_member

입력

{ "요청문": "홍길동 회원번호 12345 휴대폰 010-1111-2222 주소 서울" }


출력

{ "message": "홍길동 회원 신규 등록 완료" }

🔹 /update_member

입력

{ "요청문": "홍길동 주소 부산으로 변경" }


출력

{ "message": "홍길동 기존 회원 정보 수정 완료" }

🔹 /delete_member_field_nl

입력

{ "요청문": "홍길동 휴대폰번호 삭제" }


출력

{ "message": "홍길동님의 휴대폰번호가 삭제되었습니다." }

🔹 /find_member

입력

{ "회원명": "홍길동" }


출력

{ "회원명": "홍길동", "회원번호": "12345", "휴대폰번호": "010-1111-2222" }

🔹 /members/search-nl

입력

{ "query": "계보도가 장천수 우측인 회원" }


출력 (text/plain)

홍길동 (회원번호: 12345, 연락처: 010-1111-2222)
장미 (회원번호: 67890, 연락처: 010-3333-4444)

🔹 /upload_order_ipad

입력 (form-data)

회원명=홍길동
image=@order.jpg


출력

{ "status": "success", "message": "홍길동님의 주문이 저장되었습니다." }

🔹 /upload_order_text

입력

{ "message": "홍길동 노니 2개 카드 주문 저장" }


출력

{
  "status": "success",
  "회원명": "홍길동",
  "추출된_JSON": [
    { "제품명": "노니", "수량": 2, "결재방법": "카드" }
  ]
}

🔹 /delete_order_request

입력

{}


출력

{
  "message": "📌 최근 주문 내역 5건입니다. 삭제할 번호를 선택해 주세요.",
  "주문목록": [
    { "번호(행번호)": "1 (행:2)", "회원명": "홍길동", "제품명": "노니", "가격": "50000" }
  ]
}

🔹 /delete_order_confirm

입력

{ "삭제번호": "1,3" }


출력

{
  "message": "✅ 1, 3번 주문(행번호: 2,4)이 삭제되었습니다.",
  "삭제된_번호": [1,3],
  "삭제된_행번호": [2,4]
}

🔹 /add_counseling

입력

{ "요청문": "홍길동 상담일지 오늘 제품설명 진행" }


출력

{ "message": "홍길동님의 상담일지 저장 완료" }

🔹 /search_memo

입력

{ "keywords": ["제품", "설명"], "mode": "상담" }


출력

{
  "status": "success",
  "results": {
    "상담": [
      { "날짜": "2025-08-29", "회원명": "홍길동", "내용": "오늘 제품설명 진행" }
    ]
  }
}

🔹 /find_commission

입력

{ "회원명": "홍길동" }


출력

[
  { "회원명": "홍길동", "기준일자": "2025-08-01", "후원수당": "120000" }
]

🔹 /register_commission

입력

{ "회원명": "홍길동", "후원수당": "100000", "비고": "8월분", "지급일자": "2025-08-30" }


출력

{ "message": "홍길동님의 후원수당 100000원이 등록되었습니다." }


