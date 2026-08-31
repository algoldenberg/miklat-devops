#!/usr/bin/env bash
# Фаза 4, шаг 3: create-jobs.sh
# Job'ы miklat-ci/miklat-cd создаются АВТОМАТИЧЕСКИ через JCasC (ключ
# `jobs:` в jenkins/values.yaml, плагин Job DSL) при каждом старте или
# reload контроллера — отдельного "seed job", который нужно было бы
# руками нажимать Build Now через UI, здесь нет и не требуется.
#
# Этот скрипт нужен только на случай, если конфигурация обновилась
# (helm upgrade), а сайдкар config-reload по какой-то причине не
# среагировал сам: форсирует JCasC reload через тот же эндпоинт, что
# использует сайдкар, и затем проверяет, что оба job'а реально существуют.
#
# Требует: активный `kubectl port-forward -n jenkins svc/jenkins 8090:8080`
# и переменные JENKINS_ADMIN_USER/JENKINS_ADMIN_PASSWORD.
set -euo pipefail

JENKINS_URL="${JENKINS_URL:-http://localhost:8090}"
RELOAD_TOKEN="${RELOAD_TOKEN:-jenkins-0}"   # имя пода = casc-reload-token по умолчанию в чарте

: "${JENKINS_ADMIN_USER:?переменная JENKINS_ADMIN_USER обязательна}"
: "${JENKINS_ADMIN_PASSWORD:?переменная JENKINS_ADMIN_PASSWORD обязательна}"

echo "== Форсирую JCasC reload на $JENKINS_URL =="
curl -sf -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
  "${JENKINS_URL}/reload-configuration-as-code/?casc-reload-token=${RELOAD_TOKEN}" >/dev/null
echo "OK"

sleep 3

echo
echo "== Проверяю job'ы =="
status=0
for job in miklat-ci miklat-cd; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
    "${JENKINS_URL}/job/${job}/api/json")
  if [ "$code" = "200" ]; then
    echo "  ${job}: OK"
  else
    echo "  ${job}: НЕ НАЙДЕН (HTTP ${code})"
    status=1
  fi
done

exit "$status"
