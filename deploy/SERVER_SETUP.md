# semenkohome deployment

The Telegram bot runs in the `investment-tbot` container from
`/home/feelwent/apps/investment-tbot`. Its Docker image is
`investment-tbot:stock-cards-20261008T174845Z` and its data directory is
`data/users/default`. Earlier bot containers remain stopped for rollback.

## Stock cards release, 9 October 2026

The verified image ID is
`sha256:60623404a44bfed7544450f87f892bba5f95b55cf3e22993158ca35c56a9cada`.
It was built from Git base `ff9000809fc62da25cc3e5f73506ff940e6c88f9` plus
the reviewed 55-file manifest. Those source files are applied to the server
checkout as uncommitted changes; Git HEAD remains at the base commit. The
release source and manifest are retained in
`runtime/releases/stock-cards-20261008T174845Z`.

The live database is at revision `f9a2b7c83e51`. The switch preserved all
previous fields and records in 29 existing tables. The stopped previous
container is `investment-tbot-prev-20261009T182607Z`; its image is
`investment-tbot:20261001-news-ca`. The fresh backup of SQLite and private
configuration is in
`runtime/releases/stock-cards-20261008T174845Z/deployment-20261009T182607Z/backup`.
Do not use `validation/data` from the release checks as live data.

All 410 tests passed inside the image before deployment. Live checks confirmed
the main process's Telegram proxy connection, valid bot token, inactive webhook,
zero restarts, registered `/stock` and `/notes` commands, and a successful
scheduled refresh of both current accounts. Real trading and automatic investing
remain disabled. No test messages or broker orders were sent. Stock tracking is
opt-in: portfolio -> account -> stock -> tracking. Reopen the Telegram menu with
`/start` to see the added Notes button. The existing local Qwen model is retained.

One initial switch was rolled back because a startup check required an INFO
message that Alembic's logging configuration suppresses. The check now uses the
main process's proxy socket and persisted scheduled-refresh state. The first
attempt's backup and failed-container data were retained. Existing Alembic
logging behavior remains unchanged; do not require that INFO message for health.
The deployment state, migration log, and read-only live verification are retained
beside the fresh backup.

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
database schema revision before the 9 October update was `d6e2a4b91c30`. The online SQLite backup
and matching `.env`/`users.json` copies from before the news migration have the
prefix `backups/pre_news_20260930T232006Z`; the backup revision is
`a3d9c8b7e621`. The migration was checked on a copy before updating the live
database.
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
and inactive webhook from the running container before changing polling bots.
Only one container may poll Telegram with the same token at a time.

On 1 October the `telegram-auto` route selected an unreachable node. The
working route was `node-3`; the private refresh script now checks candidate
nodes through a canary proxy and keeps the first route that reaches Telegram.
It runs from `/home/feelwent/.config/investment-vpn/refresh.py`, outside this
repository. Configuration backups remain in that private directory. Check the
timer result and proxy response after any subscription change.

## Switching containers

The current container uses the verified release described above. It uses host networking, with
`TELEGRAM_PROXY_URL=http://127.0.0.1:12335`, and mounts `.env`, `users.json`,
and `data`. An earlier service-level verification found two current broker accounts and
five positions. An older third account still exists in SQLite; monitoring
discovery excludes it. Trading remains disabled. `NEWS_LLM_ENABLED=true` uses
the local Qwen3.5-4B Q6_K. Monitoring alerts and the 09:00 Moscow digest are
enabled for the configured user with the default `owned` scope and 5% price
threshold. A clearly labeled test alert was delivered through
`MonitoringRunner._send_alerts` without writing a synthetic event to the live
database. Keep the stopped prior containers and database backup for rollback.
The model read timeout is 420 seconds, below the news job's 10-minute lease.
The first live batch completed all 14 account-scoped jobs without errors and
stored two news events. The source publications were already too old for
urgent delivery; they remain available to the morning digest.

## Rebuilding the image

From the server checkout, run `docker build -t investment-tbot:<tag> .` after
pulling a reviewed commit. The image build includes the verified root and
intermediate certificates in `deploy/certs` for the T-Bank package registry.
They are used only by pip during the build. Without the intermediate, a clean
build fails TLS verification because the registry does not send the complete
chain. Keep the existing running image until the new image has built and its
configuration has been checked.

The production container runs as `feelwent` (`1000:1000`) so SQLite and
other data files stay writable by the server user. The Dockerfile grants that
UID ownership of the image's app directory for legacy SQLite initialization
and file logging, and sets it as the runtime user. After building an image,
stop and retain the previous container, then start the new one with the same
mounts and proxy:

```sh
cd /home/feelwent/apps/investment-tbot
IMAGE_TAG=investment-tbot:next-reviewed-release
docker build -t "$IMAGE_TAG" .
docker stop --timeout 20 investment-tbot
docker rename investment-tbot "investment-tbot-prev-$(date +%Y%m%d%H%M%S)"
docker run -d --name investment-tbot --network host --user 1000:1000 \
  --restart unless-stopped \
  -e TELEGRAM_PROXY_URL=http://127.0.0.1:12335 \
  --mount type=bind,source="$PWD/.env",target=/opt/tbot/.env,readonly \
  --mount type=bind,source="$PWD/users.json",target=/opt/tbot/users.json,readonly \
  --mount type=bind,source="$PWD/data",target=/opt/tbot/data \
  "$IMAGE_TAG"
```

Check `docker inspect investment-tbot` for `Config.User=1000:1000` and a
running container before removing any prior image or container.
