# Перенос Tbot на ноутбук с Ubuntu

## Код и конфигурация

Передавайте **Git bundle** из каталога рядом с `Tbot`. Создайте его из текущей ветки: `git bundle create ../Tbot-ubuntu.bundle telegram-proxy-polling-recovery`. Bundle содержит историю и текущий коммит, поэтому после переноса можно продолжать разработку и делать новые коммиты. Проверка на Ubuntu: `git bundle verify Tbot-ubuntu.bundle`, затем `git clone Tbot-ubuntu.bundle Tbot`.

`.env`, `users.json`, базы SQLite, окружение Python и логи в bundle не входят. Передайте `.env` и `users.json` отдельным защищённым способом. Если нужна существующая история портфелей, остановите старый бот и отдельно перенесите файлы из `data/users/` (включая `*.db`) в те же относительные пути. Копировать работающую SQLite-базу нельзя: сначала остановите процесс или сделайте корректный backup SQLite. Не запускайте одновременно два экземпляра с одним `BOT_TOKEN`: Telegram polling конфликтует. Не загружайте секреты и базы в Git.

## Установка на Ubuntu

Нужны Git, Python 3.12, модуль `venv` для него и доступ к официальному Python-репозиторию T-Bank, указанному в `requirements-base.txt`. Работайте из корня клонированного проекта:

```bash
bash scripts/bootstrap-ubuntu.sh
```

Скрипт создаёт `.venv`, устанавливает зависимости и создаёт только отсутствующие `.env` и `users.json` из примеров. Замените шаблонные `BOT_TOKEN`, `telegram_chat_id` и брокерские токены. Проверьте `APP_MODE="sandbox"`, `ALLOW_PROD_TRADING="false"`, `SSL_TBANK_VERIFY="True"`; для новой разработки оставьте автоматическое исполнение заявок отключённым. Установите права `chmod 600 .env users.json`.

Проверка и первый запуск:

```bash
.venv/bin/python -m unittest discover -q
.venv/bin/python app/run.py
```

При первом запуске выполняется миграция каждой пользовательской базы, включая таблицы мониторинга. Подписки на оповещения выключены по умолчанию; включайте их в Telegram через `/monitor`. Перед обновлением работающего экземпляра остановите его и сохраните резервную копию баз.

## Работа в фоне и дальнейшая разработка

Для постоянной работы скопируйте `deploy/tbot.service.example` в `~/.config/systemd/user/tbot.service`, замените `REPLACE_WITH_ABSOLUTE_PROJECT_PATH` на фактический абсолютный путь и выполните:

```bash
systemctl --user daemon-reload
systemctl --user enable --now tbot.service
systemctl --user status tbot.service
journalctl --user -u tbot.service -f
```

Чтобы пользовательский сервис продолжал работать после выхода из сеанса, администратор может включить linger: `sudo loginctl enable-linger "$USER"`. Для обновления кода остановите сервис, сохраните базы, получите новые коммиты через Git, установите обновлённые зависимости, запустите тесты и снова запустите сервис. История Git из bundle позволяет создать на ноутбуке собственную ветку и позже добавить нужный remote.

Docker Compose также подготовлен: после создания `.env` и `users.json` можно выполнить `docker compose up --build -d`. Базы в `data/users/` сохраняются на хосте. Для активной разработки удобнее установка в `.venv`, описанная выше.
