#!/usr/bin/env bash
# Фаза 4, шаг 3: install-jenkins.sh
# Устанавливает/обновляет Jenkins в k3s через официальный Helm chart.
# Вся конфигурация (namespace, PVC, ServiceAccount/RBAC, agent pod
# template'ы, seed-jobs через Job DSL) берётся из jenkins/values.yaml —
# этот скрипт только кодифицирует команды, которые иначе пришлось бы
# помнить и вводить руками.
#
# Перед первым запуском (install) должен существовать Secret с учёткой
# администратора — см. configure-jenkins.sh.
set -euo pipefail

NAMESPACE="jenkins"
CHART_VERSION="5.9.29"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALUES_FILE="${SCRIPT_DIR}/../values.yaml"

if [ ! -f "$VALUES_FILE" ]; then
  echo "Не найден $VALUES_FILE" >&2
  exit 1
fi

echo "== Добавляю/обновляю Helm-репозиторий jenkinsci =="
helm repo add jenkins https://charts.jenkins.io >/dev/null 2>&1 || true
helm repo update jenkins

echo "== Namespace $NAMESPACE =="
kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 || kubectl create namespace "$NAMESPACE"

if helm status jenkins -n "$NAMESPACE" >/dev/null 2>&1; then
  echo "== Release jenkins уже существует — helm upgrade (версия чарта зафиксирована: $CHART_VERSION) =="
  helm upgrade jenkins jenkins/jenkins \
    --namespace "$NAMESPACE" \
    --version "$CHART_VERSION" \
    -f "$VALUES_FILE"
else
  if ! kubectl get secret jenkins-admin-secret -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "ВНИМАНИЕ: Secret jenkins-admin-secret не найден — сначала выполни ./configure-jenkins.sh" >&2
    exit 1
  fi
  echo "== Release jenkins не найден — helm install (версия чарта зафиксирована: $CHART_VERSION) =="
  helm install jenkins jenkins/jenkins \
    --namespace "$NAMESPACE" \
    --version "$CHART_VERSION" \
    -f "$VALUES_FILE"
fi

echo
echo "Готово. Проверка: ./verify-jenkins.sh"
