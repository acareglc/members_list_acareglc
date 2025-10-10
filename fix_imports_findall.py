import pathlib
import subprocess
import re


# 정확히 교체할 대상 (import 구문 전체 문자열 기준)

OLD = r"비밀번호"


# NEW = r"query_multi"

def fix_imports(dry_run=True):
    self_file = pathlib.Path(__file__).name  # 자기 자신 제외
    modified = False

    for file in pathlib.Path(".").rglob("*.py"):
        if file.name == self_file:
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        if re.search(OLD, text):
            print(f"🔎 Found in: {file}")
            if not dry_run:
                new_text = re.sub(OLD, NEW, text)
                file.write_text(new_text, encoding="utf-8")
                print(f"✅ Updated: {file}")
                modified = True

    if modified and not dry_run:
        print("\n📌 Running git diff ...\n")
        subprocess.run(["git", "diff"])
    elif not modified:
        print("ℹ️ No matching imports found.")

if __name__ == "__main__":
    # dry_run=True → 찾기만
    # dry_run=False → 실제 교체 + git diff
    fix_imports(dry_run=True)






