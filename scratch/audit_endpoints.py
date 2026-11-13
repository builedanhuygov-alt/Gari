import sys
import re

with open("api_server.py", "r", encoding="utf-8") as f:
    content = f.read()

route_matches = re.findall(r'@(?:app|router)\.(get|post|put|delete|patch|options)\(["\']([^"\']+)["\']', content)
print(f"Total API route matches: {len(route_matches)}")

categories = {
    "auth": [],
    "user_profile": [],
    "crops_catalog": [],
    "diagnosis_predict": [],
    "farms_management": [],
    "community_knowledge": [],
    "expert_network": [],
    "system_health": [],
    "b2b_payments": [],
    "other": []
}

for method, path in route_matches:
    m_p = f"{method.upper()} {path}"
    if "/auth" in path:
        categories["auth"].append(m_p)
    elif "/user" in path or "/profile" in path:
        categories["user_profile"].append(m_p)
    elif "/predict" in path or "/diagnos" in path or "/leaf" in path:
        categories["diagnosis_predict"].append(m_p)
    elif "/crop" in path or "/disease" in path:
        categories["crops_catalog"].append(m_p)
    elif "/farm" in path or "/plot" in path or "/task" in path:
        categories["farms_management"].append(m_p)
    elif "/community" in path or "/post" in path or "/comment" in path:
        categories["community_knowledge"].append(m_p)
    elif "/expert" in path:
        categories["expert_network"].append(m_p)
    elif "/health" in path or "/ready" in path or "/metrics" in path or "/status" in path:
        categories["system_health"].append(m_p)
    elif "/pay" in path or "/plan" in path or "/b2b" in path or "/voucher" in path or "/subscription" in path:
        categories["b2b_payments"].append(m_p)
    else:
        categories["other"].append(m_p)

for cat, routes in categories.items():
    print(f"\n--- {cat.upper()} ({len(routes)} routes) ---")
    for r in routes[:10]:
        print(f"  {r}")
    if len(routes) > 10:
        print(f"  ... and {len(routes)-10} more")

