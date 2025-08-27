import subprocess
import sys
import os

# 프로젝트별 원격 저장소 정의 (ssh_config HostAlias 기반)
PROJECTS = {
    "1": {
        "name": "members_list_boram",
        "account": "boraminfo",
        "email": "boraminfo@gmail.com",
        "remote": "git@github-boraminfo:boraminfo/members_list_boram.git",
        "host": "github-boraminfo"
    },
    "2": {
        "name": "memberslist",
        "account": "boraminfo",
        "email": "boraminfo@gmail.com",
        "remote": "git@github-boraminfo:boraminfo/memberslist.git",
        "host": "github-boraminfo"
    },
    "3": {
        "name": "members_list_acareglc",
        "account": "acareglc",
        "email": "acareglc@gmail.com",
        "remote": "git@github-acareglc:acareglc/members_list_acareglc.git",
        "host": "github-acareglc"
    },
    "4": {
        "name": "members_list_iamsohappy0418",
        "account": "iamsohappy0418-bit",
        "email": "iamsohappy0418@gmail.com",
        "remote": "git@github-iamsohappy0418:iamsohappy0418-bit/members_list_iamsohappy0418.git",
        "host": "github-iamsohappy0418"
    }
}

SSH_CONFIG_PATH = r"C:/ChatGPT/ssh_config"

def run_cmd(cmd, allow_fail=False):
    """명령 실행 (출력 표시)"""
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    if result.returncode != 0 and not allow_fail:
        sys.exit(result.returncode)
    return result

def clear_remotes():
    """기존 remote 모두 제거"""
    result = subprocess.run(["git", "remote"], capture_output=True, text=True)
    remotes = result.stdout.strip().splitlines()
    for r in remotes:
        if r.strip():
            run_cmd(["git", "remote", "remove", r.strip()], allow_fail=True)
    if remotes:
        print(f"🗑 기존 remote 제거 완료: {', '.join(remotes)}")
    else:
        print("ℹ️ 기존 remote 없음")

def ssh_test(host):
    """SSH 연결 테스트 (항상 ssh_config HostAlias 사용)"""
    print("\n🌐 SSH 연결 테스트 중...")
    cmd = ["ssh", "-F", SSH_CONFIG_PATH, "-T", host]
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
        print(f"\n⚠️ SSH 연결 실패:\n{output}")

def set_git_remote(remote_url):
    """git remote origin 재설정"""
    result = subprocess.run(["git", "remote"], capture_output=True, text=True)
    remotes = result.stdout.strip().splitlines()
    for r in remotes:
        if r.strip():
            run_cmd(["git", "remote", "remove", r.strip()], allow_fail=True)

    run_cmd(["git", "remote", "add", "origin", remote_url], allow_fail=False)

    print(f"\n✅ 원격 저장소가 {remote_url} 으로 변경되었습니다.")
    run_cmd(["git", "remote", "-v"], allow_fail=False)

def set_git_config(name, email):
    """git config user.name / user.email 설정"""
    run_cmd(["git", "config", "--local", "user.name", name])
    run_cmd(["git", "config", "--local", "user.email", email])
    print("\n👤 Git 사용자 설정 완료:")
    run_cmd(["git", "config", "user.name"], allow_fail=True)
    run_cmd(["git", "config", "user.email"], allow_fail=True)

def main():
    print("\n==============================")
    print("📂 프로젝트 선택")
    for k, v in PROJECTS.items():
        print(f"[{k}] {v['name']}  → GitHub 계정: {v['account']}")
    print("==============================")

    choice = input("번호를 입력하세요 (1~4): ").strip()
    proj = PROJECTS.get(choice)

    if not proj:
        print("❌ 잘못된 선택입니다.")
        sys.exit(1)

    account = proj["account"]
    email = proj["email"]
    remote_url = proj["remote"]
    host = proj["host"]

    print(f"\n👉 선택된 프로젝트: {proj['name']} (GitHub 계정: {account})\n")

    # Git 원격 저장소 설정
    clear_remotes()
    set_git_remote(remote_url)

    # SSH 연결 테스트 (항상 HostAlias)
    ssh_test(host)

    # Git config user.name / user.email 설정
    set_git_config(account, email)

    # 현재 Git 상태 확인
    print("\n📌 현재 Git 상태 확인:")
    run_cmd(["git", "status"], allow_fail=True)

if __name__ == "__main__":
    main()
