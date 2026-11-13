import os
import shutil

art_dir = r"C:\Users\danhu\.gemini\antigravity\brain\f726ce3c-fc1b-42bc-a6f0-9ea2576ca58b"
os.makedirs(art_dir, exist_ok=True)

for i in range(1, 7):
    pattern = f"expansion_0{i}"
    for f in os.listdir("tests/screenshots"):
        if f.startswith(pattern):
            src = os.path.join("tests/screenshots", f)
            dst = os.path.join(art_dir, f)
            shutil.copy2(src, dst)
            print(f"Copied {f} to artifacts directory.")
