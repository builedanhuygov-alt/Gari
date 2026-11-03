import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
api_server_path = ROOT / "api_server.py"

with open(api_server_path, "r", encoding="utf-8") as f:
    tree = ast.parse(f.read(), filename="api_server.py")

for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if node.lineno <= 1980:
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                    dec_str = f"@{getattr(dec.func.value, 'id', '')}.{dec.func.attr}"
                    path = ""
                    if dec.args and isinstance(dec.args[0], ast.Constant):
                        path = dec.args[0].value
                    print(f"L{node.lineno:4d} | {dec_str:15} {path:50} | fn: {node.name:30} | args: {[arg.arg for arg in node.args.args]}")
