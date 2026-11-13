# syntax=docker/dockerfile:1
#
# Образ "web": nginx со сборкой игры (Unity WebGL из папки frontend/) и прокси к API.
# nginx-unprivileged работает не от root (пользователь nginx) и слушает порт 8080.
# Контекст сборки — корень репозитория (так видны и web/, и frontend/): docker build -f web/Dockerfile .

FROM nginxinc/nginx-unprivileged:1.27-alpine

COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY frontend/ /usr/share/nginx/html/

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:8080/StreamingAssets/config.json || exit 1
