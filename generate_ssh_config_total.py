from pathlib import Path
import os
import subprocess
import sys

# 1) SSH 설정에 넣을 사용자/호스트 목록
SSH_USERS = [
    {"host": "github-boraminfo",      "identity": "id_ed25519_boraminfo"},
    {"host": "github-acareglc",       "identity": "id_ed25519_acareglc"},
    {"host": "github-iamsohappy0418", "identity": "id_ed25519_iamsohappy0418"},
]

# 2) Git user/remote 선택 목록
GIT_USERS = {
    "1": {
        "name": "boraminfo",
        "email": "boraminfo@gmail.com",
        "remote": "git@github-boraminfo:boraminfo/members_list_boram.git",
    },
    "2": {
        "name": "boraminfo",
        "email": "boraminfo@gmail.com",
        "remote": "git@github-boraminfo:boraminfo/memberslist.git",
    },
    "3": {
        "name": "acareglc",
        "email": "acareglc@gmail.com",
        "remote": "git@github-acareglc:acareglc/members_list_acareglc.git",
    },
    "4": {
        "name": "iamsohappy0418",
        "email": "iamsohappy0418@gmail.com",
        "remote": "git@github-iamsohappy0418:iamsohappy0418/members_list_iamsohappy0418.git",
    },
}

def generate_ssh_config() -> Path:
    """C:/ChatGPT/ssh_config 파일을 덮어쓰기 생성"""
    ssh_config_path = Path("C:/ChatGPT/ssh_config")
    ssh_config_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    for u in SSH_USERS:
        identity_path = Path("C:/ChatGPT") / u["identity"]
        lines.append(
            f"""Host {u['host']}
    HostName github.com
    User git
    IdentityFile {identity_path.as_posix()}
    IdentitiesOnly yes
"""
        )

    ssh_config_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ SSH 설정 파일 생성(덮어쓰기) → {ssh_config_path}")
    return ssh_config_path

def select_git_user() -> dict:
    print("\n==============================")
    print("🔐 Git 사용자 계정을 선택하세요:")
    print("[1] members_list_boram")
    print("[2] memberslist")
    print("[3] acareglc")
    print("[4] iamsohappy0418")
    print("==============================")
    choice = input("번호를 입력하세요 (1~4): ").strip()

    user = GIT_USERS.get(choice)
    if not user:
        print("❌ 잘못된 입력입니다.")
        sys.exit(1)
    return user

def reset_and_set_remote(user: dict):
    """모든 remote 삭제 후 origin만 등록"""
    result = subprocess.run(["git", "remote"], capture_output=True, text=True)
    remotes = result.stdout.split()

    for r in remotes:
        if r.strip():
            subprocess.run(["git", "remote", "remove", r], check=False)
            print(f"🗑️ remote '{r}' 삭제")

    subprocess.run(["git", "remote", "add", "origin", user["remote"]], check=False)
    print(f"🔗 remote 'origin' 추가: {user['remote']}")

def apply_git_settings(user: dict, ssh_config_path: Path):
    os.environ["GIT_SSH_COMMAND"] = f'ssh -F "{ssh_config_path}"'

    subprocess.run(["git", "config", "--local", "user.name", user["name"]], check=False)
    subprocess.run(["git", "config", "--local", "user.email", user["email"]], check=False)

    reset_and_set_remote(user)

    print("\n✅ 설정 완료:")
    print(f"✔️ user.name:       {user['name']}")
    print(f"✔️ user.email:      {user['email']}")
    print(f"✔️ origin:          {user['remote']}")
    print(f"✔️ SSH config 사용: {ssh_config_path}")

    print("\n📌 현재 등록된 git remote 목록:")
    subprocess.run(["git", "remote", "-v"])

def main():
    ssh_config_path = generate_ssh_config()
    user = select_git_user()
    apply_git_settings(user, ssh_config_path)

if __name__ == "__main__":
    main()
