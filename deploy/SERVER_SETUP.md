# semenkohome deployment

The Telegram bot runs in the `investment-tbot` container from
`/home/feelwent/apps/investment-tbot`. Its Docker image is
`investment-tbot:20261001-news-ca` and its data directory is
`data/users/default`. Earlier bot containers remain stopped for rollback.

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
current database schema revision is `d6e2a4b91c30`. The online SQLite backup
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

The current container uses the deployed Git HEAD. It uses host networking, with
`TELEGRAM_PROXY_URL=http://127.0.0.1:12335`, and mounts `.env`, `users.json`,
and `data`. A service-level verification found two current broker accounts and
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
IMAGE_TAG=investment-tbot:20261001-news-ca
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
