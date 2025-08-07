import subprocess
import sys
from pathlib import Path
import os

def git_pull_push():
    print("\n📥 git pull 실행 중...")

    # ✅ ssh_config 위치: ./set_git_user/ssh_config
    ssh_config_path = Path(__file__).parent / "set_git_user" / "ssh_config"
    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = f'ssh -F "{ssh_config_path.as_posix()}"'

    # git pull
    subprocess.run(["git", "pull", "origin", "main"], env=env)

    # 변경 감지
    result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if not result.stdout.strip():
        print("✅ 변경사항 없음. push 생략.")
        return


    # 변경사항 출력
    print("\n🔍 변경사항 요약 (git status):")
    subprocess.run(["git", "status"], env=env)

 
    # git add .
    subprocess.run(["git", "add", "."], env=env)

    # 커밋 메시지 입력
    commit_msg = input("💬 커밋 메시지를 입력하세요: ").strip()
    if not commit_msg:
        print("❌ 커밋 메시지가 비어 있어 작업을 취소합니다.")
        return

    # commit & push
    subprocess.run(["git", "commit", "-m", commit_msg], env=env)
    subprocess.run(["git", "push", "origin", "main"], env=env)

    print("✅ Push 완료!")

def main():
    git_pull_push()

if __name__ == "__main__":
    main()


