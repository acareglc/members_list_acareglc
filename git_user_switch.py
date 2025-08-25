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
            "remote": "git@github-boraminfo:boraminfo/members_list_boram.git",
            "host": "github-boraminfo"
        },
        "2": {
            "name": "ehlhappyday",
            "email": "ehlhappyday@gmail.com",
            "remote": "git@github-ehlhappyday:ehlhappyday/members_list_ehlhappyday.git",
            "host": "github-ehlhappyday"
        },
        "3": {
            "name": "sohee4463",
            "email": "sohee4463@gmail.com",
            "remote": "git@github-sohee4463:sohee4463/members_list_sohee4463.git",
            "host": "github-sohee4463"
        },
        "4": {
            "name": "boraminfo",
            "email": "boraminfo2@gmail.com",
            "remote": "git@github-boraminfo:boraminfo/memberslist.git",
            "host": "github-boraminfo"
        }
    }

    user = users.get(choice)
    if not user:
        print("\033[91m❌ 잘못된 입력입니다.\033[0m")
        exit(1)
    return user

def get_current_branch():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"

def main():
    user = select_user()

    # ✅ SSH config 경로 지정
    ssh_config_path = Path(__file__).parent / "set_git_user" / "ssh_config"
    os.environ["GIT_SSH_COMMAND"] = f'ssh -F "{ssh_config_path}"'

    # ✅ Git 사용자 정보 설정
    subprocess.run(["git", "config", "--local", "user.name", user["name"]])
    subprocess.run(["git", "config", "--local", "user.email", user["email"]])

    # ✅ 리모트 주소 변경
    subprocess.run(["git", "remote", "set-url", "origin", user["remote"]])

    # ✅ 현재 브랜치
    branch = get_current_branch()

    # ✅ 출력
    print("\n✅ 설정 완료:")
    print(f"✔️ user.name:      {user['name']}")
    print(f"✔️ user.email:     {user['email']}")
    print(f"✔️ origin:         {user['remote']}")
    print(f"✔️ branch:         {branch}")
    print(f"✔️ SSH config 사용: {ssh_config_path}")

    # ✅ GitHub 연결 테스트 (자동 yes)
    print("\n🌐 GitHub 연결 테스트 중...")
    try:
        result = subprocess.run(
            f'echo y | ssh -F "{ssh_config_path}" -T {user["host"]}',
            shell=True, capture_output=True, text=True
        )
        output = (result.stdout + result.stderr).strip()

        if "successfully authenticated" in output.lower():
            print(f"\033[92m✔️ [{user['name']} / {user['email']} / {user['remote']} / branch:{branch}] 연결 성공:\033[0m {output}")
        else:
            print(f"\033[91m❌ [{user['name']} / {user['email']} / {user['remote']} / branch:{branch}] 연결 실패:\033[0m {output}")
    except Exception as e:
        print(f"\033[91m❌ [{user['name']} / {user['email']} / {user['remote']} / branch:{branch}] SSH 테스트 실행 오류:\033[0m {e}")

if __name__ == "__main__":
    main()


