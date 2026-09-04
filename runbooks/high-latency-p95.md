# Runbook: HighLatencyP95

## Симптом

Алерт `HighLatencyP95` (severity: warning) — p95 latency сервиса `{{ $labels.job }}` выше 400мс (SLO, `monitoring/slo-queries.md`) на протяжении 5+ минут. Источник — recording rule `job:http_request_duration_highr_seconds:p95_5m` (`monitoring/slo-recording-rules.yaml`).

## Диагностика

1. Посмотреть, какой сервис и насколько превышен порог (панель "Latency p50/p95/p99 by service" и "Latency SLO compliance" в дашборде Application Overview):
   ```bash
   curl -s 'http://localhost:9090/api/v1/query?query=job:http_request_duration_highr_seconds:p95_5m' | python3 -m json.tool
   ```
2. Найти конкретный медленный эндпоинт (панель "p95 latency by endpoint (handler)"):
   ```bash
   curl -s --data-urlencode 'query=histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, job, handler))' 'http://localhost:9090/api/v1/query' | python3 -m json.tool
   ```
3. Проверить CPU/память пода — латентность часто следствие throttling, а не логики (панель "CPU throttling by pod" в дашборде Kubernetes/Cluster):
   ```bash
   curl -s --data-urlencode 'query=sum(rate(container_cpu_cfs_throttled_periods_total{namespace="miklat-app",container!=""}[5m])) by (pod)' 'http://localhost:9090/api/v1/query' | python3 -m json.tool
   ```
4. Для `miklat-routes`/`miklat-walking-routes` — проверить время ответа внешнего OSRM (латентность может быть не в самом сервисе, а в зависимости).
5. Для `miklat-photos` — проверить размер загружаемых файлов/нагрузку на диск (обработка изображений обычно самая тяжёлая операция в проекте — см. `monitoring/slo-queries.md`, обоснование порога).

## Вероятные причины

- CPU throttling из-за заниженного `limits.cpu` при возросшей нагрузке.
- Деградация внешней зависимости (OSRM, БД).
- Утечка ресурсов/деградация после релиза — сравнить с `app_info` (какая версия сейчас отвечает).

## Устранение

1. Если throttling — рассмотреть увеличение `resources.limits.cpu` в Helm values сервиса (`services/*/values.yaml` или аналог) и передеплоить.
2. Если внешняя зависимость — задокументировать, при системной деградации рассмотреть таймауты/circuit breaker (вне текущего скоупа проекта, отметить как улучшение).
3. Если следствие плохого релиза — rollback (`kubectl rollout undo deployment/<service-name> -n miklat-app`), как в runbook `high-error-rate.md`.
4. Подтвердить восстановление через `job:http_request_duration_highr_seconds:p95_5m` и переход алерта в `resolved`.

## Evidence (Фаза 5, п.8)

Будет заполнено при реальном учении отказа, если применимо (не входит в список 4 обязательных учений плана, но может быть продемонстрировано дополнительно).