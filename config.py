import os
from urllib.parse import urljoin
from openai import OpenAI

# ✅ 환경 변수 로드
if os.getenv("RENDER") is None:  # 로컬에서 실행 중일 때만
    from dotenv import load_dotenv
    dotenv_path = os.path.abspath('.env')
    if not os.path.exists(dotenv_path):
        raise FileNotFoundError(f".env 파일이 존재하지 않습니다: {dotenv_path}")
    load_dotenv(dotenv_path)

# --------------------------------------------------
# 필수 환경 변수
# --------------------------------------------------
API_BASE = os.getenv("API_BASE", "http://localhost:5000")
GOOGLE_SHEET_TITLE = os.getenv("GOOGLE_SHEET_TITLE")
SHEET_KEY = os.getenv("GOOGLE_SHEET_KEY")

# --------------------------------------------------
# OpenAI 관련
# --------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL")
PROMPT_ID = os.getenv("PROMPT_ID")
PROMPT_VERSION = os.getenv("PROMPT_VERSION")

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
    "member_update": urljoin(API_BASE, "/update_Member"),
    "member_update_legacy": urljoin(API_BASE, "/updateMember"),
    "order": urljoin(API_BASE, "/save_order"),
    "commission": urljoin(API_BASE, "/save_commission"),
}


SHEET_MAP = {
    "개인": "개인일지",
    "상담": "상담일지",
    "활동": "활동일지",
}




DT_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]

