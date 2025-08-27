import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

# ✅ SSH config 고정 경로
SSH_CONFIG_PATH = Path(r"C:/ChatGPT/ssh_config")

def git_pull_push():
    print("\n📥 git pull 실행 중...")

    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = f'ssh -F "{SSH_CONFIG_PATH}"'
    branch = "main"

    # git pull
    subprocess.run(["git", "pull", "origin", branch], env=env)

    # 변경 감지
    result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, env=env)
    if not result.stdout.strip():
        print("✅ 변경사항 없음. push 생략.")
        return

    # git add .
    subprocess.run(["git", "add", "."], env=env)

    # 변경된 파일 목록 보여주기
    print("\n📌 변경된 파일 목록:")
    diff_result = subprocess.run(["git", "diff", "--cached", "--name-status"], capture_output=True, text=True, env=env)
    print(diff_result.stdout.strip() or "(변경 없음)")

    # 커밋 메시지 입력
    commit_msg = input("\n💬 커밋 메시지를 입력하세요 (비우면 자동 메시지 사용): ").strip()
    if not commit_msg:
        commit_msg = f"자동 커밋 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        print(f"ℹ️ 기본 커밋 메시지 사용: {commit_msg}")

    # commit
    subprocess.run(["git", "commit", "-m", commit_msg], env=env)

    # ✅ push (force 허용)
    subprocess.run(["git", "push", "origin", branch, "--force"], env=env)

    print(f"\n✅ Git push 완료 (강제) → origin/{branch}")

def main():
    # set_git_user.py 호출 제거
    git_pull_push()

if __name__ == "__main__":
    main()
