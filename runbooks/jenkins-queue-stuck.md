# Runbook: JenkinsQueueStuck

## Симптом

Алерт `JenkinsQueueStuck` (severity: warning) — `jenkins_queue_stuck_value` или `jenkins_queue_blocked_value` > 0 на протяжении 10+ минут. CI/CD pipeline, вероятно, не может обработать новые билды.

## Диагностика

1. Текущее состояние очереди (панель "Build queue state" в дашборде Jenkins & Delivery):
   ```bash
   curl -s 'http://localhost:9090/api/v1/query?query=jenkins_queue_size_value' | python3 -m json.tool
   curl -s 'http://localhost:9090/api/v1/query?query=jenkins_queue_blocked_value' | python3 -m json.tool
   curl -s 'http://localhost:9090/api/v1/query?query=jenkins_queue_stuck_value' | python3 -m json.tool
   ```
2. Состояние executor'ов/агентов по label (панель "Executors state by agent label"):
   ```bash
   curl -s 'http://localhost:9090/api/v1/query?query=default_jenkins_executors_busy' | python3 -m json.tool
   curl -s 'http://localhost:9090/api/v1/query?query=default_jenkins_executors_online' | python3 -m json.tool
   ```
3. Проверить реальные поды динамических агентов в неймспейсе `jenkins`:
   ```bash
   kubectl get pods -n jenkins -o wide
   kubectl describe pod -n jenkins <agent-pod-name>
   ```
4. Проверить, не уперлись ли динамические агенты в нехватку ресурсов ноды (тот же single-node сервер, что и весь остальной кластер — см. `node-not-ready-or-pressure.md`):
   ```bash
   kubectl describe node mbdai | grep -A5 "Allocated resources"
   ```
5. Посмотреть, какая именно job заблокирована и почему (через Jenkins UI, доступный по port-forward — Jenkins сознательно не выведен в интернет, см. п.1 плана Фазы 5):
   ```bash
   kubectl port-forward -n jenkins svc/jenkins 18080:8080
   # затем http://localhost:18080/queue/ — вкладка Build Queue покажет причину блокировки текстом
   ```

## Вероятные причины

- Динамический pod-агент (Kubernetes-плагин Jenkins) не может подняться — нехватка ресурсов ноды, `ImagePullBackOff` для образа агента, проблема с ServiceAccount/RBAC агента.
- Все executor'ы заняты одновременно (built-in имеет 0 executor'ов архитектурно — см. `claude/miklat-progress.md`, Фаза 5, дашборд Jenkins & Delivery — сборки идут только на build-agent/cd-agent/ci-agent).
- Проблема с NetworkPolicy/RBAC, блокирующая создание/коммуникацию агент-пода (прецедент уже был в этом проекте — Фаза 4, JNLP-порт; Фаза 5, scrape-порт).

## Устранение

1. Если агент не может подняться — `kubectl describe pod` покажет точную причину (Events); устранить конкретно (ресурсы/образ/RBAC).
2. Если ресурсы ноды исчерпаны — дождаться освобождения либо вручную остановить менее приоритетные job'ы.
3. Если проблема с NetworkPolicy — сверить `jenkins/network-policy.yaml` с реальными портами агента (тот же подход, что уже применялся дважды в этом проекте).
4. После устранения — подтвердить, что очередь очистилась (`jenkins_queue_stuck_value`/`jenkins_queue_blocked_value` вернулись к 0), алерт переходит в `resolved`.

## Evidence (Фаза 5, п.8)

Соответствует учению "задержать Jenkins agent" — заполняется реальными логами/скриншотами в `docs/evidence/task5/`, без изменения прав доступа (согласно требованию плана).