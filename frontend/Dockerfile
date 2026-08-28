# Multi-stage: собираем статику Vite-сборкой, отдаём через nginx —
# тот же принцип, что запланирован в Ansible playbooks/nginx.yml для Фазы 2
# (nginx на frontend, reverse proxy "/api/*" -> backend), только здесь прокси
# настроен на miklat-gateway (см. nginx.conf).

FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
# non-root: nginx:alpine уже включает пользователя nginx. Порт (8080) задан
# прямо в nginx.conf.
#
# nginx-main.conf целиком заменяет /etc/nginx/nginx.conf из базового образа —
# единственное отличие от оригинала: pid переопределён на /tmp/nginx.pid
# (см. комментарий в самом файле). Раньше это пытались патчить через `sed`
# поверх дефолтного nginx.conf, но в этом образе sed — это busybox sed, а не
# GNU sed: `\s` он молча не подставляет (без ошибки — просто no-op), из-за
# чего pid оставался на дефолтном /run/nginx.pid, недоступном для записи
# непривилегированному пользователю nginx — сервис падал в restart-loop
# ("Permission denied"). Тот же урок, что и с MSYS-путями на Windows: не
# полагаться на sed-эвристики, которые работают в одном окружении и молча
# ничего не делают в другом — теперь конфиг просто полностью свой, без
# патчинга на этапе сборки.
COPY nginx-main.conf /etc/nginx/nginx.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx/conf.d

USER nginx
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
