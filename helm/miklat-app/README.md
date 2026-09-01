# miklat-app (Helm chart)

Обёртка вокруг манифестов Фазы 3 (`k8s/*.yaml`) специально под `Jenkinsfile-cd`
(Фаза 4, шаг 5) — чтобы деплой шёл через `helm upgrade --install` (с
`helm rollback` при неудаче), а не через голый `kubectl apply`/`kubectl set image`.

## Что НЕ входит в чарт (осознанно)

- **Namespace `miklat-app`** — создан один раз вручную (`kubectl create namespace`,
  Фаза 3 шаг 2), Helm им не управляет: `helm uninstall` не должен иметь
  возможность снести весь namespace целиком.
- **Secret `miklat-secrets`** — как и раньше, создаётся императивно одной
  kubectl-командой, значения никогда не попадают ни в values.yaml, ни в git.
  Чарт только ссылается на его ключи через `secretKeyRef` в шаблонах.
- **nginx ingress controller** (`k8s/03-ingress-nginx-controller.yaml`) —
  инфраструктурный компонент кластера, не часть релиза приложения, остаётся
  обычным kubectl-манифестом.

## Первая миграция существующего kubectl-деплоя под управление Helm

Ресурсы (`miklat-frontend-sa`/`miklat-backend-sa`/`miklat-worker-sa`,
`miklat-config`, `miklat-ingress`, 8 Deployment+Service) уже существуют в
кластере, применённые голым `kubectl apply` в Фазе 3 — у них нет
Helm-аннотаций/лейблов владения. Прямой `helm install` откажется их
"усыновить" (`... exists and cannot be imported into the current release`).
Перед первым `helm upgrade --install` нужно один раз проставить каждому
существующему объекту:
- аннотации `meta.helm.sh/release-name=miklat-app`,
  `meta.helm.sh/release-namespace=miklat-app`;
- лейбл `app.kubernetes.io/managed-by=Helm`.

См. `migrate-to-helm.sh` рядом с этим файлом — делает это идемпотентно для
всех объектов разом.

## Установка / обновление

```
helm upgrade --install miklat-app ./helm/miklat-app \
  --namespace miklat-app \
  --reuse-values \
  --set miklatPhotos.imageTag=<GIT_SHA>
```

`--reuse-values` обязателен при точечном обновлении одного сервиса — без
него Helm откатит теги ВСЕХ остальных сервисов на значения по умолчанию
из `values.yaml`, а не оставит их как есть.
