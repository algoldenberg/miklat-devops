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

## Устранение

1. Если причина — плохой релиз: выполнить rollback через Jenkins CD pipeline (`Jenkinsfile-cd`, откат на предыдущий известный здоровый image digest) или вручную:
   ```bash
   kubectl rollout undo deployment/<service-name> -n miklat-app
   ```
2. Если причина — внешняя зависимость: проверить её доступность отдельно, задокументировать инцидент, при необходимости включить деградированный режим (если предусмотрен).
3. После устранения — подтвердить восстановление через ту же recording rule (`job:http_request_availability:ratio5m` должна вернуться к ~1.0) и через панель дашборда, дождаться перехода алерта в Alertmanager из `firing` в `resolved`.

## Evidence (учение отказа, Фаза 5 п.8)

Будет заполнено при реальном учении "управляемо вернуть 5xx" — см. `docs/evidence/task5/`.