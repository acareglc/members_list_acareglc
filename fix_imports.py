import pathlib
import subprocess

# 문자열을 조각으로 나눠서 정의 (자기 자신 탐지 방지)
TARGET = "from utils." + "clean_content import clean_content"
REPLACEMENT = "from utils import clean_content"

def fix_imports(dry_run=True):
    for file in pathlib.Path(".").rglob("*.py"):
        try:
            text = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"⚠️ Skipping (decode error): {file}")
            continue

        if TARGET in text:
            print(f"🔎 Found in: {file}")
            if not dry_run:
                new_text = text.replace(TARGET, REPLACEMENT)
                file.write_text(new_text, encoding="utf-8")
                print(f"✅ Updated: {file}")

    if not dry_run:
        print("\n📌 Running git diff ...\n")
        subprocess.run(["git", "diff"])

if __name__ == "__main__":
    fix_imports(dry_run=True)
    # 👉 실제 수정하려면 아래 주석 해제
    # fix_imports(dry_run=False)
