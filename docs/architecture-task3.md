# Диаграмма архитектуры — Задание 3 (Kubernetes)

Deployment View: namespace'ы, Deployment/Service, Ingress, границы трафика и разделение
public/private. Рендерится нативно на GitHub (mermaid-блок ниже); альтернативно — готовый
PNG рядом (`architecture-task3.png`), на случай просмотра вне GitHub.

Легенда (цвет = зона):
- 🔴 **красный** — публичная зона (снаружи кластера/снаружи VPC): пользователь, Ingress-контроллер, Ingress-ресурс.
- 🔵 **синий** — приватная зона внутри кластера (только `ClusterIP`, недостижимо снаружи): все 8 Deployment/Service, ConfigMap, Secret.
- 🟢 **зелёный** — AWS-облако (Задание 2, Terraform): RDS, S3, SNS — вне кластера, доступ по сети/IAM.
- ⬜ **серый пунктир** — продакшен `shelternearyou.online` на том же физическом сервере `mbdai`, вне scope этого задания, показан только для контекста изоляции.

```mermaid
flowchart TB
    User(["Пользователь\n(браузер)"])

    subgraph MBDAI["VPS mbdai"]
        direction TB

        subgraph PROD["Docker Compose — продакшен shelternearyou.online (вне scope Задания 3, порты 80/443/27017/6379/...)"]
            PRODSTACK["nginx + Node + MongoDB + Redis"]
        end

        subgraph K3S["k3s кластер (единственная нода)"]
            direction TB

            subgraph NSING["namespace: ingress-nginx"]
                IC["ingress-nginx-controller\nService NodePort 30080/30443"]
            end

            subgraph NSAPP["namespace: miklat-app"]
                direction TB

                ING["Ingress: miklat-ingress\nclass nginx · path / → frontend:8080"]

                subgraph TFRONT["tier: frontend · SA: miklat-frontend-sa"]
                    FE["Deployment: frontend\nService ClusterIP :8080\n(React+Vite статика, non-root nginx)"]
                end

                subgraph TBACK["tier: backend · SA: miklat-backend-sa"]
                    GW["miklat-gateway\nClusterIP :8000"]
                    SVC["miklat-service\nClusterIP :8000"]
                    COM["miklat-comments\nClusterIP :8000"]
                end

                subgraph TWORK["tier: worker · SA: miklat-worker-sa"]
                    RT["miklat-routes\nClusterIP :8000"]
                    WRT["miklat-walking-routes\nClusterIP :8000"]
                    PH["miklat-photos\nClusterIP :8000"]
                    OSRM["osrm (3rd-party, root)\nClusterIP :5000"]
                end

                CM[("ConfigMap\nmiklat-config")]
                SEC[("Secret\nmiklat-secrets\n(Opaque, 6 ключей)")]
            end
        end
    end

    subgraph AWSCLOUD["AWS il-central-1 (Terraform, Задание 2)"]
        direction TB
        RDS[("RDS PostgreSQL+PostGIS")]
        S3[("S3: miklat-photos-tf-*")]
        SNS[("SNS: miklat-notifications-tf")]
    end

    User -- "HTTP :30080 (публичная граница)" --> IC
    IC --> ING
    ING --> FE
    FE -- "/api/*" --> GW
    GW --> SVC
    GW --> COM
    GW --> RT
    GW --> WRT
    GW --> PH
    RT --> OSRM
    WRT --> OSRM

    SVC -. "psql :5432" .-> RDS
    COM -. "psql :5432" .-> RDS
    RT -. "psql :5432" .-> RDS
    WRT -. "psql :5432" .-> RDS
    PH -. "psql :5432" .-> RDS
    SVC -. "IAM: miklat-k8s" .-> SNS
    PH -. "IAM: miklat-k8s" .-> S3
    PH -. "IAM: miklat-k8s" .-> SNS

    CM -.-> SVC & COM & RT & WRT & PH
    SEC -.-> SVC & COM & RT & WRT & PH

    classDef publicZone fill:#ffe0e0,stroke:#c0392b,stroke-width:2px;
    classDef privateZone fill:#e0f0ff,stroke:#2980b9,stroke-width:1px;
    classDef cloudZone fill:#e8f8e8,stroke:#27ae60,stroke-width:1px;
    classDef prodZone fill:#f0f0f0,stroke:#888,stroke-width:1px,stroke-dasharray: 4 3;

    class User,IC,ING publicZone;
    class FE,GW,SVC,COM,RT,WRT,PH,OSRM,CM,SEC privateZone;
    class RDS,S3,SNS cloudZone;
    class PRODSTACK prodZone;
```
