# Architecture — Task 4 (Jenkins CI/CD)

Two diagrams required for Task 4: **Deployment View** (where the Jenkins CI/CD components physically live relative to the rest of the `mbdai` cluster) and **Pipeline Flow** (how a commit turns into a deployed pod, including the rollback path on failure).

Both diagrams are Mermaid, so they render natively on GitHub. Pre-rendered PNGs (`task4-deployment.png`, `task4-pipeline.png`) sit alongside this file in case Mermaid isn't supported wherever this is viewed.

Color legend, shared with `architecture-task3.md`:

| Color | Meaning |
|---|---|
| 🔴 pink | public / external entry point (internet, webhook, image registry) |
| 🔵 blue | internal cluster component (Jenkins, Helm release, pods) |
| 🟢 green | managed AWS service (Task 2) / successful outcome |
| ⬜ grey (dashed) | out of scope for this architecture (production original) |

---

## 1. Deployment View

Shows where the Jenkins CI/CD components (namespace `jenkins`) physically sit relative to `ingress-nginx`, the application (`miklat-app`, details in `architecture-task3.md`), AWS services, and the production stack that stays untouched.

```mermaid
flowchart TB
    DEV["Developer<br/>git push"]
    GH["GitHub<br/>algoldenberg/miklat-devops"]
    GHCR[("GHCR<br/>ghcr.io/algoldenberg/*")]
    USER["User (browser)"]
    ADMIN["Admin<br/>kubectl port-forward"]

    subgraph AWS["AWS (Task 2)"]
        RDS[("RDS PostgreSQL")]
        S3[("S3 photos")]
        SNS(["SNS notifications"])
    end

    subgraph MBDAI["mbdai — k3s, single node"]
        subgraph NS_INGRESS["namespace: ingress-nginx"]
            ING["ingress-nginx-controller<br/>NodePort 30080/30443"]
        end

        subgraph NS_JENKINS["namespace: jenkins"]
            JCTRL["jenkins-0 (controller)<br/>SA: jenkins<br/>Svc jenkins:8080, jenkins-agent:50000"]
            PVCJ[("PVC jenkins-home 8Gi")]
            CIAGENT["ci-agent-* (ephemeral)<br/>SA: jenkins<br/>git + python-tools + node-tools + kaniko"]
            CDAGENT["cd-agent-* (ephemeral)<br/>SA: jenkins-cd<br/>kubectl-helm"]
        end

        subgraph NS_APP["namespace: miklat-app"]
            HELM["Helm release miklat-app<br/>7 services + osrm<br/>(details — architecture-task3)"]
            SECAPP[("Secret miklat-secrets")]
        end
    end

    subgraph PROD["shelternearyou.online — production, out of scope"]
        PRODSTACK["Docker Compose stack<br/>not touched"]
    end

    DEV -->|git push| GH
    GH -->|"POST /github-webhook/<br/>HMAC X-Hub-Signature-256"| ING
    ING -->|"port 8080, this path only"| JCTRL
    ING -->|"/ → frontend"| HELM
    USER -->|HTTP| ING
    JCTRL -->|creates/deletes pod| CIAGENT
    JCTRL -->|creates/deletes pod| CDAGENT
    JCTRL --- PVCJ
    CIAGENT -->|git clone| GH
    CIAGENT -->|"kaniko push, tag=commit-SHA"| GHCR
    CIAGENT -->|"build job miklat-cd, wait:false"| JCTRL
    CDAGENT -->|"helm upgrade --install<br/>RBAC: jenkins-cd → miklat-app"| HELM
    CDAGENT -->|curl smoke-test| HELM
    HELM --> SECAPP
    HELM --> RDS
    HELM --> S3
    HELM --> SNS
    ADMIN -.->|"port-forward, NOT via ingress"| JCTRL

    classDef public fill:#f8d7da,stroke:#c0392b,color:#000;
    classDef internal fill:#d6e9f8,stroke:#2c7fb8,color:#000;
    classDef awscls fill:#d5f5d5,stroke:#2e7d32,color:#000;
    classDef prodcls fill:#eeeeee,stroke:#999999,color:#000,stroke-dasharray: 5 5;

    class DEV,GH,GHCR,USER,ADMIN,ING public;
    class JCTRL,PVCJ,CIAGENT,CDAGENT,HELM,SECAPP internal;
    class RDS,S3,SNS awscls;
    class PRODSTACK prodcls;
    class PROD prodcls;
```

![Deployment View](task4-deployment.png)

Key points visible on the diagram:

- The Jenkins controller (`jenkins-0`) is the only long-lived pod in namespace `jenkins`; agents (`ci-agent-*`, `cd-agent-*`) are ephemeral and created/deleted by the controller for every build.
- The only external path into Jenkins is `POST /github-webhook/` through `ingress-nginx`; everything else (`/login`, `/manage`, `/`) on the same Ingress falls through to the `miklat-app` frontend (confirmed in Step 7 via the `X-Jenkins` response header — see the README Security section).
- `ci-agent-*` runs as ServiceAccount `jenkins` with no cluster API permissions; `cd-agent-*` runs as a separate ServiceAccount `jenkins-cd`, scoped only to namespace `miklat-app`.
- Admin access to the Jenkins UI is only via `kubectl port-forward`, never through Ingress.
- The production stack (`shelternearyou.online`) physically runs on the same server (`mbdai`) but is entirely outside the scope of this cluster/Jenkins — no CI/CD component touches it.

---

## 2. Pipeline Flow

Shows the full path of a commit: from `git push` to rollout in `miklat-app`, including the happy path and the rollback on a failed smoke test.

```mermaid
flowchart TD
    START(["git push<br/>(commit to main)"])
    WEBHOOK["GitHub webhook<br/>POST /github-webhook/<br/>HMAC X-Hub-Signature-256"]

    subgraph CI["Job: miklat-ci"]
        direction TB
        CI1["Checkout"]
        CI2["Validate<br/>(repository structure)"]
        CI3["Lint<br/>(flake8 / eslint)"]
        CI4["Tests<br/>(pytest / npm test)"]
        CI5["Detect changed services<br/>(git diff over services/* dirs)"]
        CI6["Build & push (kaniko)<br/>tag = commit SHA"]
        CI7["Publish metadata<br/>(image tag → build artifact)"]
        CI8["Trigger CD<br/>(build job: miklat-cd, wait:false)"]
        CI1 --> CI2 --> CI3 --> CI4 --> CI5 --> CI6 --> CI7 --> CI8
    end

    GHCR[("GHCR<br/>ghcr.io/algoldenberg/&lt;service&gt;:&lt;sha&gt;")]

    subgraph CD["Job: miklat-cd (auto-triggered upstream)"]
        direction TB
        CD1["Validate parameters<br/>(service, image tag)"]
        CD2["Validate manifests<br/>(helm lint / template)"]
        CD3["Authenticate<br/>(SA: jenkins-cd, RBAC → miklat-app)"]
        CD4["Deploy<br/>(helm upgrade --install)"]
        CD5["Rollout status<br/>(kubectl rollout status)"]
        CD6["Verify<br/>(pod image tag == expected)"]
        CD7{"Smoke test<br/>(curl /health)"}
        CD1 --> CD2 --> CD3 --> CD4 --> CD5 --> CD6 --> CD7
    end

    SUCCESS(["Finished: SUCCESS<br/>production namespace miklat-app updated"])
    ROLLBACK["post{failure}<br/>helm rollback miklat-app"]
    FAILED(["Finished: FAILURE<br/>rolled back, alert sent"])

    START --> WEBHOOK --> CI1
    CI6 --> GHCR
    CI8 -.->|"parameters: service, tag"| CD1
    GHCR -.->|"image pull"| CD4
    CD7 -->|OK| SUCCESS
    CD7 -->|"FAIL"| ROLLBACK --> FAILED

    classDef public fill:#f8d7da,stroke:#c0392b,color:#000;
    classDef internal fill:#d6e9f8,stroke:#2c7fb8,color:#000;
    classDef awscls fill:#d5f5d5,stroke:#2e7d32,color:#000;
    classDef fail fill:#f8d7da,stroke:#c0392b,color:#000;
    classDef ok fill:#d5f5d5,stroke:#2e7d32,color:#000;

    class START,WEBHOOK public;
    class CI1,CI2,CI3,CI4,CI5,CI6,CI7,CI8 internal;
    class GHCR public;
    class CD1,CD2,CD3,CD4,CD5,CD6,CD7 internal;
    class SUCCESS ok;
    class ROLLBACK,FAILED fail;
```

![Pipeline Flow](task4-pipeline.png)

Key points:

- `miklat-ci` and `miklat-cd` are separate Jenkins jobs; they're linked not by a webhook or polling but by a direct `build job: 'miklat-cd', wait: false` call at the end of `miklat-ci` (confirmed by a real end-to-end run in Step 6 — commit `742153e` → `miklat-photos` build → `miklat-cd` build #13 auto-triggered with matching parameters).
- `wait:false` means `miklat-ci` does not block waiting for `miklat-cd` — the job is marked successful as soon as `miklat-cd` is queued.
- Rollback (`helm rollback`) lives in the `post{failure}` block of `Jenkinsfile-cd`; it only fires if the smoke test fails, not on any deployment error (which is already caught by the earlier `Deploy`/`Rollout status` stages).
- Images in GHCR are tagged with the commit SHA, not `latest` — this is what makes rollback possible: the previous tag stays available in the registry.
