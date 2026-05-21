"""
push_to_github.py — Saare bot files GitHub pe push karta hai.

Replit mein run karo:
    python3 telegram-bot/push_to_github.py

Agar sirf kuch files push karni hain:
    python3 telegram-bot/push_to_github.py main.py payment.py
"""

import os
import sys
import json
import base64
from urllib import request, error

# ─── CONFIG — yahan apna token daalo ─────────────────────────────────────────
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")  # Ya seedha yahan paste karo
OWNER = "lakshayp3500-sys"
REPO  = "Mybot"
BRANCH = "main"
BOT_DIR = os.path.join(os.path.dirname(__file__))  # telegram-bot/ folder
# ─────────────────────────────────────────────────────────────────────────────

SKIP_FILES = {".env", "voucher_bot.db", "push_to_github.py"}
SKIP_DIRS  = {"__pycache__", "qr_codes", ".pythonlibs"}
SKIP_EXT   = {".pyc", ".pyo", ".db"}

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/vnd.github.v3+json",
}


def gh(method, path, data=None):
    url  = f"https://api.github.com{path}"
    body = json.dumps(data).encode() if data else None
    req  = request.Request(url, data=body, headers=HEADERS, method=method)
    try:
        with request.urlopen(req) as r:
            return json.loads(r.read())
    except error.HTTPError as e:
        print(f"[ERROR] HTTP {e.code} — {e.read().decode()[:200]}")
        raise


def collect_files(specific=None):
    """Return list of (relative_path, full_path) to push."""
    if specific:
        return [(f, os.path.join(BOT_DIR, f)) for f in specific
                if os.path.exists(os.path.join(BOT_DIR, f))]
    files = []
    for root, dirs, filenames in os.walk(BOT_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in filenames:
            if fname in SKIP_FILES:
                continue
            if any(fname.endswith(e) for e in SKIP_EXT):
                continue
            full = os.path.join(root, fname)
            rel  = os.path.relpath(full, BOT_DIR)
            files.append((rel, full))
    return files


def push(specific_files=None):
    if not GITHUB_TOKEN:
        print("[ERROR] GITHUB_TOKEN nahi mila!")
        print("  Option 1: GITHUB_TOKEN env var set karo")
        print("  Option 2: Is file mein line 14 pe token paste karo")
        return

    print(f"Repo: {OWNER}/{REPO} ({BRANCH})")

    # Branch info
    info = gh("GET", f"/repos/{OWNER}/{REPO}/branches/{BRANCH}")
    base_commit = info["commit"]["sha"]
    base_tree   = info["commit"]["commit"]["tree"]["sha"]

    files = collect_files(specific_files)
    print(f"Files to push: {len(files)}")

    # Blobs
    tree_items = []
    for rel, full in files:
        with open(full, "rb") as f:
            content = f.read()
        blob = gh("POST", f"/repos/{OWNER}/{REPO}/git/blobs", {
            "content": base64.b64encode(content).decode(),
            "encoding": "base64",
        })
        tree_items.append({"path": rel, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print(f"  Uploaded: {rel}")

    # Commit
    new_tree   = gh("POST", f"/repos/{OWNER}/{REPO}/git/trees",   {"base_tree": base_tree, "tree": tree_items})
    new_commit = gh("POST", f"/repos/{OWNER}/{REPO}/git/commits", {
        "message": "Update from Replit",
        "tree": new_tree["sha"],
        "parents": [base_commit],
    })
    gh("PATCH", f"/repos/{OWNER}/{REPO}/git/refs/heads/{BRANCH}", {
        "sha": new_commit["sha"], "force": True
    })

    print(f"\nDONE! https://github.com/{OWNER}/{REPO}")
    print("Railway auto-redeploy shuru ho gaya!")


if __name__ == "__main__":
    specific = sys.argv[1:] if len(sys.argv) > 1 else None
    push(specific)
