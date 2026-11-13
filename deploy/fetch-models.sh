#!/bin/bash
# Кладёт веса BERT в каталог $1/rosberta, если их там ещё нет. Веса не публичные и в git не хранятся;
# их один раз загружают в «Package Registry» проекта GitLab (deploy/upload-bert-weights.sh), а отсюда скачивает ВМ.
set -euo pipefail
DEST="${1:?укажите каталог для моделей}/rosberta"
VERSION="${BERT_PACKAGE_VERSION:-1.0.0}"
FILES="config.json model.safetensors tokenizer.json tokenizer_config.json vocab.json merges.txt special_tokens_map.json"

if [ -f "$DEST/config.json" ] && [ -f "$DEST/model.safetensors" ] && { [ -f "$DEST/tokenizer.json" ] || [ -f "$DEST/vocab.json" ]; }; then
    echo "Веса BERT уже на месте: $DEST"
    exit 0
fi

echo "Веса BERT не найдены в $DEST — скачиваю из пакетов GitLab (версия $VERSION)"
install -d -m 755 "$DEST"
for file in $FILES; do
    curl -fL --retry 3 --header "JOB-TOKEN: ${CI_JOB_TOKEN:?нет CI_JOB_TOKEN}" \
        -o "$DEST/$file.part" "$CI_API_V4_URL/projects/$CI_PROJECT_ID/packages/generic/rosberta/$VERSION/$file"
    mv "$DEST/$file.part" "$DEST/$file"
done
echo "Веса BERT загружены в $DEST"
