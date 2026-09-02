# Architecture Diagram — Task 2 (Terraform + Ansible)

Shows the AWS infrastructure created by Terraform, the software configured on top of it by
Ansible, traffic directions, and the separation between the two tools. Renders natively on
GitHub (Mermaid block below); a pre-rendered PNG is also included
(`architecture-task2.png`) for viewing outside GitHub.

Legend (color = zone):
- 🔴 **red** — public entry point (Internet, Internet Gateway, the frontend EC2's public interface on port 80).
- 🔵 **blue** — private application layer inside the VPC (backend/worker EC2, reachable only from specific Security Groups, never directly from the Internet).
- 🟢 **green** — managed AWS service (RDS, S3, SNS) — reached over the network/IAM, not part of any EC2.
- ⬜ **grey** — the Ansible control node (a Docker container on the operator's machine) — outside AWS, connects over SSH only, not part of the running application.

**Terraform vs Ansible, in one line:** every box inside the AWS boundary below (VPC, subnets, Internet Gateway, the 3 EC2 instances as empty shells, the 4 Security Groups, RDS, S3, SNS) is created by **Terraform** (`terraform/*.tf`). Everything running *inside* those EC2 instances (nginx, the Python services under systemd, the OSRM container) is installed and configured by **Ansible** (`ansible/playbooks/*.yml`) after Terraform hands off the bare instances — labeled on each node below.

```mermaid
flowchart TB
    Internet(["User (browser)"])
    Admin["Ansible control node\n(Docker container, operator's machine)"]

    subgraph AWS["AWS il-central-1 — Terraform-managed"]
        direction TB

        IGW["Internet Gateway\n(Terraform: network.tf)"]

        subgraph VPC["VPC (Terraform: network.tf)"]
            direction TB

            subgraph SubnetA["Public Subnet A"]
                FE["EC2: miklat-frontend\nSG: frontend-sg (Terraform)\nnginx + React build (Ansible: nginx.yml)"]
            end

            subgraph SubnetB["Public Subnet B"]
                BE["EC2: miklat-backend\nSG: backend-sg (Terraform)\nIAM: miklat-app-role (Terraform)\nmiklat-gateway + miklat-service + miklat-comments, systemd (Ansible: deploy-backend.yml)"]
                WK["EC2: miklat-worker\nSG: worker-sg (Terraform)\nIAM: miklat-app-role (Terraform)\nmiklat-routes + miklat-walking-routes + miklat-photos, systemd + OSRM container (Ansible: deploy-worker.yml)"]
            end
        end

        subgraph DBGROUP["DB Subnet Group, 2 AZ (Terraform: rds.tf)"]
            RDS[("RDS PostgreSQL + PostGIS\nSG: rds-sg (Terraform)")]
        end

        S3[("S3: miklat-photos-tf-*\n(Terraform: s3.tf)")]
        SNS(["SNS: miklat-notifications-tf\n(Terraform: sns.tf)"])
    end

    Internet -- "HTTP :80 (public boundary)" --> IGW --> FE
    FE -- "/api/* → backend private IP" --> BE
    BE -- "gateway → service/comments (localhost)" --> BE
    BE -- "gateway → routes/walking-routes/photos (worker private IP)" --> WK

    BE -. "psql :5432" .-> RDS
    WK -. "psql :5432" .-> RDS
    BE -. "IAM: miklat-app-role, sns:Publish" .-> SNS
    WK -. "IAM: miklat-app-role, s3:PutObject/GetObject" .-> S3
    WK -. "IAM: miklat-app-role, sns:Publish" .-> SNS

    Admin -. "SSH (ssh_allowed_cidr only) + ansible-playbook" .-> FE
    Admin -. "SSH (ssh_allowed_cidr only) + ansible-playbook" .-> BE
    Admin -. "SSH (ssh_allowed_cidr only) + ansible-playbook" .-> WK

    classDef publicZone fill:#ffe0e0,stroke:#c0392b,stroke-width:2px;
    classDef privateZone fill:#e0f0ff,stroke:#2980b9,stroke-width:1px;
    classDef cloudZone fill:#e8f8e8,stroke:#27ae60,stroke-width:1px;
    classDef adminZone fill:#f0f0f0,stroke:#888,stroke-width:1px,stroke-dasharray: 4 3;

    class Internet,IGW,FE publicZone;
    class BE,WK privateZone;
    class RDS,S3,SNS cloudZone;
    class Admin adminZone;
```
