import subprocess
import sys
import os

# 저장소 주소 정의
MAIN_REPO = "git@github-boraminfo:boraminfo/members_list_boram.git"
BACKUP_REPO = "git@github-boraminfo:boraminfo/memberslist.git"

def run_git_command(cmd, env=None):
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        print("⚠️ 명령 실행 실패")
        sys.exit(result.returncode)

def main():
    # ✅ SSH config 자동 적용
    ssh_config_path = "C:/ChatGPT/members_list_boram/set_git_user/ssh_config"
    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = f'ssh -F "{ssh_config_path}"'

    print("\n🔄 기존 원격(remote) 초기화 중...")
    # 모든 remote 제거 (있을 때만)
    for name in ["origin", "backup"]:
        try:
            run_git_command(["git", "remote", "remove", name], env=env)
        except SystemExit:
            # 없는 경우는 무시
            pass

    print("\n📤 등록할 원격 저장소를 선택하세요:")
    print("[1] 백업 저장소 (memberslist.git)   → backup 으로 등록")
    print("[2] 메인 저장소 (members_list_boram.git) → origin 으로 등록")
    print("==============================")
    choice = input("번호를 입력하세요 (1~2): ").strip()

    if choice == "1":
        remote_name = "backup"
        remote_url = BACKUP_REPO
    elif choice == "2":
        remote_name = "origin"
        remote_url = MAIN_REPO
    else:
        print("❌ 잘못된 선택")
        sys.exit(1)

    # ✅ 선택한 원격 등록
    run_git_command(["git", "remote", "add", remote_name, remote_url], env=env)

    # 등록 확인
    print("\n✅ 원격(remote) 등록 완료:")
    run_git_command(["git", "remote", "-v"], env=env)

if __name__ == "__main__":
    main()
