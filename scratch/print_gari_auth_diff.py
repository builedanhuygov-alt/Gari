import subprocess

baseline = "2318ee75"
proc = subprocess.run(["git", "diff", baseline, "--", "gari_auth.py"], capture_output=True, text=True)
print(f"Diff lines count: {len(proc.stdout.splitlines())}")
print(proc.stdout[:2500])

