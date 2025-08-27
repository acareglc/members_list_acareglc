import os
import subprocess
from pathlib import Path
import sys

def select_user():
    print("\n==============================")
    print("🔐 Git 사용자 계정을 선택하세요:")
    print("[1] members_list_boram")
    print("[2] memberslist")
    print("[3] acareglc")
    print("[4] iamsohappy0418")
    print("==============================")
    choice = input("번호를 입력하세요 (1~4): ").strip()

    users = {
        "1": {
            "name": "boraminfo",
            "email": "boraminfo@gmail.com",
            "remote": "git@github-boraminfo:boraminfo/members_list_boram.git"
        },
        "2": {
            "name": "boraminfo",
            "email": "boraminfo@gmail.com",
            "remote": "git@github-boraminfo:boraminfo/memberslist.git"
        },
        "3": {
            "name": "acareglc",
            "email": "acareglc@gmail.com",
            "remote": "git@github-acareglc:acareglc/members_list_acareglc.git"
        },
        "4": {
            "name": "iamsohappy0418",
            "email": "iamsohappy0418@gmail.com",
            "remote": "git@github-iamsohappy0418:iamsohappy0418/members_list_iamsohappy0418.git"
        }
    }

    user = users.get(choice)
    if not user:
        print("❌ 잘못된 입력입니다.")
        sys.exit(1)
    return user

def reset_and_set_remote(user):
    """등록된 모든 remote 삭제 후 origin만 새로 추가"""
    # 현재 remote 목록 가져오기
    result = subprocess.run(["git", "remote"], capture_output=True, text=True)
    remotes = result.stdout.split()

    # 기존 remote 모두 삭제
    for r in remotes:
        if r.strip():
            subprocess.run(["git", "remote", "remove", r], check=False)
            print(f"🗑️ remote '{r}' 삭제")

    # 새로운 origin 추가
    subprocess.run(["git", "remote", "add", "origin", user["remote"]], check=False)
    print(f"🔗 remote 'origin' 추가: {user['remote']}")

def main():
    user = select_user()

    # ✅ SSH config 경로 지정 (set_git_user/ssh_config)
    ssh_config_path = Path(__file__).parent / "ssh_config"
    os.environ["GIT_SSH_COMMAND"] = f'ssh -F "{ssh_config_path}"'

    # ✅ Git 사용자 정보 설정
    subprocess.run(["git", "config", "--local", "user.name", user["name"]], check=False)
    subprocess.run(["git", "config", "--local", "user.email", user["email"]], check=False)

    # ✅ 모든 remote 삭제 후 origin 등록
    reset_and_set_remote(user)

    # ✅ 출력
    print("\n✅ 설정 완료:")
    print(f"✔️ user.name:      {user['name']}")
    print(f"✔️ user.email:     {user['email']}")
    print(f"✔️ origin:         {user['remote']}")
    print(f"✔️ SSH config 사용: {ssh_config_path}")

    # 현재 remote 목록 확인
    print("\n📌 현재 등록된 git remote 목록:")
    subprocess.run(["git", "remote", "-v"])

if __name__ == "__main__":
    main()
