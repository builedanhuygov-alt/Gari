import ast
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def analyze_api_server():
    api_server_path = ROOT / "api_server.py"
    with open(api_server_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename="api_server.py")
    
    routes = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                dec_str = ""
                if isinstance(dec, ast.Call):
                    if isinstance(dec.func, ast.Attribute):
                        dec_str = f"@{getattr(dec.func.value, 'id', '')}.{dec.func.attr}"
                        path = ""
                        if dec.args and isinstance(dec.args[0], ast.Constant):
                            path = dec.args[0].value
                        routes.append({
                            "line": node.lineno,
                            "decorator": dec_str,
                            "path": path,
                            "fn": node.name,
                            "args": [arg.arg for arg in node.args.args]
                        })
    return routes

routes = analyze_api_server()
print(f"Total decorated functions found in api_server.py: {len(routes)}")
for r in routes:
    if "app." in r["decorator"]:
        print(f"L{r['line']:4d} | {r['decorator']:15} {r['path']:45} | fn: {r['fn']} | args: {r['args']}")
