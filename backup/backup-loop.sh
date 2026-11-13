#!/bin/sh
# Расписание резервного копирования: копия при старте контейнера и затем каждые BACKUP_INTERVAL_HOURS часов.
# Контейнер живёт постоянно (restart: unless-stopped), так что расписание переживает перезапуск сервера.
set -u
while true; do
    /bin/sh /backup/backup.sh || echo "ОШИБКА: резервная копия не создана"
    sleep $((BACKUP_INTERVAL_HOURS * 3600))
done
