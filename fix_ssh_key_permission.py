import subprocess
import os
import sys

# 계정별 SSH 키/원격 설정
KEYS = {
    "1": {
        "name": "members_list_boram",
        "path": r"C:\ChatGPT\id_ed25519_boraminfo",
        "account": "boraminfo",
        "email": "boraminfo@gmail.com",
        "host": "github-boraminfo",
        "remote": "git@github-boraminfo:boraminfo/members_list_boram.git",
    },
    "2": {
        "name": "memberslist",
        "path": r"C:\ChatGPT\id_ed25519_boraminfo",   # 같은 키 공유
        "account": "boraminfo",
        "email": "boraminfo@gmail.com",
        "host": "github-boraminfo",
        "remote": "git@github-boraminfo:boraminfo/memberslist.git",
    },
    "3": {
        "name": "members_list_acareglc",
        "path": r"C:\ChatGPT\id_ed25519_acareglc",
        "account": "acareglc",
        "email": "acareglc@gmail.com",
        "host": "github-acareglc",
        "remote": "git@github-acareglc:acareglc/members_list_acareglc.git",
    },
    "4": {
        "name": "members_list_iamsohappy0418",
        "path": r"C:\ChatGPT\id_ed25519_iamsohappy0418",
        "account": "iamsohappy0418-bit",
        "email": "iamsohappy0418@gmail.com",
        "host": "github-iamsohappy0418",
        "remote": "git@github-iamsohappy0418:iamsohappy0418-bit/members_list_iamsohappy0418.git",
    }
}

SSH_CONFIG_PATH = r"C:/ChatGPT/ssh_config"

def run_cmd(cmd, allow_fail=False, env=None):
    """명령 실행 (출력 표시)"""
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    if result.returncode != 0 and not allow_fail:
        print(f"❌ 명령 실패: {cmd}")
        if not allow_fail:
            sys.exit(result.returncode)
    return result

def fix_permissions(key_path):
    """SSH 키 권한 수정"""
    username = os.getenv("USERNAME")

    print("\n🔑 소유자 설정")
    run_cmd(f'takeown /F "{key_path}"', allow_fail=True)
    run_cmd(f'icacls "{key_path}" /setowner {username}', allow_fail=True)

    print("\n🛠 상속 제거 + 현재 사용자 읽기 권한 부여")
    run_cmd(f'icacls "{key_path}" /inheritance:r', allow_fail=True)
    run_cmd(f'icacls "{key_path}" /grant:r {username}:(R)', allow_fail=True)

    print("\n🧹 불필요한 권한 제거")
    run_cmd(f'icacls "{key_path}" /remove "BUILTIN\\Users" "Users" "Everyone" "Authenticated Users"', allow_fail=True)

    print("\n✅ 최종 권한 확인")
    run_cmd(f'icacls "{key_path}"')

def ssh_test(host):
    """SSH 연결 테스트"""
    print("\n🌐 SSH 연결 테스트 중...")
    cmd = f'ssh -F {SSH_CONFIG_PATH} -T {host}'
    result = run_cmd(cmd, allow_fail=True)
    output = (result.stdout + result.stderr).strip()

    if "successfully authenticated" in output.lower():
        account_name = "Unknown"
        for line in output.splitlines():
            if line.startswith("Hi "):
                account_name = line.split(" ")[1].replace("!", "")
                break
        print(f"\n🎉 SSH 연결 성공 → GitHub 계정: {account_name}")
    else:
        print("\n⚠️ SSH 연결 실패")
        print(output)

def git_ls_remote():
    """Git 원격 연결 확인"""
    print("\n📌 Git 원격 저장소 연결 테스트")
    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = f'ssh -F {SSH_CONFIG_PATH}'
    run_cmd("git ls-remote origin", allow_fail=True, env=env)

def set_git_config(account, email):
    """git config user.name / user.email 설정"""
    print("\n⚙️ Git 사용자 설정 적용")
    run_cmd(f'git config --local user.name "{account}"')
    run_cmd(f'git config --local user.email "{email}"')

    print("\n👤 Git 사용자 설정 확인")
    run_cmd("git config user.name", allow_fail=True)
    run_cmd("git config user.email", allow_fail=True)

def main():
    print("\n==============================")
    print("🔐 SSH 키 선택")
    for k, v in KEYS.items():
        print(f"[{k}] {v['name']}")
    print("==============================")

    choice = input("번호를 입력하세요 (1~4): ").strip()
    key_info = KEYS.get(choice)

    if not key_info:
        print("❌ 잘못된 선택입니다.")
        return

    key_path = key_info["path"]
    host = key_info["host"]
    account = key_info["account"]
    email = key_info["email"]

    print(f"\n👉 선택된 프로젝트: {key_info['name']} (GitHub 계정: {account})\n")

    # 1️⃣ 권한 수정
    fix_permissions(key_path)

    # 2️⃣ SSH 연결 테스트
    ssh_test(host)

    # 3️⃣ Git 원격 저장소 연결 확인
    git_ls_remote()

    # 4️⃣ Git 사용자 설정
    set_git_config(account, email)

if __name__ == "__main__":
    main()
