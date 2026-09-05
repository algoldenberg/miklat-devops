#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Точечные правки README.md: добавление метрик frontend (04.09.2026) в уже
существующую секцию "Kubernetes: Мониторинг (Задание 5)" + документирование
двух реальных находок (баг CI-детектора при многокоммитных пушах,
NetworkPolicy реально enforce'ится — блокировка порта 9113).

Запуск из корня репозитория:
    python3 patch_readme.py

Каждая замена проверяется на то, что старый текст встречается РОВНО один раз
(иначе скрипт останавливается и ничего не пишет на диск) — чтобы случайно не
затронуть что-то ещё и не получить тихий no-op.
"""
import sys

PATH = "README.md"

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

replacements = []

# 1) Таблица файлов monitoring/ — уточнить состав 7 ServiceMonitor'ов
replacements.append((
    "| `service-monitors/miklat-app-services.yaml` | `ServiceMonitor` на 7 портов приложения (`namespace: miklat-app`, 15s interval) |",
    "| `service-monitors/miklat-app-services.yaml` | `ServiceMonitor` на 7 портов приложения — 6 backend (`targetPort: 8000`) + `frontend` (именованный порт `metrics`, добавлен 04.09.2026) (`namespace: miklat-app`, 15s interval) |",
))

# 2) "Дополнительно" абзац — добавить упоминание файлов, изменённых при добавлении метрик frontend
replacements.append((
    "Дополнительно (интеграция с CI/CD, Задание 4 файлы обновлены, не пересозданы): `ci/validate_monitoring.py` (новый), `Jenkinsfile-ci` (новая стадия `Validate monitoring manifests`), `Jenkinsfile-cd` (новая стадия `Monitoring health gate`), `jenkins/network-policy.yaml` (добавлено правило egress для `cd-agent` → `observability`). А также `runbooks/*.md` — 6 файлов, по одному на каждый алерт (см. ниже).",
    "Дополнительно (интеграция с CI/CD, Задание 4 файлы обновлены, не пересозданы): `ci/validate_monitoring.py` (новый), `Jenkinsfile-ci` (новая стадия `Validate monitoring manifests`), `Jenkinsfile-cd` (новая стадия `Monitoring health gate`), `jenkins/network-policy.yaml` (добавлено правило egress для `cd-agent` → `observability`). А также `runbooks/*.md` — 6 файлов, по одному на каждый алерт (см. ниже).\n\nПозже, при добавлении метрик frontend (04.09.2026): `helm/miklat-app/templates/frontend.yaml` (добавлен sidecar-контейнер `nginx-prometheus-exporter`), `Jenkinsfile-ci` (исправлена логика детектора изменившихся сервисов — см. находки ниже), `Jenkinsfile-cd` (health-gate расширен на `frontend`), `monitoring/network-policy.yaml` (добавлен порт `9113` в `allow-prometheus-egress` — см. находки ниже).",
))

# 3) Абзац про frontend в "Что мониторится" — было "отложено", стало "сделано"
replacements.append((
    "`frontend` (nginx) метрики в этой итерации не инструментированы — сознательное решение: ни SLI/SLO, ни один из 6 обязательных алертов, ни 2 из 3 дашбордов на frontend не завязаны (SLO строится на API backend-сервисов), отложено на конец Фазы 5 (нужен отдельный `nginx-prometheus-exporter`-сайдкар).",
    "`frontend` (nginx) — метрики добавлены отдельным шагом в конце Фазы 5 (04.09.2026, после основного объёма работ по Заданию 5): sidecar-контейнер `nginx-prometheus-exporter:1.5.1` в том же поде читает `stub_status` (`frontend/nginx.conf`, `location /nginx_status`, доступ только с `127.0.0.1` — тот же под) и отдаёт `/metrics` в формате Prometheus на порту `9113`; `ServiceMonitor` (в отличие от 6 backend-сервисов) ссылается на порт по имени (`port: metrics`), т.к. Service `frontend` — единственный, кто именует свои порты (у него их два: `http`/`metrics`). Ни SLI/SLO, ни один из 6 обязательных алертов, ни 2 из 3 дашбордов на frontend по-прежнему не завязаны (SLO строится на API backend-сервисов) — метрики frontend дают только базовую видимость (`up`, счётчики соединений/запросов nginx), без прикладной латентности (см. ограничение `nginx-prometheus-exporter` ниже).",
))

# 4) CD health-gate — было "пропускается для frontend", стало "сокращённая проверка"
replacements.append((
    "- **CD** (`Jenkinsfile-cd`, стадия `Monitoring health gate`, после `Smoke test`, пропускается для `frontend`): пауза 30с (2 цикла scrape), затем через Prometheus API проверяются `up{job=<service>}==1`, `job:http_request_availability:ratio5m >= 0.98`, `job:http_request_duration_highr_seconds:p95_5m < 0.4` — те же recording rules из SLI/SLO, без дублирования формул. Провал любой проверки — `error()`, автоматически запускающий уже существующий `post{failure}` `helm rollback` (новой rollback-логики не потребовалось).",
    "- **CD** (`Jenkinsfile-cd`, стадия `Monitoring health gate`, после `Smoke test`): пауза 30с (2 цикла scrape), затем через Prometheus API проверяются `up{job=<service>}==1`, `job:http_request_availability:ratio5m >= 0.98`, `job:http_request_duration_highr_seconds:p95_5m < 0.4` — те же recording rules из SLI/SLO, без дублирования формул. Провал любой проверки — `error()`, автоматически запускающий уже существующий `post{failure}` `helm rollback` (новой rollback-логики не потребовалось). Для `frontend` (04.09.2026) стадия не пропускается, а сокращена: проверяется только `up{job=\"frontend\"}==1` — recording rules availability/latency построены на гистограмме `http_request_duration_seconds` из `prometheus-fastapi-instrumentator`, которой у nginx-экспортёра нет (он отдаёт только счётчики соединений/запросов, без прикладной латентности запроса).",
))

# 5) Trade-offs — было "отложено", стало "сделано, с оговоркой об ограничении"
replacements.append((
    "- **Метрики `frontend` (nginx)** — сознательно отложены на конец Фазы 5 (нужен `nginx.conf`/Dockerfile фронтенда для сайдкара `nginx-prometheus-exporter`), ни один обязательный SLI/SLO/алерт/дашборд от них не зависит.",
    "- **Метрики `frontend` (nginx)** — реализованы (см. выше) в упрощённом виде: только `up` и nginx-счётчики соединений/запросов, без прикладной латентности (нет `http_request_duration_seconds` — это метрика `prometheus-fastapi-instrumentator`, которой во frontend нет и не может быть без переписывания статики на приложение); ни один обязательный SLI/SLO/алерт/дашборд от этого не зависит — они и так были рассчитаны только на backend.",
))

# 6) Новый подраздел с двумя находками — вставляется после подраздела NetworkPolicy,
#    перед "### Известные компромиссы (trade-offs) и открытые пункты"
anchor = "### Известные компромиссы (trade-offs) и открытые пункты\n\n- **Метрики `frontend` (nginx)**"
new_subsection = """### Находки при внедрении метрик frontend (04.09.2026)

Обе находки — реальные, обнаруженные не при планировании, а по факту сбоя, с диагностикой и исправлением, применённым на кластере.

**1. Баг детектора изменившихся сервисов в CI при многокоммитных пушах (`Jenkinsfile-ci`).** Стадия `Detect changed services` сравнивала `git diff --name-only HEAD~1 HEAD` — то есть только последний коммит пуша со своим непосредственным родителем. При пуше из нескольких коммитов это могло молча пропустить сервис, если путь к нему менялся в одном из более ранних коммитов пуша, а не в последнем — ровно так был потерян билд `frontend/nginx.conf` в рамках этой же работы. Исправлено: базой для diff теперь служит `env.GIT_PREVIOUS_SUCCESSFUL_COMMIT` (переменная плагина Jenkins Git — SHA последнего успешного билда этого job'а), с фолбэком на `HEAD~1` (самый первый билд) и далее на «собрать все сервисы», если базовый коммит недостижим при shallow-клоне.

**2. `NetworkPolicy` в кластере реально enforce'ится — ещё одно, второе по счёту подтверждение (после инцидента с JNLP-портом Jenkins, Задание 4).** После деплоя sidecar-экспортёра `up{job="frontend"}` стабильно возвращал `0` с `lastError: connection refused`, хотя под, эндпоинт и `curl` изнутри того же namespace и из `observability` через debug-под — всё работало. Причина: `allow-prometheus-egress` в `monitoring/network-policy.yaml` разрешал egress из `observability` в `miklat-app` только на порт `8000` (под 6 существующих backend-сервисов) — порт `9113` нового экспортёра был не указан и потому блокировался. Исправлено добавлением `port: 9113` в то же правило, применено `kubectl apply -f monitoring/network-policy.yaml`, после чего `up{job="frontend"}` стал `1`. Формулировки про «flannel не enforce'ит NetworkPolicy» в разделах Security Заданий 3 и 4 остаются как есть до перевода README в Фазе 6 (см. оговорку выше) — эта находка лишь ещё раз подтверждает то же исправление понимания, что уже отражено в этом разделе.

### Известные компромиссы (trade-offs) и открытые пункты

- **Метрики `frontend` (nginx)**"""

replacements.append((anchor, new_subsection))

errors = []
for i, (old, new) in enumerate(replacements, start=1):
    count = content.count(old)
    if count != 1:
        errors.append((i, count))
    else:
        content = content.replace(old, new)

if errors:
    print("ОШИБКА: не применено. Проблемные замены (номер, найдено раз):")
    for i, count in errors:
        print(f"  #{i}: найдено {count} раз(а) (ожидалось 1)")
    print("\nФайл НЕ изменён. Пришли мне вывод этого скрипта — разберёмся.")
    sys.exit(1)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

print(f"OK: применено {len(replacements)} правок в {PATH}")