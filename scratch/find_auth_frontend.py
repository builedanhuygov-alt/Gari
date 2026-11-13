import os

text_to_find = "khởi tạo tài khoản"
results = []
for root, dirs, files in os.walk("frontend2"):
    for f in files:
        if f.endswith((".html", ".js", ".ts", ".css")):
            p = os.path.join(root, f)
            try:
                with open(p, "r", encoding="utf-8") as fp:
                    content = fp.read()
                    if text_to_find.lower() in content.lower():
                        results.append(p)
            except Exception:
                pass

print("Files matching 'khởi tạo tài khoản':", results)

# Also search for register form or register handler
for root, dirs, files in os.walk("frontend2"):
    for f in ["register.html", "login.html", "app.js"]:
        if f in files:
            print(f"Found {f} at {os.path.join(root, f)}")

