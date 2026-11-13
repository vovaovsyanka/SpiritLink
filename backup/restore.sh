#!/bin/sh
# Восстановление базы из копии:  restore.sh /backups/spiritlink-20261101-120000.dump
# --clean --if-exists: перед загрузкой удаляет существующие таблицы, поэтому текущие данные заменяются данными из копии.
# Приложение на время восстановления лучше остановить (см. docs/deploy/README.md, раздел «Резервные копии»).
set -eu

[ $# -eq 1 ] || { echo "Использование: restore.sh <файл.dump>"; exit 1; }
[ -f "$1" ] || { echo "Нет файла $1"; exit 1; }

pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error -d "$PGDATABASE" "$1"
echo "База $PGDATABASE восстановлена из $1"
