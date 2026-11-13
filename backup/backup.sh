#!/bin/sh
# Одна резервная копия базы. Подключение берётся из переменных PGHOST, PGUSER, PGPASSWORD, PGDATABASE.
#   -Fc — "custom"-формат pg_dump: сжатый, и из него pg_restore умеет восстанавливать выборочно
set -eu

DIR=/backups
OUT="$DIR/$PGDATABASE-$(date +%Y%m%d-%H%M%S).dump"

# Сначала пишем во временный файл: оборвавшийся дамп не должен выглядеть как годная копия
pg_dump -Fc -f "$OUT.part"
mv "$OUT.part" "$OUT"
echo "Резервная копия: $OUT ($(du -h "$OUT" | cut -f1))"

# Храним только BACKUP_KEEP последних копий, остальные удаляем
ls -1t "$DIR"/*.dump 2>/dev/null | tail -n +"$((BACKUP_KEEP + 1))" | xargs -r rm -f
