
import ast

with open("app.py", "r", encoding="utf-8") as f:
    tree = ast.parse(f.read())

for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        print(node.name, ":", bool(ast.get_docstring(node)))
