import subprocess
import sys
import os

# 저장소 주소 정의
MAIN_REPO = "git@github-boraminfo:boraminfo/members_list_boram.git"
BACKUP_REPO = "git@github-boraminfo:boraminfo/memberslist.git"

# SSH config 고정 경로
SSH_CONFIG_PATH = "C:/ChatGPT/ssh_config"

def run_git_command(cmd, env=None):
    """Git 명령 실행 래퍼"""
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        print("⚠️ 명령 실행 실패")
        sys.exit(result.returncode)
    return result

def main():
    # ✅ SSH config 고정 적용
    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = f'ssh -F "{SSH_CONFIG_PATH}"'
    print(f"\n🔑 SSH 설정 파일 사용: {SSH_CONFIG_PATH}")

    print("\n🔄 기존 원격(remote) 초기화 중...")
    # origin 삭제 (있을 때만)
    subprocess.run(["git", "remote", "remove", "origin"], env=env, check=False)

    # ✅ 등록할 저장소 선택
    print("\n📤 등록할 원격 저장소를 선택하세요:")
    print("[1] 메인 저장소 (members_list_boram.git)")
    print("[2] 백업 저장소 (memberslist.git)")
    print("==============================")
    choice = input("번호를 입력하세요 (1~2): ").strip()

    if choice == "1":
        remote_url = MAIN_REPO
    elif choice == "2":
        remote_url = BACKUP_REPO
    else:
        print("❌ 잘못된 선택")
        sys.exit(1)

    # ✅ 선택한 원격을 항상 origin으로 등록
    run_git_command(["git", "remote", "add", "origin", remote_url], env=env)

    # 등록 확인
    print(f"\n✅ origin 원격이 {remote_url} 에 성공적으로 연결되었습니다!")
    print("\n🔗 현재 등록된 원격(remote) 목록:")
    run_git_command(["git", "remote", "-v"], env=env)

if __name__ == "__main__":
    main()
