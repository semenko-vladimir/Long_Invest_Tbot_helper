#!/usr/bin/env python3
"""Send only three selected local .env values to semenkohome over SSH stdin."""

import json
import re
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parent.parent
LOCAL_ENV = ROOT / ".env"
REMOTE_IMPORTER = "/home/feelwent/apps/investment-tbot/deploy/import-server-secrets.py"


def main() -> None:
    values = dotenv_values(LOCAL_ENV)
    token = values.get("BOT_TOKEN") or ""
    chat_id = values.get("CHAT_ID") or ""
    sandbox_token = values.get("SANDBOX_TOKEN") or ""
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]{20,}", token):
        raise SystemExit("Local BOT_TOKEN is missing or malformed")
    if not re.fullmatch(r"-?\d{5,}", chat_id):
        raise SystemExit("Local CHAT_ID is missing or malformed")
    if not sandbox_token or sandbox_token.startswith("your_"):
        raise SystemExit("Local SANDBOX_TOKEN is missing")
    if sys.argv[1:] == ["--check"]:
        print("Local BOT_TOKEN, CHAT_ID, and SANDBOX_TOKEN are present.")
        return
    if sys.argv[1:]:
        raise SystemExit("Usage: transfer-secrets.py [--check]")

    payload = json.dumps({
        "bot_token": token,
        "chat_id": chat_id,
        "sandbox_token": sandbox_token,
    })
    ssh = Path("C:/Windows/System32/OpenSSH/ssh.exe")
    result = subprocess.run(
        [str(ssh), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
         "-T", "semenkohome", "python3", REMOTE_IMPORTER],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise SystemExit("SSH import failed. No credential values were printed.")
    print(result.stdout.strip())


if __name__ == "__main__":
    main()
