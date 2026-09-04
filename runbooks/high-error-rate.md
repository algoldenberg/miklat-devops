# Runbook: HighErrorRate

## Симптом

Алерт `HighErrorRate` (severity: critical) — availability сервиса `{{ $labels.job }}` ниже 98% (SLO, `monitoring/slo-queries.md`) на протяжении 5+ минут. Источник — recording rule `job:http_request_availability:ratio5m` (`monitoring/slo-recording-rules.yaml`).

## Диагностика

1. Посмотреть, какой именно сервис и насколько ниже порога (панель "Availability (% non-5xx) by service" и "Availability SLO compliance" в дашборде Application Overview, uid `miklat-application-overview`):
   ```bash
   curl -s 'http://localhost:9090/api/v1/query?query=job:http_request_availability:ratio5m' | python3 -m json.tool
   ```
2. Понять, какие именно эндпоинты дают 5xx — по хендлеру:
   ```bash
   curl -s --data-urlencode 'query=sum(rate(http_requests_total{status="5xx"}[5m])) by (job, handler)' 'http://localhost:9090/api/v1/query' | python3 -m json.tool
   ```
3. Посмотреть логи пода(ов) проблемного сервиса за последние 10-15 минут:
   ```bash
   kubectl logs -n miklat-app -l app=<service-name> --since=15m --tail=200
   ```
4. Проверить, не было ли недавнего деплоя (алерт может быть следствием плохого релиза — коррелировать с `app_info{job="<service>"}` и временем последнего деплоя из Jenkins).
5. Проверить состояние подов и их зависимостей (например, RDS/внешние сервисы, если сервис зависит от БД):
   ```bash
   kubectl get pods -n miklat-app -l app=<service-name> -o wide
   kubectl describe pod -n miklat-app <pod-name>
   ```

## Вероятные причины

- Плохой релиз (баг в новом коде, обрабатывающий запросы с ошибкой).
- Проблема у зависимости (БД недоступна, таймаут внешнего API — например OSRM для `miklat-routes`/`miklat-walking-routes`).
- Нехватка ресурсов (под падает под нагрузкой, OOMKilled — см. также runbook `node-not-ready-or-pressure.md`).
- Сломан прокси-адрес одной из downstream-зависимостей у `miklat-gateway` (env-переменная `MIKLAT_*_URL`) — сам gateway при этом остаётся `Ready`/`up`, поэтому алерт срабатывает без сопутствующего `PrometheusTargetDown` (см. Evidence ниже — именно так был воспроизведён реальный отказ в учении).

## Устранение

1. Если причина — плохой релиз: выполнить rollback через Jenkins CD pipeline (`Jenkinsfile-cd`, откат на предыдущий известный здоровый image digest) или вручную:
   ```bash
   kubectl rollout undo deployment/<service-name> -n miklat-app
   ```
2. Если причина — внешняя зависимость: проверить её доступность отдельно, задокументировать инцидент, при необходимости включить деградированный режим (если предусмотрен).
3. После устранения — подтвердить восстановление через ту же recording rule (`job:http_request_availability:ratio5m` должна вернуться к ~1.0) и через панель дашборда, дождаться перехода алерта в Alertmanager из `firing` в `resolved`.

   **Важно (подтверждено реальным учением ниже):** `job:http_request_availability:ratio5m` — скользящее 5-минутное окно. Сразу после устранения причины значение может ещё какое-то время оставаться заниженным (в окне ещё сидят накопленные ошибки) — это не значит, что фикс не сработал; нужно подождать, пока полное окно "очистится" (обычно ещё 4-5 минут), и только потом делать вывод.

## Evidence (учение отказа, Фаза 5 п.8)

Реальное, управляемое учение проведено 04.09.2026 на `mbdai`. Полный ход, все команды и сырой вывод — `docs/evidence/task5/failure-drill-1-high-error-rate.txt`. Кратко:

- **Поломка:** `kubectl set env deployment/miklat-gateway -n miklat-app MIKLAT_COMMENTS_URL=http://miklat-comments-broken.miklat-app.svc.cluster.local:8000` — подмена одного из проксируемых адресов `miklat-gateway` на несуществующий (выбрано намеренно вместо поломки БД/S3/SNS — иначе упал бы `/ready` целевого сервиса и сработал бы `PrometheusTargetDown`, а не `HighErrorRate`).
- **Нагрузка:** 45 запросов к `GET /miklats/1/comments` с интервалом 8с (~6 минут) — все 45 вернули реальный `503`.
- **Подтверждено сработавшим тремя независимыми способами:** `job:http_request_availability:ratio5m{job="miklat-gateway"}` = `0.6907` (69%, порог 0.98); состояние правила в Prometheus — `"state": "firing"`; Alertmanager реально получил алерт (`GET /api/v2/alerts`) с `severity: critical`, `receivers: [{"name":"demo-webhook"}]`, `runbook_url` — ссылкой на этот файл.
- **Устранение:** `kubectl rollout undo deployment/miklat-gateway -n miklat-app` — откат на предыдущую ревизию (не повторный `kubectl set env`, чтобы не потерять оригинальную ссылку `configMapKeyRef`). Реальный запрос после отката → `200`.
- **Снятие алерта подтверждено, не просто предположено:** через 90с после отката `ratio5m` ещё оставался заниженным (скользящее окно, накопленные ошибки ещё в нём) — через 5 минут: `ratio5m = 1`, `state: "inactive"`, Alertmanager — пустой список.

Прод `shelternearyou.online` не затрагивался — менялся только `env` `miklat-gateway` в изолированном namespace `miklat-app`.