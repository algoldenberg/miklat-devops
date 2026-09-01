#!/usr/bin/env bash
# Разовая миграция уже существующих (применённых голым kubectl apply в
# Фазе 3) ресурсов namespace miklat-app под управление этим Helm-чартом.
#
# Без этого шага первый `helm install` откажется "усыновить" объекты:
#   Error: rendered manifests contain a resource that already exists...
#   ... exists and cannot be imported into the current release
#
# Скрипт идемпотентен — повторный запуск не навредит (kubectl annotate/label
# --overwrite просто перезапишет тем же значением).
#
# Namespace miklat-app и Secret miklat-secrets НЕ трогаем — они сознательно
# не входят в этот Helm chart (см. helm/miklat-app/README.md).
set -euo pipefail

NAMESPACE="miklat-app"
RELEASE="miklat-app"

echo "== Помечаем ресурсы аннотациями/лейблами Helm (release=${RELEASE}, namespace=${NAMESPACE}) =="

RESOURCES=(
  "serviceaccount/miklat-frontend-sa"
  "serviceaccount/miklat-backend-sa"
  "serviceaccount/miklat-worker-sa"
  "configmap/miklat-config"
  "ingress/miklat-ingress"
  "deployment/osrm" "service/osrm"
  "deployment/miklat-service" "service/miklat-service"
  "deployment/miklat-comments" "service/miklat-comments"
  "deployment/miklat-routes" "service/miklat-routes"
  "deployment/miklat-walking-routes" "service/miklat-walking-routes"
  "deployment/miklat-photos" "service/miklat-photos"
  "deployment/miklat-gateway" "service/miklat-gateway"
  "deployment/frontend" "service/frontend"
)

for res in "${RESOURCES[@]}"; do
  echo "-- ${res}"
  kubectl -n "${NAMESPACE}" annotate "${res}" \
    "meta.helm.sh/release-name=${RELEASE}" \
    "meta.helm.sh/release-namespace=${NAMESPACE}" \
    --overwrite
  kubectl -n "${NAMESPACE}" label "${res}" \
    "app.kubernetes.io/managed-by=Helm" \
    --overwrite
done

echo "== Готово. Теперь можно запускать: =="
echo "helm upgrade --install ${RELEASE} ./helm/miklat-app --namespace ${NAMESPACE}"
