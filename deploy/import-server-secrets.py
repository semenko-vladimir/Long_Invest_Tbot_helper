#!/usr/bin/env python3
"""Receive selected Tbot credentials on stdin and merge them into server config."""

import json
import os
import re
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def write_private(path: Path, content: str) -> None:
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        if set(payload) != {"bot_token", "chat_id", "sandbox_token"}:
            raise ValueError("Unexpected field set")
        token = payload["bot_token"]
        chat_id = str(payload["chat_id"])
        sandbox_token = payload["sandbox_token"]
        if not isinstance(token, str) or not re.fullmatch(r"\d+:[A-Za-z0-9_-]{20,}", token):
            raise ValueError("BOT_TOKEN is missing or malformed")
        if not re.fullmatch(r"-?\d{5,}", chat_id):
            raise ValueError("CHAT_ID is missing or malformed")
        if not isinstance(sandbox_token, str) or not sandbox_token or sandbox_token.startswith("your_"):
            raise ValueError("SANDBOX_TOKEN is missing")

        env_path = ROOT / ".env"
        users_path = ROOT / "users.json"
        env_lines = env_path.read_text(encoding="utf-8").splitlines()
        user_config = json.loads(users_path.read_text(encoding="utf-8"))
        users = user_config["users"]
        if len(users) != 1 or users[0].get("id") != "default":
            raise ValueError("Expected one default user in users.json")

        replaced = False
        for index, line in enumerate(env_lines):
            if re.match(r"^\s*BOT_TOKEN\s*=", line):
                env_lines[index] = "BOT_TOKEN = " + json.dumps(token)
                replaced = True
        if not replaced:
            env_lines.append("BOT_TOKEN = " + json.dumps(token))
        users[0]["telegram_chat_id"] = chat_id
        users[0]["sandbox_token"] = sandbox_token

        write_private(users_path, json.dumps(user_config, ensure_ascii=False, indent=2) + "\n")
        write_private(env_path, "\n".join(env_lines) + "\n")
        print("Three selected fields imported; no values printed.")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"Import failed: {type(error).__name__}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
