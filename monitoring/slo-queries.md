# SLI/SLO — miklat-app (Фаза 5, Задание 5, п.5)

Реализация: `monitoring/slo-recording-rules.yaml` (`PrometheusRule`, namespace `observability`, подхватывается Prometheus Operator без специальных лейблов — `ruleSelectorNilUsesHelmValues: false` и `ruleNamespaceSelector: {}` в `monitoring/values-kube-prometheus-stack.yaml`, подтверждено чтением реального values-файла).

Обе SLI считаются один раз как recording rules и переиспользуются в трёх местах без дублирования формулы:
1. Панели дашборда `Application Overview` (`monitoring/dashboards/application-overview.yaml`).
2. Будущие алерты `HighErrorRate`/`HighLatencyP95` (Фаза 5, п.6 — следующий шаг).
3. Прямые PromQL-запросы для ручной диагностики/защиты проекта (ниже).

## SLI 1 — Availability

**Определение:** доля ответов backend-сервиса, НЕ являющихся 5xx, за скользящее окно 5 минут, по каждому сервису (`job`).

**SLO:** **>= 98%**.

**Обоснование порога:** не выбран произвольно. На момент реализации (04.09.2026) реальный error rate по всем 6 backend-сервисам `miklat-app` за 30 минут — **0%** (прямой запрос `sum(rate(http_requests_total{status="5xx"}[30m])) by (job)` вернул ПУСТОЙ результат — то есть ни одной ошибки 5xx зафиксировано не было). 98% — стандартный индустриальный порог с разумным запасом на редкие сбои/нагрузку, при этом достаточно строгий, чтобы реально ловить деградацию, а не быть тривиально всегда пройденным.

**Recording rules** (`monitoring/slo-recording-rules.yaml`, группа `miklat.slo.availability`):

```promql
# 1. Общий RPS по сервису
job:http_requests:rate5m = sum(rate(http_requests_total[5m])) by (job)

# 2. Error rate по сервису (с защитой от "пустой серии" при 0 ошибках —
#    реально подтверждено: sum(rate(...{status="5xx"}...)) при 0 ошибках
#    возвращает ПУСТОЙ vector, а не 0, поэтому нужна OR-заглушка)
job:http_requests_errors:rate5m =
  (sum(rate(http_requests_total{status="5xx"}[5m])) by (job) or (0 * job:http_requests:rate5m))

# 3. Error ratio
job:http_requests_errors:ratio5m = job:http_requests_errors:rate5m / job:http_requests:rate5m

# 4. Availability ratio (сама SLI, 0.0-1.0)
job:http_request_availability:ratio5m = 1 - job:http_requests_errors:ratio5m

# 5. SLO-индикатор (1 = соблюдён, 0 = нарушен) — читается панелью дашборда И будущим алертом
job:http_request_availability_slo:met = job:http_request_availability:ratio5m >= bool 0.98
```

**Ручная проверка (пример, живой запрос к Prometheus):**
```bash
curl -s 'http://localhost:9090/api/v1/query?query=job:http_request_availability:ratio5m' | python3 -m json.tool
```

**Реально подтверждено на живых данных (04.09.2026):** `job:http_request_availability:ratio5m = 1` (100%) у всех 6 сервисов; `job:http_request_availability_slo:met = 1` у всех 6.

## SLI 2 — Latency

**Определение:** 95-й перцентиль (p95) времени ответа backend-сервиса за скользящее окно 5 минут, по каждому сервису (`job`), на основе гистограммы `http_request_duration_highr_seconds` (мелкогранулированная, без разбивки по `handler` — точнее для общего SLI, чем `http_request_duration_seconds` с крупными бакетами 0.1/0.5/1.0s).

**SLO:** **p95 < 400ms**.

**Обоснование порога:** не выбран произвольно. Реальные текущие значения p95 (30-минутное окно, прямой запрос перед реализацией): 22-25мс у большинства сервисов (`miklat-gateway`/`miklat-comments`/`miklat-routes`/`miklat-walking-routes`), но заметно выше у `miklat-photos` (≈98мс) и `miklat-service` (≈93мс) — закономерно, т.к. первый обрабатывает загрузку файлов, второй — более тяжёлую бизнес-логику одобрения заявок на укрытие. 400мс даёт ~4x запас над текущим реальным пиком — не ловит обычные колебания нагрузки, но реально ловит деградацию производительности.

**Recording rules** (`monitoring/slo-recording-rules.yaml`, группа `miklat.slo.latency`):

```promql
job:http_request_duration_highr_seconds:p50_5m =
  histogram_quantile(0.5, sum(rate(http_request_duration_highr_seconds_bucket[5m])) by (le, job))

job:http_request_duration_highr_seconds:p95_5m =
  histogram_quantile(0.95, sum(rate(http_request_duration_highr_seconds_bucket[5m])) by (le, job))

job:http_request_duration_highr_seconds:p99_5m =
  histogram_quantile(0.99, sum(rate(http_request_duration_highr_seconds_bucket[5m])) by (le, job))

# SLO-индикатор (1 = соблюдён, 0 = нарушен) — читается панелью дашборда И будущим алертом
job:http_request_latency_slo:met = job:http_request_duration_highr_seconds:p95_5m < bool 0.4
```

**Ручная проверка:**
```bash
curl -s 'http://localhost:9090/api/v1/query?query=job:http_request_duration_highr_seconds:p95_5m' | python3 -m json.tool
```

**Реально подтверждено на живых данных (04.09.2026):** p95 по сервисам от 22мс (`miklat-comments`) до 147мс (`miklat-photos`, естественное колебание в пределах ожидаемого — всё равно далеко от порога 400мс); `job:http_request_latency_slo:met = 1` у всех 6 сервисов.

## Где эти recording rules используются

| Место | Файл | Как |
|---|---|---|
| Дашборд Application Overview, панель "Availability" | `monitoring/dashboards/application-overview.yaml`, панель id 3 | `100 * job:http_request_availability:ratio5m{job=~"$job"}` |
| Дашборд Application Overview, панель "Latency p50/p95/p99" | `monitoring/dashboards/application-overview.yaml`, панель id 4 | напрямую 3 recording rules по job |
| Дашборд Application Overview, панель "Availability SLO compliance" (новая) | `monitoring/dashboards/application-overview.yaml`, панель id 10 | `job:http_request_availability_slo:met{job=~"$job"}` |
| Дашборд Application Overview, панель "Latency SLO compliance" (новая) | `monitoring/dashboards/application-overview.yaml`, панель id 11 | `job:http_request_latency_slo:met{job=~"$job"}` |
| Алерт `HighErrorRate` (Фаза 5, п.6 — следующий шаг) | `monitoring/alerts/*.yaml` (ещё не создан) | будет читать `job:http_request_availability:ratio5m` / `job:http_request_availability_slo:met` |
| Алерт `HighLatencyP95` (Фаза 5, п.6 — следующий шаг) | `monitoring/alerts/*.yaml` (ещё не создан) | будет читать `job:http_request_duration_highr_seconds:p95_5m` / `job:http_request_latency_slo:met` |

Ни одна из этих формул не продублирована вручную в двух местах — везде используется имя recording rule, а не повторный `histogram_quantile(...)`/`sum(rate(...))`.