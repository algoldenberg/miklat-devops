# Runbook: PrometheusTargetDown

## Симптом

Алерт `PrometheusTargetDown` (severity: critical) — `up{job="<job>"} == 0` на протяжении 5+ минут для одного из компонентов, реально принадлежащих проекту: 6 backend-сервисов `miklat-app`, `jenkins`, либо сам стек мониторинга (`kube-prometheus-stack-prometheus`/`-grafana`/`-alertmanager`/`-operator`, `kube-state-metrics`, `node-exporter`). Область алерта сознательно НЕ включает `apiserver`/`coredns`/`kubelet` — это базовая инфраструктура k8s вне владения проекта.

## Диагностика

1. Какой именно target упал (панель "Jenkins scrape health" для Jenkins; для остальных — прямой запрос):
   ```bash
   curl -s 'http://localhost:9090/api/v1/targets' | python3 -c "
   import json,sys
   d = json.load(sys.stdin)['data']['activeTargets']
   for t in d:
       if t['health'] != 'up':
           print(t['scrapePool'], t['scrapeUrl'], t['health'], t.get('lastError'))
   "
   ```
2. Если это один из 6 backend-сервисов — под жив вообще?
   ```bash
   kubectl get pods -n miklat-app -l app=<service-name> -o wide
   kubectl logs -n miklat-app <pod-name> --tail=100
   ```
3. Если это Jenkins — тот же принцип, namespace `jenkins` (уже дважды был реальный инцидент в этом проекте: сначала плагин не был установлен, потом NetworkPolicy блокировала scrape — см. `claude/miklat-progress.md`, оба разбора).
4. Если это сам компонент стека мониторинга (`kube-prometheus-stack-*`) — вероятно, серьёзнее: сам мониторинг частично ослеп.
   ```bash
   kubectl get pods -n observability -o wide
   kubectl describe pod -n observability <pod-name>
   ```
5. Общая первая проверка для ЛЮБОГО падения — не NetworkPolicy ли блокирует scrape (частая причина в этом проекте):
   ```bash
   kubectl get networkpolicy -n <namespace-таргета>
   ```

## Вероятные причины

- Под с `/metrics` endpoint упал или перезапускается (`CrashLoopBackOff`, OOMKilled).
- NetworkPolicy блокирует scrape-трафик Prometheus → под (см. `jenkins/network-policy.yaml`, `monitoring/network-policy.yaml` — оба уже содержат исправленные реальные инциденты этого типа).
- Сервис/Endpoint изменил порт или лейблы, из-за чего `ServiceMonitor` больше не матчит правильный под.
- Сам Prometheus/Operator упал (если `up{job="kube-prometheus-stack-prometheus"}==0` — самый критичный случай, весь мониторинг ослеп).

## Устранение

1. Если под упал — стандартная диагностика пода (`describe`/`logs`), рестарт при необходимости (`kubectl rollout restart` для соответствующего Deployment/StatefulSet).
2. Если NetworkPolicy — сверить с реальными портами/namespace-селекторами (тот же метод, что уже дважды применялся в этом проекте: сравнить реальный containerPort/Service port с правилами NetworkPolicy, добавить недостающее правило).
3. Если сам Prometheus упал — это критичнее всего остального: сначала восстановить сам Prometheus/Operator (`kubectl get pods -n observability`, `kubectl describe statefulset kube-prometheus-stack-prometheus -n observability`), т.к. пока он не работает, остальные алерты тоже не эвалюируются.
4. Подтвердить восстановление: `up{job="<job>"} == 1`, алерт переходит в `resolved`.

## Evidence (Фаза 5, п.8)

Не входит напрямую в список 4 обязательных учений плана, но диагностика этого runbook'а — прямое обобщение двух уже произошедших в этом проекте реальных инцидентов (Jenkins plugin missing, NetworkPolicy blocking scrape), задокументированных в `claude/miklat-progress.md`.