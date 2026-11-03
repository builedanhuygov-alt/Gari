import inspect
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from api_server import app

print("=" * 100)
print(f"Total routes in FastAPI app: {len(app.routes)}")
print("=" * 100)

for route in app.routes:
    if hasattr(route, "methods"):
        methods = ",".join(sorted(route.methods))
        path = route.path
        endpoint = getattr(route, "endpoint", None)
        endpoint_name = endpoint.__name__ if endpoint else "unknown"
        
        # Check dependencies
        dep_names = []
        if hasattr(route, "dependant"):
            for dep in route.dependant.dependencies:
                if dep.call:
                    dep_names.append(dep.call.__name__)
        deps_str = ", ".join(dep_names) if dep_names else "NO_AUTH"
        print(f"{methods:12} {path:55} -> {endpoint_name:30} [{deps_str}]")
    else:
        print(f"MOUNT        {route.path}")
