import subprocess
import os

baseline = "2318ee75"

def check_auth_diffs():
    auth_files = [
        "frontend2/register.html",
        "frontend2/login.html",
        "frontend2/forgot-password.html",
        "frontend2/firebase-client.js",
        "frontend2/app.js",
        "frontend2/host-login.html",
        "frontend2/host.html",
        "api/[...path].js",
        "frontend2/api/[...path].js",
        "api/auth/firebase-config.js",
        "frontend2/api/auth/firebase-config.js",
        "gari_auth.py",
        "gari_firebase.py"
    ]

    print("=== GIT DIFF AGAINST BASELINE 2318ee75 FOR AUTH-RELATED FILES ===")
    for f in auth_files:
        if not os.path.exists(f):
            print(f"[NOT IN FS] {f}")
            continue
        proc = subprocess.run(["git", "diff", baseline, "--", f], capture_output=True, text=True)
        diff = proc.stdout.strip()
        if not diff:
            # check if file is untracked
            p_untracked = subprocess.run(["git", "status", "--porcelain", f], capture_output=True, text=True)
            if "??" in p_untracked.stdout:
                print(f"[UNTRACKED FILE] {f} (size: {os.path.getsize(f)} bytes)")
            else:
                print(f"[IDENTICAL TO BASELINE] {f}")
        else:
            diff_lines = diff.split("\n")
            print(f"[MODIFIED vs BASELINE] {f} ({len(diff_lines)} lines of diff)")
            # print diff stat / summary
            added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
            removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))
            print(f"    Added: {added}, Removed: {removed}")

if __name__ == '__main__':
    check_auth_diffs()

