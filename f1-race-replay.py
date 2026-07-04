#!/usr/bin/env python3
"""
F1 Race Replay - Launcher
Double-click or run: python3 f1-race-replay.py
First run clones the repo and installs dependencies (~1 min).
Later runs pull updates and launch instantly.
"""

import sys
import os
import subprocess
from pathlib import Path

REPO_URL = "https://github.com/matiua/f1-race-replay-app"
INSTALL_DIR = Path(__file__).parent / "f1-race-replay"


def run(cmd, **kwargs):
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        sys.exit(result.returncode)
    return result


def _normalize_repo_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[: -len(".git")]
    return url


def main():
    print("============================================")
    print("        F1 Race Replay - Launcher")
    print("============================================\n")

    # Check Python version
    if sys.version_info < (3, 10):
        print(f"ERROR: Python 3.10+ is required. You have {sys.version.split()[0]}")
        print("\nDownload Python 3.11 from: https://www.python.org/downloads/")
        input("\nPress Enter to close...")
        sys.exit(1)

    # Check Git
    if subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
        print("ERROR: Git is not installed.")
        print("\nMac: run   xcode-select --install   in Terminal")
        print("Windows: https://git-scm.com/download/win")
        input("\nPress Enter to close...")
        sys.exit(1)

    # Clone or update repo
    if not INSTALL_DIR.exists():
        print("[1/4] Cloning repository...")
        run(["git", "clone", REPO_URL, str(INSTALL_DIR)])
    else:
        # An existing folder may have been cloned from an older/different
        # remote (e.g. before this fork existed). `git pull` silently pulls
        # from whatever remote is already configured, not from REPO_URL, so
        # fix the remote first if it doesn't match.
        current_url = subprocess.run(
            ["git", "-C", str(INSTALL_DIR), "remote", "get-url", "origin"],
            capture_output=True, text=True
        ).stdout.strip()
        if _normalize_repo_url(current_url) != _normalize_repo_url(REPO_URL):
            print(f"[1/4] Existing folder points at a different repo ({current_url}). Fixing remote...")
            run(["git", "-C", str(INSTALL_DIR), "remote", "set-url", "origin", REPO_URL])
        print("[1/4] Pulling latest updates...")
        run(["git", "-C", str(INSTALL_DIR), "pull"])

    # Python executable to use for venv
    python = sys.executable
    venv_dir = INSTALL_DIR / "venv"
    pip = venv_dir / ("Scripts/pip.exe" if sys.platform == "win32" else "bin/pip")
    py  = venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

    # Create venv
    if not venv_dir.exists():
        print("[2/4] Creating virtual environment...")
        run([python, "-m", "venv", str(venv_dir)])
    else:
        print("[2/4] Virtual environment ready.")

    # Install dependencies
    print("[3/4] Installing dependencies (first run takes ~1 min)...")
    run([str(pip), "install", "--quiet", "-r", str(INSTALL_DIR / "requirements.txt")])

    # Launch
    print("[4/4] Launching F1 Race Replay...\n")
    subprocess.run([str(py), str(INSTALL_DIR / "main.py")])

    input("\nApp closed. Press Enter to exit.")


if __name__ == "__main__":
    main()
