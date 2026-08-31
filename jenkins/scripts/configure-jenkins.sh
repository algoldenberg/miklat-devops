#!/usr/bin/env bash
# Фаза 4, шаг 3: configure-jenkins.sh
# Создаёт (при отсутствии) Secret с учёткой администратора Jenkins —
# это единственная часть настройки Jenkins, которая осознанно НЕ идёт
# через JCasC/values.yaml (реальный пароль нельзя класть в Git ни в каком
# виде, по аналогии с miklat-secrets в Фазе 3).
#
# Значения передаются через переменные окружения JENKINS_ADMIN_USER /
# JENKINS_ADMIN_PASSWORD, либо запрашиваются интерактивно, если не заданы.
# Ничего не выводится в лог и никуда не пишется на диск.
set -euo pipefail

NAMESPACE="jenkins"
SECRET_NAME="jenkins-admin-secret"

kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 || kubectl create namespace "$NAMESPACE"

if kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" >/dev/null 2>&1; then
  echo "Secret $SECRET_NAME уже существует в namespace $NAMESPACE — пропускаю."
  echo "Чтобы пересоздать с новыми значениями: kubectl delete secret $SECRET_NAME -n $NAMESPACE, затем повтори этот скрипт."
  exit 0
fi

: "${JENKINS_ADMIN_USER:=}"
: "${JENKINS_ADMIN_PASSWORD:=}"

if [ -z "$JENKINS_ADMIN_USER" ]; then
  read -rp "Jenkins admin username: " JENKINS_ADMIN_USER
fi
if [ -z "$JENKINS_ADMIN_PASSWORD" ]; then
  read -rsp "Jenkins admin password: " JENKINS_ADMIN_PASSWORD
  echo
fi

if [ -z "$JENKINS_ADMIN_USER" ] || [ -z "$JENKINS_ADMIN_PASSWORD" ]; then
  echo "Логин и пароль не могут быть пустыми." >&2
  exit 1
fi

kubectl create secret generic "$SECRET_NAME" \
  --namespace "$NAMESPACE" \
  --from-literal=jenkins-admin-user="$JENKINS_ADMIN_USER" \
  --from-literal=jenkins-admin-password="$JENKINS_ADMIN_PASSWORD"

unset JENKINS_ADMIN_PASSWORD

echo "Secret $SECRET_NAME создан в namespace $NAMESPACE."
echo "Если Jenkins уже запущен — перезапусти под, чтобы security-realm подхватил новые данные: kubectl delete pod jenkins-0 -n $NAMESPACE"
