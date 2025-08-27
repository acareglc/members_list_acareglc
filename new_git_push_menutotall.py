import subprocess
import sys
import os
from datetime import datetime

# 저장소 주소 정의
MAIN_REPO = "git@github-boraminfo:boraminfo/members_list_boram.git"
BACKUP_REPO = "git@github-boraminfo:boraminfo/memberslist.git"
EHLHAPPYDAY_REPO = "git@github-acareglc:acareglc/members_list_acareglc.git"
SOHEE_REPO = "git@github-iamsohappy0418:iamsohappy0418/members_list_iamsohappy0418.git"

# SSH config 경로 고정
SSH_CONFIG_PATH = r"C:/ChatGPT/ssh_config"

def run_git_command(cmd, env=None, capture_output=False, allow_fail=False):
    """Git 명령 실행 래퍼"""
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env, capture_output=capture_output, text=True)
    if result.returncode != 0:
        if allow_fail:
            print("⚠️ 명령 실행 실패 (무시)")
            return result
        print("❌ 명령 실행 실패")
        sys.exit(result.returncode)
    return result

def get_current_branch(env):
    """현재 브랜치 자동 감지"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            env=env, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "main"

def main():
    print(f"\n🔑 SSH 설정 파일 사용: {SSH_CONFIG_PATH}")

    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = f'ssh -F "{SSH_CONFIG_PATH}"'

    # ✅ push할 저장소 선택
    print("\n📤 push할 저장소를 선택하세요:")
    print("[1] 메인 저장소 (members_list_boram.git)")
    print("[2] 백업 저장소 (memberslist.git)")
    print("[3] acareglc 저장소 (members_list_acareglc.git)")
    print("[4] sohee 저장소 (members_list_iamsohappy0418.git)")
    choice = input("번호를 입력하세요 (1~4): ").strip()

    if choice == "1":
        remote_url = MAIN_REPO
    elif choice == "2":
        remote_url = BACKUP_REPO
    elif choice == "3":
        remote_url = EHLHAPPYDAY_REPO
    elif choice == "4":
        remote_url = SOHEE_REPO
    else:
        print("❌ 잘못된 선택")
        sys.exit(1)

    # ✅ 항상 origin만 유지
    subprocess.run(["git", "remote", "remove", "origin"], env=env, check=False)
    run_git_command(["git", "remote", "add", "origin", remote_url], env=env)

    print(f"\n✅ origin 원격이 {remote_url} 에 성공적으로 연결되었습니다!")
    run_git_command(["git", "remote", "-v"], env=env)

    # ✅ 상태 확인
    run_git_command(["git", "status"], env=env)

    # ✅ 커밋 메시지 입력 (기본값 제공)
    commit_msg = input("\n💬 커밋 메시지를 입력하세요 (비우면 자동 메시지 사용): ").strip()
    if not commit_msg:
        commit_msg = f"자동 커밋 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        print(f"ℹ️ 기본 커밋 메시지 사용: {commit_msg}")

    run_git_command(["git", "add", "."], env=env)
    run_git_command(["git", "commit", "-m", commit_msg], env=env, allow_fail=True)

    # ✅ 현재 브랜치 자동 감지
    branch = get_current_branch(env)
    print(f"\n📌 현재 브랜치: {branch}")

    # ✅ pull --rebase & push --force
    print("\n📥 pull --rebase 실행 중...")
    result = subprocess.run(["git", "pull", "--rebase", "origin", branch], env=env)
    if result.returncode != 0:
        print("⚠️ pull --rebase 과정에서 충돌이 발생했습니다. 수동으로 해결 후 다시 실행하세요.")
        return

    run_git_command(["git", "push", "origin", branch, "--force"], env=env)
    print(f"\n🚀 origin ({remote_url}) → 브랜치 '{branch}' 강제 push 완료!")

if __name__ == "__main__":
    main()
