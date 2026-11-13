with open('api_server.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = "experts = gari_database.list_expert_profiles(active_only=active_only, limit=limit, offset=offset)"
replacement = "experts = gari_database.list_expert_profiles(active_only=active_only)"

if target in text:
    text = text.replace(target, replacement, 1)
    with open('api_server.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Fixed list_expert_profiles call in api_server.py")
else:
    print("Target not found")
