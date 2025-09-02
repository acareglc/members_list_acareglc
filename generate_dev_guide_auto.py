import os
import re
import ast

DOCS_DIR = "docs"
DOC_FILE = os.path.join(DOCS_DIR, "DEVELOPER_AUTO_GUIDE.md")
APP_FILE = "app.py"   # 분석 대상 파일

ROUTE_PATTERN = re.compile(
    r'@app\.route\(["\']([^"\']+)["\'].*?\)\s*def\s+(\w+)',
    re.DOTALL
)

def extract_routes_with_docstrings(app_path):
    """app.py에서 라우트 경로, 함수명, docstring 추출"""
    with open(app_path, "r", encoding="utf-8") as f:
        code = f.read()

    # 라우트 매핑 (path → 함수명)
    matches = ROUTE_PATTERN.findall(code)

    # AST로 함수 docstring 추출
    tree = ast.parse(code)
    func_docs = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            docstring = ast.get_docstring(node) or ""
            func_docs[node.name] = docstring

    routes = []
    for path, func in matches:
        routes.append({
            "path": path,
            "func": func,
            "doc": func_docs.get(func, "").strip()
        })
    return routes

def generate_markdown(routes):
    """라우트 + docstring을 Markdown으로 변환"""
    lines = []
    lines.append("# 📑 API Route 자동 문서 (docstring 기반)")
    lines.append("")
    lines.append("이 문서는 `app.py`에서 자동 추출한 라우트 목록 + docstring 설명을 포함합니다.")
    lines.append("")
    lines.append("| 경로(Path) | 함수명(Function) | 설명 (docstring) |")
    lines.append("|------------|-----------------|------------------|")
    for r in routes:
        desc = r['doc'].split("\n")[0] if r['doc'] else "⚠️ 설명 없음"
        lines.append(f"| `{r['path']}` | `{r['func']}` | {desc} |")
    lines.append("")
    lines.append("## 📄 상세 Docstring")
    for r in routes:
        lines.append(f"### `{r['path']}` → `{r['func']}`")
        if r['doc']:
            lines.append("```text")
            lines.append(r['doc'])
            lines.append("```")
        else:
            lines.append("_⚠️ docstring 없음_")
        lines.append("")
    return "\n".join(lines)

def main():
    os.makedirs(DOCS_DIR, exist_ok=True)
    routes = extract_routes_with_docstrings(APP_FILE)
    md_content = generate_markdown(routes)
    with open(DOC_FILE, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"✅ 자동 문서 생성 완료: {DOC_FILE}")

if __name__ == "__main__":
    main()
