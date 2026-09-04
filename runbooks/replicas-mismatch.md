# Runbook: ReplicasMismatch

## Симптом

Алерт `ReplicasMismatch` (severity: warning) — у Deployment `{{ $labels.deployment }}` в namespace `{{ $labels.namespace }}` число доступных реплик меньше желаемого на протяжении 10+ минут (окно намеренно шире типичного rollout, чтобы не ловить нормальный процесс деплоя).

## Диагностика

1. Посмотреть текущее состояние всех Deployment'ов в затронутом namespace (панель "Deployment replicas: desired vs available" в дашборде Kubernetes/Cluster):
   ```bash
   kubectl get deployments -n <namespace>
   curl -s --data-urlencode 'query=kube_deployment_spec_replicas{namespace="<namespace>"}' 'http://localhost:9090/api/v1/query' | python3 -m json.tool
   curl -s --data-urlencode 'query=kube_deployment_status_replicas_available{namespace="<namespace>"}' 'http://localhost:9090/api/v1/query' | python3 -m json.tool
   ```
2. Посмотреть под(ы), которые не готовы:
   ```bash
   kubectl get pods -n <namespace> -l app=<deployment-name> -o wide
   kubectl describe pod -n <namespace> <pod-name>
   ```
3. Проверить события namespace на предмет ошибок планирования/образов:
   ```bash
   kubectl get events -n <namespace> --sort-by='.lastTimestamp' | tail -30
   ```
4. Частые причины в этом кластере (single-node k3s, `mbdai`, разделяемый с продакшн `shelternearyou.online`):
   - Нехватка памяти/CPU на единственной ноде (см. также `node-not-ready-or-pressure.md`).
   - `ImagePullBackOff` — проблема с registry или тегом образа после релиза.
   - Failing readiness/liveness probe — приложение поднялось, но не проходит healthcheck.

## Устранение

1. Если нехватка ресурсов — проверить `kubectl top nodes`/`kubectl top pods -A`, при необходимости освободить ресурсы (уменьшить нагрузку от менее критичных подов) или уменьшить requests/limits проблемного сервиса.
2. Если `ImagePullBackOff` — проверить, что образ реально существует в registry и тег корректен (сверить с последним успешным build в Jenkins).
3. Если readiness probe падает — смотреть логи пода (`kubectl logs`), исправить причину (конфиг, секреты, зависимость).
4. Если ничего не помогает быстро — откатить Deployment на предыдущую известную здоровую ревизию:
   ```bash
   kubectl rollout undo deployment/<deployment-name> -n <namespace>
   kubectl rollout status deployment/<deployment-name> -n <namespace>
   ```
5. Подтвердить восстановление: `available == desired` в `kube_deployment_status_replicas_available`/`kube_deployment_spec_replicas`, алерт переходит в `resolved`.

## Evidence (Фаза 5, п.8)

Соответствует учению "удалить/сломать readiness Pod'а" — заполняется реальными логами/скриншотами в `docs/evidence/task5/`.