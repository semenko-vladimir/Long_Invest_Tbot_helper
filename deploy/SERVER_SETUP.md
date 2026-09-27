# semenkohome deployment

The Telegram bot runs in the `investment-tbot` container from
`/home/feelwent/apps/investment-tbot`. Its Docker image is
`investment-tbot:20260927` and its data directory is `data/users/default`.
The old `tbot` container remains stopped and available for rollback.

## User configuration

Edit `.env` and `users.json` on the server. `BOT_TOKEN` is in `.env`;
`telegram_chat_id`, `sandbox_token`, and `token` are in `users.json`. The
current token was verified against the real T-Invest API and the bot is set
to `APP_MODE="prod"` for real portfolio reads. Keep `ALLOW_PROD_TRADING`
and all automatic execution flags set to `false`; keep `SSL_TBANK_VERIFY`
set to `True`. Both configuration files should retain mode `0600`.

From the Windows laptop, the three required fields can be copied from the
local `.env` through SSH without putting their values in a command line or
creating an extra credentials file on the server:

```powershell
cd C:\Users\vladimir\Desktop\Investment\Tbot
.\venv312\Scripts\python.exe deploy\transfer-secrets.py --check
.\venv312\Scripts\python.exe deploy\transfer-secrets.py
```

The transfer excludes the `TOKEN` field and leaves all other server settings
unchanged. The current `token` field was set from the already configured
`sandbox_token` after a read-only real API check proved it could list the
real accounts. Run the second command only when ready to copy the three
credentials; it does not change the mode.

Check the fields without printing values:

```sh
cd /home/feelwent/apps/investment-tbot
python3 deploy/check-server-config.py
```

## History

The original database was backed up to `backups/legacy_tbot_20260927.db` using
SQLite's online backup API. Its migrated copy is in
`data/users/default/database.db`. The migration preserved all original table
row counts; both the original database and backup remain untouched. The
current database schema revision is `a3d9c8b7e621`.
The switch to read-only real portfolio mode backed up `.env`, `users.json`,
and the live SQLite database under `backups/pre_readonly_20260927T191926Z.*`.

## Telegram proxy

The private proxy listens on `127.0.0.1:12335` and is managed by the user
service `investment-telegram-proxy.service`. A user timer named
`investment-vpn-refresh.timer` refreshes its subscription daily. Credentials
and the subscription address live outside this repository under
`/home/feelwent/.config/investment-vpn`, with private permissions.

The bot container uses host networking so it can reach that local proxy. Pass
`TELEGRAM_PROXY_URL=http://127.0.0.1:12335` as a container environment
variable. Verify proxy reachability with:

```sh
curl --proxy http://127.0.0.1:12335 \
  --max-time 15 -o /dev/null -w '%{http_code}\n' https://api.telegram.org/
```

HTTP 302 is a valid response for the Telegram API root. Verify the bot token
with `deploy/verify-telegram.py` from the image before changing polling bots.
Only one container may poll Telegram with the same token at a time.

## Switching containers

The current container was recreated after the mode change so its file mounts
point to the updated config. It uses host networking, with
`TELEGRAM_PROXY_URL=http://127.0.0.1:12335`, and mounts `.env`, `users.json`,
and `data`. A service-level verification found two real accounts and five
positions, with trading disabled; the portfolio handler successfully sent a
Telegram message. Keep the old project and database for rollback.
