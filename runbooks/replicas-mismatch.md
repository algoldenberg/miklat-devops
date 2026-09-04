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

**Найдено при реальном учении ниже, полезно на будущее:** `kubectl delete pod <pod>` НЕ выводит старый под из ротации при зависшем rollout — ReplicaSet-контроллер тут же пересоздаёт его обратно по своему `desired count`, независимо от общей логики Deployment. Чтобы реально убрать старую версию (например, при ручном разборе зависшего rollout), нужно явно `kubectl scale rs <replicaset-name> -n <namespace> --replicas=0`, а не удалять отдельные поды.

## Evidence (Фаза 5, п.8)

Реальное, управляемое учение проведено 04.09.2026 на `mbdai`. Полный ход, все команды и сырой вывод — `docs/evidence/task5/failure-drill-2-replicas-mismatch.txt`. Кратко:

- **Поломка:** `kubectl patch deployment miklat-routes --type=json` — подмена `readinessProbe.httpGet.path` на несуществующий путь у сервиса `miklat-routes` (namespace `miklat-app`, 1 реплика).
- **Реальная накладка по ходу (задокументирована как находка, не как баг кластера):** первая попытка (просто патч) не дала мисматча — при `replicas=1` и дефолтном `RollingUpdate` старый здоровый под остаётся жив, пока новый не станет `Ready` (чего не случится с битым probe). Вторая попытка (`kubectl delete pod` на старом) тоже не сработала напрямую — ReplicaSet-контроллер тут же пересоздал под обратно под старым (рабочим) шаблоном. Сработало только явное `kubectl scale rs <старый-rs> --replicas=0` — итог: 1 под, `0/1`, устойчиво (без рестарт-лупа, т.к. `livenessProbe` не тронута).
- **Подтверждено сработавшим:** после выдержки 10 минут (`for: 10m`) — состояние правила `"state": "firing"`, Alertmanager реально получил алерт (`deployment=miklat-routes`, `namespace=miklat-app`, `severity=warning`).
- **Честно отмеченный пробел:** значения `kube_deployment_status_replicas_available`/`up` именно в момент отказа не были заново запрошены через Prometheus API до отката (случайный повторный запуск команды отката обогнал проверку) — сам факт мисматча зафиксирован `kubectl get deployment` (`READY 0/1 AVAILABLE 0`) и подтверждён срабатыванием алерта, но не задокументирован отдельным API-снимком в момент отказа.
- **Устранение:** возврат `readinessProbe.httpGet.path` к `/ready` — k8s переиспользовал старый (ранее обнулённый) ReplicaSet вместо создания нового, новый под стал `Ready` за ~12с.
- **Снятие алерта подтверждено:** через 10 минут после восстановления — `state: "inactive"`, Alertmanager — пустой список, в кластере остался ровно один здоровый под.

Прод `shelternearyou.online` не затрагивался — менялся только `readinessProbe` `miklat-routes` в изолированном namespace `miklat-app`.