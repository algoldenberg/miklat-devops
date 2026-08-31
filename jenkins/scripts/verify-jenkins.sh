#!/usr/bin/env bash
# Фаза 4, шаг 3: verify-jenkins.sh
# Комплексная проверка состояния Jenkins после install/upgrade: под и PVC
# в кластере, доступность UI, наличие job'ов и pod template'ов Kubernetes
# Cloud (если заданы креды — без них REST API недоступен, т.к.
# anonymous read отключён).
#
# Требует активный `kubectl port-forward -n jenkins svc/jenkins 8090:8080`
# для проверки HTTP-доступности; JENKINS_ADMIN_USER/JENKINS_ADMIN_PASSWORD
# опциональны (без них пропускаются только REST-проверки job'ов/облака).
set -euo pipefail

NAMESPACE="jenkins"
JENKINS_URL="${JENKINS_URL:-http://localhost:8090}"

echo "== Под и PVC в namespace $NAMESPACE =="
kubectl get pods -n "$NAMESPACE"
echo
kubectl get pvc -n "$NAMESPACE"

echo
echo "== HTTP-доступность ($JENKINS_URL/login) =="
code=$(curl -s -o /dev/null -w '%{http_code}' "${JENKINS_URL}/login" || echo "000")
echo "HTTP ${code}"
if [ "$code" != "200" ]; then
  echo "Jenkins недоступен по $JENKINS_URL." >&2
  echo "Проверь: kubectl port-forward -n $NAMESPACE svc/jenkins 8090:8080" >&2
  exit 1
fi

if [ -n "${JENKINS_ADMIN_USER:-}" ] && [ -n "${JENKINS_ADMIN_PASSWORD:-}" ]; then
  echo
  echo "== Job'ы (Job DSL / JCasC) =="
  for job in miklat-ci miklat-cd; do
    code=$(curl -s -o /dev/null -w '%{http_code}' -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
      "${JENKINS_URL}/job/${job}/api/json")
    echo "  ${job}: HTTP ${code}"
  done

  echo
  echo "== Pod template'ы Kubernetes Cloud =="
  curl -s -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
    "${JENKINS_URL}/manage/cloud/kubernetes/api/json" 2>/dev/null \
    | grep -o '"name":"[^"]*"' \
    || echo "  Не удалось разобрать ответ — проверь вручную: Manage Jenkins → Clouds → kubernetes → Pod Templates"
else
  echo
  echo "JENKINS_ADMIN_USER/JENKINS_ADMIN_PASSWORD не заданы — пропускаю проверку job'ов и облака через REST API"
  echo "(anonymous read отключён, см. controller.JCasC в values.yaml)."
fi

echo
echo "Готово."
