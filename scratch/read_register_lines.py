with open("frontend2/register.html", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, l in enumerate(lines, 1):
    if "khởi tạo tài khoản" in l or "addEventListener" in l or "fetch(" in l or "register" in l.lower() and "form" in l.lower():
        print(f"{i:4d}: {l.strip()[:100]}")

