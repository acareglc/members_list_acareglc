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
    print(f"\n✅ [{user['name']}] 설정 완료 (branch:{branch})")
    return branch

def show_changes():
    result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
    changes = result.stdout.strip()
    if not changes:
        print("✅ 변경 사항 없음.")
        return False
    print("\n📄 변경된 파일 목록:")
    print(changes)
    return True

def git_commit_and_push(branch):
    if not show_changes():
        return

    commit_msg = input("\n💬 커밋 메시지를 입력하세요: ").strip()
    if not commit_msg:
        print("❌ 커밋 메시지가 비어있습니다.")
        return

    subprocess.run(["git", "add", "."])
    subprocess.run(["git", "commit", "-m", commit_msg])
    subprocess.run(["git", "pull", "origin", branch])
    subprocess.run(["git", "push", "origin", branch])
    print("\n🚀 Push 완료!")

def main():
    user = select_user()
    if not user:
        print("❌ 잘못된 입력입니다.")
        return
    branch = setup_git(user)
    git_commit_and_push(branch)

if __name__ == "__main__":
    main()


