# Runbook: NodeNotReadyOrPressure

## Симптом

Алерт `NodeNotReadyOrPressure` (severity: critical) — нода `{{ $labels.node }}` не в статусе `Ready`, либо в состоянии `MemoryPressure`/`DiskPressure`/`PIDPressure` на протяжении 5+ минут.

**Критично для этого проекта:** кластер — single-node k3s на сервере `mbdai`, который также хостит продакшн `shelternearyou.online` (11 production-контейнеров вне k8s). Проблема с единственной нодойk8s затрагивает ВЕСЬ проект (приложение, Jenkins, сам мониторинг) одновременно, а деградация самого сервера (память/диск) потенциально затрагивает и продакшн.

## Диагностика

1. Общее состояние ноды:
   ```bash
   kubectl get nodes -o wide
   kubectl describe node mbdai
   ```
2. Конкретное условие, которое сработало (панель "Node Ready"/"Disk usage" в дашборде Kubernetes/Cluster):
   ```bash
   curl -s --data-urlencode 'query=kube_node_status_condition{condition=~"Ready|MemoryPressure|DiskPressure|PIDPressure"}' 'http://localhost:9090/api/v1/query' | python3 -m json.tool
   ```
3. Если `MemoryPressure` — реальное потребление памяти нодой (не забывать, что сервер общий с продакшн-нагрузкой):
   ```bash
   free -h
   curl -s --data-urlencode 'query=100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))' 'http://localhost:9090/api/v1/query' | python3 -m json.tool
   docker stats --no-stream   # реальная нагрузка продакшн-контейнеров вне k8s
   ```
4. Если `DiskPressure` — свободное место на корневом разделе (панель "Disk usage (root, node mbdai)"):
   ```bash
   df -h /
   ```
5. Если `NotReady` — статус самого kubelet/k3s-агента:
   ```bash
   systemctl status k3s
   journalctl -u k3s --since "15 minutes ago" | tail -50
   ```

## Вероятные причины (специфично для этого сервера)

- Одновременный рост нагрузки от production-контейнеров и k8s-подов (общая память сервера — известное узкое место, см. `claude/miklat-progress.md`, Фаза 5, Шаг 1: сервер уже один раз апгрейжен с 5.8Gi до 7.8Gi RAM).
- Динамические Jenkins CI-агенты (K8s-плагин) создают дополнительные поды под нагрузку в момент сборки — пиковое потребление CPU/памяти именно во время CI/CD.
- Заполнение диска логами/образами Docker/containerd со временем.

## Устранение

1. При `MemoryPressure`: остановить/уменьшить некритичную нагрузку (например, дождаться завершения активных Jenkins-сборок, не запускать новые), при системной нехватке — эскалировать к апгрейду RAM сервера (прецедент уже есть в этом проекте).
2. При `DiskPressure`: очистить неиспользуемые образы/логи:
   ```bash
   docker system prune -af --volumes   # ОСТОРОЖНО: только после проверки, что не заденет production-volume'ы
   kubectl get pods -A -o wide | grep -v Running   # проверить зависшие поды, которые могут копить логи
   ```
3. При `NotReady` без явной причины — попытаться мягкий рестарт k3s-агента (`systemctl restart k3s`), только после диагностики логов, не вслепую.
4. Подтвердить восстановление: `kube_node_status_condition{condition="Ready",status="true"} == 1`, отсутствие pressure-условий, алерт переходит в `resolved`.

## Evidence (Фаза 5, п.8)

Не входит напрямую в список 4 обязательных учений плана (учения фокусируются на приложении/Jenkins/CD), но диагностика этого runbook'а пересекается с учением "удалить/сломать readiness Pod'а" на уровне платформы.