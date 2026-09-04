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
5. Проверить, не блокирует ли создание пода агента `ResourceQuota` в namespace `jenkins` (не только нехватка реальных ресурсов ноды — квота может отклонять создание пода на уровне admission control, даже если на ноде физически есть свободные ресурсы; см. реальное учение ниже):
   ```bash
   kubectl get resourcequota -n jenkins
   kubectl describe resourcequota -n jenkins
   ```
6. Посмотреть реальный текст ошибки провижининга на стороне самого контроллера (самый быстрый способ увидеть точную причину, без догадок):
   ```bash
   kubectl logs jenkins-0 -n jenkins -c jenkins --since=10m | grep -i -B2 -A5 "exceeded\|quota\|provision\|error"
   ```
7. Посмотреть, какая именно job заблокирована и почему (через Jenkins UI, доступный по port-forward — Jenkins сознательно не выведен в интернет, см. п.1 плана Фазы 5):
   ```bash
   kubectl port-forward -n jenkins svc/jenkins 18080:8080
   # затем http://localhost:18080/queue/ — вкладка Build Queue покажет причину блокировки текстом
   ```

## Вероятные причины

- Динамический pod-агент (Kubernetes-плагин Jenkins) не может подняться — нехватка ресурсов ноды, `ImagePullBackOff` для образа агента, проблема с ServiceAccount/RBAC агента.
- `ResourceQuota` в namespace `jenkins` блокирует создание пода агента на уровне admission control (`403 Forbidden: exceeded quota`) — отдельная от нехватки реальных ресурсов причина; под просто не может быть создан, даже если на ноде есть свободная память/CPU (подтверждено реальным учением ниже).
- Все executor'ы заняты одновременно (built-in имеет 0 executor'ов архитектурно — см. `claude/miklat-progress.md`, Фаза 5, дашборд Jenkins & Delivery — сборки идут только на build-agent/cd-agent/ci-agent).
- Проблема с NetworkPolicy/RBAC, блокирующая создание/коммуникацию агент-пода (прецедент уже был в этом проекте — Фаза 4, JNLP-порт; Фаза 5, scrape-порт).

## Устранение

1. Если агент не может подняться — `kubectl describe pod` покажет точную причину (Events); устранить конкретно (ресурсы/образ/RBAC).
2. Если ресурсы ноды исчерпаны — дождаться освобождения либо вручную остановить менее приоритетные job'ы.
3. Если проблема с NetworkPolicy — сверить `jenkins/network-policy.yaml` с реальными портами агента (тот же подход, что уже применялся дважды в этом проекте).
4. Если проблема — `ResourceQuota` (в т.ч. случайно оставленная после диагностики/учения) — увеличить лимит или удалить объект:
   ```bash
   kubectl delete resourcequota <name> -n jenkins
   ```
   Kubernetes-плагин Jenkins сам ретраит провижининг раз в ~10 секунд — специально ничего перезапускать не нужно, зависшая сборка подхватит агента сама, как только он реально сможет подняться.
5. После устранения — подтвердить, что очередь очистилась (`jenkins_queue_stuck_value`/`jenkins_queue_blocked_value` вернулись к 0), алерт переходит в `resolved`.

   **Важно (подтверждено реальным учением ниже):** в отличие от `HighErrorRate`/`ReplicasMismatch`, у этого алерта нет скользящего окна поверх `rate()` — это прямой gauge-порог, снятие происходит почти сразу же (на следующем цикле evaluation группы правил, ~30с), а не через 5-10 минут.

## Evidence (Фаза 5, п.8)

Реальное, управляемое учение проведено 04.09.2026 на `mbdai`. Полный ход, все команды и сырой вывод — `docs/evidence/task5/failure-drill-3-jenkins-queue-stuck.txt`. Кратко:

- **Поломка:** временный `ResourceQuota` (`hard: pods: "1"`) в namespace `jenkins`, равный числу уже реально запущенных подов (только `jenkins-0`) — выбран вместо реального исчерпания ресурсов ноды (риск задеть прод `shelternearyou.online` на общем хосте, память и так уже была впритык весь проект) и вместо поломки образа в `agent.podTemplates` (лишнее касание Git-tracked `values.yaml`). Полностью безопасен: не потребляет ни байта реальных CPU/RAM, только объект admission control.
- **Запуск:** сборка `miklat-ci #37` вручную через Jenkins UI ("Build Now") — выбран `miklat-ci`, т.к. не требует деплой-параметров и не может тронуть кластер в любом исходе.
- **Подтверждено сработавшим не по предположению, а по реальному логу самого контроллера** (`kubectl logs jenkins-0 -c jenkins`): `NodeProvisioner` ретраил создание агента каждые ~10с под новым случайным именем (`ci-agent-xw6c2`, `ci-agent-hs86w`, ...) — каждый раз идентичная ошибка `403 Forbidden: exceeded quota: miklat-drill3-quota, requested: pods=1, used: pods=1, limited: pods=1`.
- **Честно отмеченная находка, не предсказанная заранее:** сработал именно `jenkins_queue_stuck_value` (не `jenkins_queue_blocked_value`, который остался `0`), и сработал быстро — в пределах ~1 минуты после постановки сборки в очередь. Для алерта это не важно (условие через `OR`), но для будущей диагностики стоит знать, что реальное поведение Jenkins в этом сценарии — именно `stuck`, а не ожидаемо более логичный `blocked`.
- **Подтверждено сработавшим (Prometheus + Alertmanager):** `activeAt: 2026-09-04T12:03:29Z` в правиле, переход в `firing` ровно через `for: 600s` — `startsAt: 2026-09-04T12:13:29Z` в Alertmanager, тайминги сошлись день в день; `severity: warning`, `category: jenkins`, `receivers: [demo-webhook]`, корректный `runbook_url`.
- **Устранение:** `kubectl delete resourcequota miklat-drill3-quota -n jenkins`. В пределах двух минут тот же самый ретраящийся `NodeProvisioner` (без вмешательства) успешно поднял `ci-agent-hrnhz`, зависшая сборка `#37` сама подхватила агента и завершилась `Success`.
- **Снятие алерта подтверждено:** сразу после фикса метрики уже были `0`, но правило ещё одну проверку показывало `firing` (пойман между evaluation-циклами, не баг) — через ~1 минуту: `state: "inactive"`, Alertmanager — пустой список.

Прод `shelternearyou.online` не затрагивался, реальных ресурсов хоста поломка не потребляла — временный `ResourceQuota` существовал только в изолированном namespace `jenkins`.