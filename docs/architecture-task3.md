# Architecture Diagram — Task 3 (Kubernetes)

Deployment View: namespaces, Deployment/Service, Ingress, traffic boundaries and
public/private separation. Renders natively on GitHub (Mermaid block below); a
pre-rendered PNG is also included (`architecture-task3.png`) for viewing outside GitHub.

Legend (color = zone):
- 🔴 **red** — public zone (outside the cluster / outside the VPC): user, Ingress controller, Ingress resource.
- 🔵 **blue** — private zone inside the cluster (`ClusterIP` only, unreachable from outside): all 8 Deployment/Service, ConfigMap, Secret.
- 🟢 **green** — AWS cloud (Task 2, Terraform): RDS, S3, SNS — outside the cluster, reached over the network/IAM.
- ⬜ **grey dashed** — production `shelternearyou.online` on the same physical server `mbdai`, out of scope for this task, shown only for isolation context.

```mermaid
flowchart TB
    User(["User\n(browser)"])

    subgraph MBDAI["VPS mbdai"]
        direction TB

        subgraph PROD["Docker Compose — production shelternearyou.online (out of scope for Task 3, ports 80/443/27017/6379/...)"]
            PRODSTACK["nginx + Node + MongoDB + Redis"]
        end

        subgraph K3S["k3s cluster (single node)"]
            direction TB

            subgraph NSING["namespace: ingress-nginx"]
                IC["ingress-nginx-controller\nService NodePort 30080/30443"]
            end

            subgraph NSAPP["namespace: miklat-app"]
                direction TB

                ING["Ingress: miklat-ingress\nclass nginx · path / → frontend:8080"]

                subgraph TFRONT["tier: frontend · SA: miklat-frontend-sa"]
                    FE["Deployment: frontend\nService ClusterIP :8080\n(React+Vite static, non-root nginx)"]
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
                SEC[("Secret\nmiklat-secrets\n(Opaque, 6 keys)")]
            end
        end
    end

    subgraph AWSCLOUD["AWS il-central-1 (Terraform, Task 2)"]
        direction TB
        RDS[("RDS PostgreSQL+PostGIS")]
        S3[("S3: miklat-photos-tf-*")]
        SNS[("SNS: miklat-notifications-tf")]
    end

    User -- "HTTP :30080 (public boundary)" --> IC
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
