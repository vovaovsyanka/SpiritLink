#!/bin/bash
# Один раз, со своего компьютера (Git Bash): загружает веса BERT в «Package Registry» проекта GitLab.
#   deploy/upload-bert-weights.sh <токен> <ID проекта> [папка с весами]
# Токен — Personal Access Token с правом api (GitLab -> Preferences -> Access tokens). ID проекта — на главной странице проекта.
# Токен никуда не сохраняется; не вставляйте его в файлы репозитория.
set -euo pipefail
TOKEN="${1:?укажите Personal Access Token}"
PROJECT_ID="${2:?укажите ID проекта GitLab}"
SRC="${3:-bek-project/models/rosberta}"
GITLAB="${GITLAB_URL:-https://gitlab.kseoni.ch}"
VERSION="${BERT_PACKAGE_VERSION:-1.0.0}"

for file in config.json model.safetensors tokenizer.json tokenizer_config.json vocab.json merges.txt special_tokens_map.json; do
    echo "Загружаю $file ..."
    curl -fS --header "PRIVATE-TOKEN: $TOKEN" --upload-file "$SRC/$file" \
        "$GITLAB/api/v4/projects/$PROJECT_ID/packages/generic/rosberta/$VERSION/$file"
    echo
done
echo "Готово. Пакет: Deploy -> Package registry в проекте GitLab."
