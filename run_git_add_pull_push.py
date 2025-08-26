import subprocess
import sys
import os
from datetime import datetime

# SSH config 고정 경로
SSH_CONFIG_PATH = "C:/ChatGPT/ssh_config"

def run_git_command(cmd, env=None, allow_fail=False, capture_output=False):
    """Git 명령 실행 래퍼"""
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env, capture_output=capture_output, text=True)
    if result.returncode != 0 and not allow_fail:
        print("❌ 명령 실행 실패")
        sys.exit(result.returncode)
    return result

def get_current_branch(env):
    """현재 브랜치 자동 감지"""
    result = run_git_command(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        env=env, capture_output=True
    )
    return result.stdout.strip() if result.stdout else "main"

def git_pull_commit_push():
    print("\n📥 git pull & push 실행")

    # ✅ SSH config 무조건 적용
    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = f'ssh -F "{SSH_CONFIG_PATH}"'
    print(f"🔑 SSH 설정 파일 사용: {SSH_CONFIG_PATH}")

    # ✅ 현재 브랜치 확인
    branch = get_current_branch(env)
    print(f"📌 현재 브랜치: {branch}")

    # ✅ git pull
    run_git_command(["git", "pull", "origin", branch], env=env, allow_fail=True)

    # ✅ 변경 사항 확인
    result = run_git_command(["git", "status", "--porcelain"], env=env, capture_output=True)
    if not result.stdout.strip():
        print("✅ 변경사항 없음. push 생략.")
        return

    # ✅ git add .
    run_git_command(["git", "add", "."], env=env)

    # ✅ 커밋 메시지 입력 (기본값 제공)
    commit_msg = input("💬 커밋 메시지를 입력하세요 (비우면 자동 메시지 사용): ").strip()
    if not commit_msg:
        commit_msg = f"자동 커밋 {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    run_git_command(["git", "commit", "-m", commit_msg], env=env, allow_fail=True)

    # ✅ git push (origin, 현재 브랜치, 강제 옵션 X)
    run_git_command(["git", "push", "origin", branch], env=env)
    print(f"\n🚀 origin → 브랜치 '{branch}' push 완료!")

def main():
    git_pull_commit_push()

if __name__ == "__main__":
    main()
