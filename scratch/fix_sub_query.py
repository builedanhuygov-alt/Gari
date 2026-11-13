with open('api_server.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = """            SELECT plan, status, count(*) as count 
            FROM subscriptions 
            GROUP BY plan, status"""

replacement = """            SELECT plan_id as plan, status, count(*) as count 
            FROM subscriptions 
            GROUP BY plan_id, status"""

if target in text:
    text = text.replace(target, replacement, 1)
    with open('api_server.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Fixed subscriptions query in api_server.py')
else:
    print('Target not found')
