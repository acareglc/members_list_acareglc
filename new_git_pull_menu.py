import os
import subprocess
from pathlib import Path

USERS = {
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

def select_user():
    print("\n==============================")
    print("🔐 Git 사용자 계정을 선택하세요:")
    for k, v in USERS.items():
        print(f"[{k}] {v['name']} ({v['email']})")
    print("==============================")
    choice = input("번호를 입력하세요 (1~4): ").strip()
    return USERS.get(choice)

def get_current_branch():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"

def setup_git(user):
    ssh_config_path = Path(__file__).parent / "set_git_user" / "ssh_config"
    os.environ["GIT_SSH_COMMAND"] = f'ssh -F "{ssh_config_path}"'

    subprocess.run(["git", "config", "--local", "user.name", user["name"]])
    subprocess.run(["git", "config", "--local", "user.email", user["email"]])
    subprocess.run(["git", "remote", "set-url", "origin", user["remote"]])

    branch = get_current_branch()

    print("\n✅ 설정 완료:")
    print(f"✔️ user.name:      {user['name']}")
    print(f"✔️ user.email:     {user['email']}")
    print(f"✔️ origin:         {user['remote']}")
    print(f"✔️ branch:         {branch}")
    print(f"✔️ SSH config 사용: {ssh_config_path}")
    return ssh_config_path, branch

def test_connection(user, ssh_config_path, branch):
    print("\n🌐 GitHub 연결 테스트 중...")
    result = subprocess.run(
        f'ssh -F "{ssh_config_path}" -T {user["host"]}',
        shell=True, capture_output=True, text=True
    )
    output = (result.stdout + result.stderr).strip()
    if "successfully authenticated" in output.lower():
        print(f"\033[92m✔️ [{user['name']} / {branch}] 연결 성공:\033[0m {output}")
    else:
        print(f"\033[91m❌ 연결 실패:\033[0m {output}")

def git_pull():
    print("\n📥 git pull 실행 중...")
    subprocess.run(["git", "pull", "origin", "main"])

def main():
    user = select_user()
    if not user:
        print("❌ 잘못된 입력입니다.")
        return
    ssh_config_path, branch = setup_git(user)

    print("\n==============================")
    print("동작을 선택하세요:")
    print("[5] 연결 테스트만")
    print("[6] pull 실행")
    print("==============================")
    action = input("번호를 입력하세요 (5~6): ").strip()

    if action == "5":
        test_connection(user, ssh_config_path, branch)
    elif action == "6":
        test_connection(user, ssh_config_path, branch)
        git_pull()
    else:
        print("❌ 잘못된 입력입니다.")

if __name__ == "__main__":
    main()
