import subprocess
import sys
import os
from datetime import datetime

# SSH config 고정 경로
SSH_CONFIG_PATH = "C:/ChatGPT/ssh_config"

def run_set_git_user():
    """Git 사용자 설정 스크립트 실행"""
    print("\n🔧 Git 사용자 설정 중...")
    subprocess.run([sys.executable, "set_git_user/set_git_user.py"], check=True)

def get_current_branch(env):
    """현재 브랜치 자동 감지"""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        env=env, capture_output=True, text=True
    )
    branch = result.stdout.strip()
    return branch if branch else "main"

def git_pull_push():
    print("\n📥 git pull & push 실행")

    # ✅ SSH config 고정 적용
    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = f'ssh -F "{SSH_CONFIG_PATH}"'
    print(f"🔑 SSH 설정 파일 사용: {SSH_CONFIG_PATH}")

    # ✅ 현재 브랜치 자동 감지
    branch = get_current_branch(env)
    print(f"📌 현재 브랜치: {branch}")

    # ✅ git pull
    subprocess.run(["git", "pull", "origin", branch], env=env)

    # ✅ 변경 감지
    result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, env=env)
    if not result.stdout.strip():
        print("✅ 변경사항 없음. push 생략.")
        return

    # ✅ git add .
    subprocess.run(["git", "add", "."], env=env)

    # ✅ 커밋 메시지 입력 (기본값 제공)
    commit_msg = input("💬 커밋 메시지를 입력하세요 (비우면 자동 메시지 사용): ").strip()
    if not commit_msg:
        commit_msg = f"자동 커밋 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        print(f"ℹ️ 기본 커밋 메시지 사용: {commit_msg}")

    # ✅ commit
    subprocess.run(["git", "commit", "-m", commit_msg], env=env)

    # ✅ push (항상 origin)
    subprocess.run(["git", "push", "origin", branch], env=env)

    print(f"\n🚀 origin → 브랜치 '{branch}' push 완료!")

def main():
    run_set_git_user()
    git_pull_push()

if __name__ == "__main__":
    main()
