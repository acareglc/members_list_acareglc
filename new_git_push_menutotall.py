import subprocess
import sys
import os

# 저장소 주소 정의
MAIN_REPO = "git@github-boraminfo:boraminfo/members_list_boram.git"
BACKUP_REPO = "git@github-boraminfo:boraminfo/memberslist.git"
EHLHAPPYDAY_REPO = "git@github-acareglc:acareglc/members_list_acareglc.git"
SOHEE_REPO = "git@github-iamsohappy0418:iamsohappy0418/members_list_iamsohappy0418.git"

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

def clear_all_remotes(env):
    """등록된 모든 remote 삭제"""
    result = subprocess.run(["git", "remote"], env=env, capture_output=True, text=True)
    remotes = result.stdout.strip().splitlines()
    for r in remotes:
        if r.strip():
            subprocess.run(["git", "remote", "remove", r.strip()], env=env)

def main():
    # ✅ ssh_config 생성
    print("\n🛠 ssh_config 자동 생성 중...")
    subprocess.run([sys.executable, "generate_ssh_config.py"], check=True)
    print("✅ SSH 설정 파일 생성 완료 → C:\\ChatGPT\\members_list_boram\\set_git_user\\ssh_config")

    # ✅ 프로젝트 선택
    print("\n📂 어떤 프로젝트에서 실행하시겠습니까?")
    print("[1] members_list_boram")
    print("[2] memberslist")
    print("[3] acareglc")
    print("[4] iamsohappy0418")

    proj_choice = input("번호를 입력하세요 (1~4): ").strip()

    if proj_choice == "1":
        ssh_config_path = r"C:/ChatGPT/members_list_boram/set_git_user/ssh_config"
        remote_name, remote_url = "origin", MAIN_REPO
    elif proj_choice == "2":
        ssh_config_path = r"C:/ChatGPT/memberslist/set_git_user/ssh_config"
        remote_name, remote_url = "backup", BACKUP_REPO
    elif proj_choice == "3":
        ssh_config_path = r"C:/ChatGPT/members_list_acareglc/set_git_user/ssh_config"
        remote_name, remote_url = "glc", EHLHAPPYDAY_REPO
    elif proj_choice == "4":
        ssh_config_path = r"C:/ChatGPT/members_list_iamsohappy0418/set_git_user/ssh_config"
        remote_name, remote_url = "sohee", SOHEE_REPO
    else:
        print("❌ 잘못된 선택")
        sys.exit(1)

    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = f'ssh -F "{ssh_config_path}"'

    # ✅ 기존 remote 모두 삭제
    clear_all_remotes(env)

    # ✅ 선택된 프로젝트 기본 remote 등록
    run_git_command(["git", "remote", "add", remote_name, remote_url], env=env)

    print(f"\n✅ '{remote_name}' 원격이 {remote_url} 에 성공적으로 연결되었습니다!")
    print("\n🔗 현재 등록된 원격(remote) 목록:")
    run_git_command(["git", "remote", "-v"], env=env)

    # ✅ push할 저장소 선택
    print("\n📤 push할 저장소를 선택하세요:")
    print("[1] 메인 저장소 (members_list_boram.git) → origin 으로 등록")
    print("[2] 백업 저장소 (memberslist.git)   → backup 으로 등록")
    print("[3] 백업 저장소 (acareglc.git)   → glc 으로 등록")
    print("[4] 백업 저장소 (iamsohappy0418.git)   → sohee 으로 등록")

    choice = input("번호를 입력하세요 (1~4): ").strip()

    if choice == "1":
        remote_name, remote_url = "origin", MAIN_REPO
    elif choice == "2":
        remote_name, remote_url = "backup", BACKUP_REPO
    elif choice == "3":
        remote_name, remote_url = "glc", EHLHAPPYDAY_REPO
    elif choice == "4":
        remote_name, remote_url = "sohee", SOHEE_REPO
    else:
        print("❌ 잘못된 선택")
        sys.exit(1)



    # ✅ 선택된 remote 등록 (중복 제거 후)   ⬅️ 추가/수정 부분
    subprocess.run(["git", "remote", "remove", remote_name], env=env)
    run_git_command(["git", "remote", "add", remote_name, remote_url], env=env)

    print(f"\n✅ '{remote_name}' 원격이 {remote_url} 에 성공적으로 연결되었습니다!")

    # ✅ 바로 상태 확인   ⬅️ 기존 'push 전 상태 확인' → 수정됨
    # ✅ push 전 상태 확인
    run_git_command(["git", "status"], env=env)

    # ✅ 커밋 메시지 입력
    commit_msg = input("\n💬 커밋 메시지를 입력하세요: ").strip()
    if commit_msg:
        run_git_command(["git", "add", "."], env=env)
        run_git_command(["git", "commit", "-m", commit_msg], env=env, allow_fail=True)
    else:
        print("⚠️ 커밋 메시지 없음 → 커밋 건너뜀")

    # ✅ push --force (항상 main 브랜치 고정)
    run_git_command(["git", "push", remote_name, "main", "--force"], env=env)
    print(f"\n🚀 {remote_name} ({remote_url}) 저장소로 강제 push 완료!")

if __name__ == "__main__":
    main()
