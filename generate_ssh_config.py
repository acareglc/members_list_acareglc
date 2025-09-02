from pathlib import Path

# 사용자 계정 정의
users = [
    {"host": "github-boraminfo",    "identity": "id_ed25519_boraminfo"},
    {"host": "github-acareglc",  "identity": "id_ed25519_acareglc"},
    {"host": "github-iamsohappy0418",    "identity": "id_ed25519_iamsohappy0418"},
    
]

def generate_ssh_config():
    project_root = Path(__file__).parent
    ssh_config_path = project_root / "set_git_user" / "ssh_config"  # ✅ 수정된 경로

    ssh_config_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []

    for user in users:
        identity_path = Path("C:/ChatGPT") / user["identity"]
        lines.append(f"""Host {user['host']}
    HostName github.com
    User git
    IdentityFile {identity_path.as_posix()}
    IdentitiesOnly yes
""")

    ssh_config_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ SSH 설정 파일 생성 완료 → {ssh_config_path}")

if __name__ == "__main__":
    generate_ssh_config()
