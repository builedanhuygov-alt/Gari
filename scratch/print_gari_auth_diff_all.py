import subprocess

baseline = "2318ee75"
proc = subprocess.run(["git", "diff", baseline, "--", "gari_auth.py"], capture_output=True, text=True)
lines = proc.stdout.splitlines()
print(f"Total lines: {len(lines)}")
# Print chunks
for i in range(0, len(lines), 80):
    print(f"--- Chunk {i//80} ---")
    print("\n".join(lines[i:i+80]))

