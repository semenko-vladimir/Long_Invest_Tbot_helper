#!/usr/bin/env python3
"""Back up live config/data, then enable production portfolio reads without trades."""

import json
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BACKUPS = ROOT / "backups"


def write_private(path: Path, content: str) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def replace_env(lines: list[str], name: str, value: str) -> None:
    replacement = f"{name} = {json.dumps(value)}"
    found = False
    for index, line in enumerate(lines):
        if re.match(rf"^\s*{re.escape(name)}\s*=", line):
            lines[index] = replacement
            found = True
    if not found:
        lines.append(replacement)


env_path = ROOT / ".env"
users_path = ROOT / "users.json"
db_path = ROOT / "data/users/default/database.db"
config = json.loads(users_path.read_text(encoding="utf-8"))
users = config.get("users", [])
if len(users) != 1 or users[0].get("id") != "default":
    raise SystemExit("Expected one default user; configuration unchanged")
user = users[0]
token = user.get("sandbox_token")
if not isinstance(token, str) or not token or token.startswith("your_"):
    raise SystemExit("Existing token is absent; configuration unchanged")
if user.get("token") and user["token"] != token:
    raise SystemExit("A different production token is already configured; configuration unchanged")
if not db_path.is_file():
    raise SystemExit("User database is absent; configuration unchanged")

env_lines = env_path.read_text(encoding="utf-8").splitlines()
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
BACKUPS.mkdir(mode=0o700, exist_ok=True)
backup_env = BACKUPS / f"pre_readonly_{stamp}.env"
backup_users = BACKUPS / f"pre_readonly_{stamp}.users.json"
backup_db = BACKUPS / f"pre_readonly_{stamp}.db"
for path in (backup_env, backup_users, backup_db):
    if path.exists():
        raise SystemExit("Backup target already exists; configuration unchanged")

shutil.copy2(env_path, backup_env)
shutil.copy2(users_path, backup_users)
with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as source:
    with sqlite3.connect(backup_db) as target:
        source.backup(target)
for path in (backup_env, backup_users, backup_db):
    path.chmod(0o600)

user["token"] = token
for name, value in {
    "APP_MODE": "prod",
    "INVEST_MODE": "prod",
    "ALLOW_PROD_TRADING": "false",
    "ALLOW_AUTO_INVESTING": "false",
    "ENABLE_STRATEGY_AUTO_EXECUTION": "false",
    "ALLOW_STRATEGY_AUTO_EXECUTION": "false",
    "MAX_ORDER_RUB": "0",
    "MAX_DAILY_INVEST_RUB": "0",
}.items():
    replace_env(env_lines, name, value)

write_private(users_path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
write_private(env_path, "\n".join(env_lines) + "\n")
print("Read-only production portfolio configuration saved.")
print("Backups:", backup_env.name, backup_users.name, backup_db.name)
