import os
import subprocess
from pathlib import Path

def select_user():
    print("\n==============================")
    print("🔐 Git 사용자 계정을 선택하세요:")
    print("[1] members_list_boram")
    print("[2] ehlhappyday")
    print("[3] sohee4463")
    print("[4] memberslist")
    print("==============================")
    choice = input("번호를 입력하세요 (1~4): ").strip()

    users = {
        "1": {
            "name": "boraminfo",
            "email": "boraminfo@gmail.com",
            "remote": "git@github-boraminfo:boraminfo/members_list_boram.git"
        },
        "2": {
            "name": "ehlhappyday",
            "email": "ehlhappyday@gmail.com",
            "remote": "git@github-ehlhappyday:ehlhappyday/members_list_ehlhappyday.git"
        },
        "3": {
            "name": "sohee4463",
            "email": "sohee4463@gmail.com",
            "remote": "git@github-sohee4463:sohee4463/members_list_sohee4463.git"
        },
        "4": {
            "name": "boraminfo",
            "email": "boraminfo2@gmail.com",
            "remote": "git@github-boraminfo:boraminfo/memberslist.git"
        }
    }

    user = users.get(choice)
    if not user:
        print("❌ 잘못된 입력입니다.")
        exit(1)
    return user

def main():
    user = select_user()

    # ✅ SSH config 경로 지정 (set_git_user/ssh_config)
    ssh_config_path = Path(__file__).parent / "ssh_config"
    os.environ["GIT_SSH_COMMAND"] = f'ssh -F "{ssh_config_path}"'

    # ✅ Git 사용자 정보 설정
    subprocess.run(["git", "config", "--local", "user.name", user["name"]])
    subprocess.run(["git", "config", "--local", "user.email", user["email"]])

    # ✅ 리모트 주소 변경
    subprocess.run(["git", "remote", "set-url", "origin", user["remote"]])

    # ✅ 출력
    print("\n✅ 설정 완료:")
    print(f"✔️ user.name:      {user['name']}")
    print(f"✔️ user.email:     {user['email']}")
    print(f"✔️ origin:         {user['remote']}")
    print(f"✔️ SSH config 사용: {ssh_config_path}")

if __name__ == "__main__":
    main()
