import subprocess
import os
import re

baseline = "2318ee75"

suspicious_patterns = [
    r"<\?php",
    r"<\?=",
    r"eval\s*\(",
    r"base64_decode",
    r"system\s*\(",
    r"exec\s*\(",
    r"passthru\s*\(",
    r"shell_exec\s*\(",
    r"`.*`",
    r"assert\s*\(",
    r"fromCharCode",
    r"unescape\s*\(",
    r"\\x[0-9a-fA-F]{2}",
    r"data:text/html",
    r"iframe\s+src",
    r"onload\s*=",
    r"onerror\s*=",
    r"document\.cookie"
]

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

def scan_file_for_suspicious(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    findings = []
    for pat in suspicious_patterns:
        matches = list(re.finditer(pat, content, re.IGNORECASE))
        for m in matches:
            line_no = content[:m.start()].count('\n') + 1
            line = content.split('\n')[line_no - 1].strip()
            findings.append((line_no, pat, line[:120]))
    return findings

def run():
    print("=== STATIC CODE SCAN ON AUTH-RELATED FILES ===")
    for f in auth_files:
        findings = scan_file_for_suspicious(f)
        if findings:
            print(f"\n[POTENTIAL HITS] {f} ({len(findings)} matches):")
            for lno, pat, sample in findings[:10]:
                print(f"  Line {lno:4d} | Pat: {pat:15s} | {sample}")
            if len(findings) > 10:
                print(f"  ... and {len(findings) - 10} more matches")
        else:
            print(f"[CLEAN] {f}")

if __name__ == '__main__':
    run()

