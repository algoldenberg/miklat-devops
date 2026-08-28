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
# non-root: nginx:alpine уже включает пользователя nginx, конфиг ниже слушает
# порт 8080 (не 80), чтобы не требовать привилегий на bind.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

RUN sed -i 's/listen\s*80;/listen 8080;/' /etc/nginx/conf.d/default.conf \
    && chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx/conf.d \
    && sed -i 's/^pid\s*\/var\/run\/nginx.pid;/pid \/tmp\/nginx.pid;/' /etc/nginx/nginx.conf \
    && touch /tmp/nginx.pid && chown nginx:nginx /tmp/nginx.pid

USER nginx
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
