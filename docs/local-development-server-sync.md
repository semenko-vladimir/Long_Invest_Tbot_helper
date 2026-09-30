# Локальная разработка и передача коммитов на сервер

Рабочий репозиторий на ноутбуке: `C:\Users\vladimir\Desktop\Investment\Tbot`, ветка
`telegram-proxy-polling-recovery`. Рабочая копия запущенного бота на сервере:
`semenkohome:/home/feelwent/apps/investment-tbot` в той же ветке. Выполняйте
команды Git из этих каталогов, а не из родительской папки `Investment`.

На 30 сентября 2026 года серверная ветка находится на `49064ca`, а локальная
ветка уже содержит следующие коммиты. На сервере есть незакоммиченные исходники,
поэтому при первой передаче их нужно сохранить в Git stash. Серверный `origin`
указывает на разовый bundle, а не на живой Git remote: `git pull` здесь не
обновит проект с ноутбука.

## На ноутбуке: после доработки

```powershell
cd C:\Users\vladimir\Desktop\Investment\Tbot
.\venv312\Scripts\python.exe -m unittest discover -q
git status --short
git add -p
# Новые файлы добавьте отдельно: git add путь\к\файлу
git diff --cached --check
git diff --cached --name-only
git commit -m "feat: add local news analysis"

git bundle create ..\Tbot-update.bundle telegram-proxy-polling-recovery
git bundle verify ..\Tbot-update.bundle
scp ..\Tbot-update.bundle semenkohome:/tmp/Tbot-update.bundle
```

Перед коммитом проверьте список добавленных файлов. `.env`, `users.json`, базы
данных, токены, отчёты и резервные копии не должны попадать в Git. Текст
сообщения коммита замените на описание фактического изменения.

## На сервере: первая передача

```bash
ssh semenkohome
cd /home/feelwent/apps/investment-tbot
git status --short --branch
git stash push -u -m "server changes before laptop sync"
git fetch /tmp/Tbot-update.bundle telegram-proxy-polling-recovery
git merge --ff-only FETCH_HEAD
git status --short --branch
git rev-parse --short HEAD
git stash list
```

`git stash` сохраняет текущие серверные правки, включая неотслеживаемые файлы.
Не применяйте stash автоматически: часть этих файлов уже вошла в локальные
коммиты, а несколько серверных версий отличаются. Если `merge --ff-only`
остановится, не используйте `reset --hard`; сначала сравните историю веток.
Игнорируемые рабочие данные (`.env`, `users.json`, `data/users/`) Git не трогает.

При следующих передачах из чистой серверной рабочей копии повторяйте только
`git fetch` и `git merge --ff-only`. Коммит создаётся на ноутбуке; сервер
получает тот же SHA. Обновление Git на сервере само по себе не пересобирает
образ и не перезапускает работающий контейнер `investment-tbot`.

Не используйте `scripts/sync-to-server.ps1` для текущего бота: он нацелен на
старый путь `/home/feelwent/projects/Tbot`, контейнер `tbot` и прежний HTTP
терминал.
