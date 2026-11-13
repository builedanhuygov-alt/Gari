import subprocess
import os
import datetime

def check_git_status():
    proc = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
    lines = proc.stdout.strip().split('\n')
    print(f"Total entries in git status: {len(lines)}")
    today = datetime.datetime(2026, 11, 11, 0, 0, 0)
    investigation_start = datetime.datetime(2026, 11, 11, 15, 40, 0)

    session_files = []
    earlier_today_files = []
    older_files = []

    for line in lines:
        if not line.strip(): continue
        status = line[:2]
        path = line[3:].strip()
        # handle quoted paths or renamed paths
        if ' -> ' in path:
            path = path.split(' -> ')[1]
        path = path.strip('"')
        
        if os.path.exists(path):
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path))
            if mtime >= investigation_start:
                session_files.append((status, mtime, path))
            elif mtime >= today:
                earlier_today_files.append((status, mtime, path))
            else:
                older_files.append((status, mtime, path))
        else:
            older_files.append((status, None, path))

    print(f"\n--- FILES MODIFIED DURING LOGIN/LOGOUT INVESTIGATION (>= 15:40) [{len(session_files)}] ---")
    for st, mt, p in session_files:
        print(f"[{st}] {mt.strftime('%Y-%m-%d %H:%M:%S')} {p}")

    print(f"\n--- FILES MODIFIED EARLIER TODAY (2026-11-11, before 15:40) [{len(earlier_today_files)}] ---")
    for st, mt, p in earlier_today_files:
        print(f"[{st}] {mt.strftime('%Y-%m-%d %H:%M:%S')} {p}")

    print(f"\n--- OLDER MODIFIED/UNTRACKED FILES (Prior to 2026-11-11) [{len(older_files)}] ---")
    for st, mt, p in older_files[:10]:
        mts = mt.strftime('%Y-%m-%d %H:%M:%S') if mt else 'DELETED/ABSENT'
        print(f"[{st}] {mts} {p}")
    if len(older_files) > 10:
        print(f"... and {len(older_files) - 10} more older files.")

if __name__ == '__main__':
    check_git_status()

