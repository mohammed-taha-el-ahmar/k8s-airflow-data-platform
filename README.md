# Kubernetes Capstone — Airflow on K8s

[![CI](https://github.com/<your-username>/k8s-airflow-data-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/<your-username>/k8s-airflow-data-platform/actions/workflows/ci.yml)

> Part of a multi-cloud data engineering pattern — see `PORTFOLIO.md` in the
> companion repos for the cross-cloud comparison. Same `shared/` ingest +
> transform logic as `aws-data-pipeline`, `gcp-data-pipeline`, and
> `azure-data-pipeline`.

A containerized data platform project: orchestrate the same
`shared/ingest.py` + `shared/transform.py` logic with **Apache Airflow
running on Kubernetes**, instead of cloud-native serverless triggers. This
demonstrates container orchestration on top of pure cloud-service knowledge.

No managed cluster (EKS / GKE / AKS) is required — [**kind**][kind] gives
you a full Kubernetes cluster inside Docker, keeping everything local and
free.

[kind]: https://kind.sigs.k8s.io/

---

## Prerequisites

| Tool | Minimum version | Install |
|------|----------------|---------|
| **Docker Desktop** | 24+ | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |
| **kubectl** | 1.28+ | `brew install kubectl` |
| **Helm** | 3.14+ | `brew install helm` |
| **kind** | 0.22+ | `go install sigs.k8s.io/kind@latest` *(see note below)* |
| **Go** *(only to install kind)* | 1.21+ | `brew install go` |

> **kind PATH gotcha (macOS / Linux):**  `go install` places binaries in
> `$(go env GOPATH)/bin` (usually `~/go/bin`). If you get
> `zsh: command not found: kind`, add this to your `~/.zshrc`:
>
> ```bash
> export PATH="$HOME/go/bin:$PATH"
> ```
>
> Then `source ~/.zshrc` or open a new terminal.

---

## Quick-Start Setup

```bash
# 1. Create the local Kubernetes cluster
kind create cluster --name data-platform

# 2. Verify the cluster is healthy
kubectl cluster-info --context kind-data-platform
kubectl get nodes

# 3. Create the project namespace
kubectl apply -f manifests/namespace.yaml

# 4. Add the Airflow Helm repo & install Airflow
helm repo add apache-airflow https://airflow.apache.org
helm repo update
helm install airflow apache-airflow/airflow \
  --namespace data-platform \
  --set executor=LocalExecutor \
  --timeout 10m

# 5. Wait for all pods to become Ready
kubectl get pods -n data-platform -w          # Ctrl-C once all are Running

# 6. Port-forward the Airflow UI
#    Airflow 3.x uses "api-server" instead of "webserver"
kubectl port-forward svc/airflow-api-server 8080:8080 -n data-platform
# Open http://localhost:8080  (default creds: admin / admin)
```

### Loading the DAG

In Airflow 3.x the **dag-processor** parses DAGs in its own pod, so files
must be copied to both the scheduler *and* the dag-processor:

```bash
# Identify the pods
SCHEDULER=$(kubectl get pods -n data-platform \
  -l component=scheduler -o jsonpath='{.items[0].metadata.name}')
DAG_PROC=$(kubectl get pods -n data-platform \
  -l component=dag-processor -o jsonpath='{.items[0].metadata.name}')

# Copy DAG + shared package to both pods
for POD in $SCHEDULER $DAG_PROC; do
  kubectl cp dags/pipeline_dag.py  data-platform/$POD:/opt/airflow/dags/pipeline_dag.py
  kubectl cp shared/               data-platform/$POD:/opt/airflow/dags/shared/
done
```

For a persistent approach, configure `dags.gitSync` in the Helm values to
pull from this repo automatically — see [docs/architecture.md](docs/architecture.md).

---

## Running a Demo

Once all pods are `Running` and the DAG is loaded (steps above):

```bash
# 1. Trigger a manual DAG run
kubectl exec $SCHEDULER -c scheduler -n data-platform -- \
  airflow dags trigger multicloud_pipeline_local

# 2. Watch the run complete (~5–10 s)
kubectl exec $SCHEDULER -c scheduler -n data-platform -- \
  airflow dags list-runs multicloud_pipeline_local

# 3. Verify data landed in PostgreSQL
kubectl exec airflow-postgresql-0 -n data-platform -- \
  env PGPASSWORD=postgres psql -U postgres -c \
  "SELECT id, ingested_at, temperature_c, wind_speed_kmh, humidity_pct
   FROM weather_observations ORDER BY ingested_at DESC;"
```

### Viewing the Dashboard

A Streamlit dashboard is included to visualise pipeline results in real time:

```bash
# Build & load the dashboard image into kind
docker build -t pipeline-dashboard:latest dashboard/
kind load docker-image pipeline-dashboard:latest --name data-platform

# Deploy the dashboard
kubectl apply -f manifests/dashboard.yaml

# Port-forward to localhost
kubectl port-forward svc/dashboard 8501:8501 -n data-platform
# → http://localhost:8501
```

The dashboard shows:
- **Key metrics** — latest temperature, wind speed, humidity
- **Historical trend charts** — temperature, wind, and humidity over time
- **Summary statistics** and a raw data table

It auto-refreshes every 15 seconds as new pipeline runs land data.

### Viewing the Airflow UI

```bash
kubectl port-forward svc/airflow-api-server 8080:8080 -n data-platform
# → http://localhost:8080  (admin / admin)
```

---

## Project Layout

```
├── .github/workflows/
│   └── ci.yml                # GitHub Actions: lint + unit tests + kind smoke test
├── README.md                 # ← you are here
├── pyproject.toml            # Ruff & pytest config
├── dags/
│   └── pipeline_dag.py       # Airflow DAG: ingest → transform → load
├── dashboard/
│   ├── app.py                # Streamlit dashboard (reads from PostgreSQL)
│   ├── Dockerfile            # Container image for the dashboard
│   └── requirements.txt      # Dashboard Python deps
├── docs/
│   ├── architecture.md       # Design decisions & component map
│   ├── commands.md           # Quick-reference kubectl / Helm / Airflow commands
│   └── troubleshooting.md    # Common errors & fixes
├── manifests/
│   ├── dashboard.yaml        # K8s Deployment + Service for the dashboard
│   └── namespace.yaml        # Kubernetes namespace manifest
├── shared/
│   ├── __init__.py
│   ├── ingest.py              # Fetch data from Open-Meteo API
│   ├── transform.py           # Flatten raw record → warehouse row
│   ├── load.py                # Write transformed rows to PostgreSQL
│   └── requirements.txt       # Python deps (psycopg2-binary for load)
└── tests/
    ├── test_ingest.py         # Unit tests for ingestion logic
    ├── test_transform.py      # Unit tests for transform logic
    └── test_load.py           # Unit tests for load logic (mocked DB)
```

---

## What This Demonstrates

- **Cross-cloud portability** — The identical `shared/` module powers
  AWS Lambda, GCP Cloud Functions, Azure Functions, *and* this Kubernetes
  deployment.
- **Self-managed orchestration** — You own the scheduling layer (Airflow)
  instead of relying on EventBridge / Cloud Scheduler / Data Factory.
- **End-to-end data pipeline** — Ingest from a live API → transform →
  load into PostgreSQL → visualise on a Streamlit dashboard.
- **Kubernetes fundamentals** — Namespaces, Helm chart lifecycle, custom
  Docker images, pod inspection, log tailing, port-forwarding.
- **Natural extension point** — Swap `PythonOperator` for
  `KubernetesPodOperator` so each task runs in its own isolated pod with
  resource limits.

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **kind over minikube** | Lighter weight; runs real K8s nodes as Docker containers; easier CI integration. |
| **Official Airflow Helm chart** | Community-maintained, production-grade defaults, simple `values.yaml` overrides. |
| **`LocalExecutor`** | No need for Celery / Redis in a single-node demo; fewer moving parts. |
| **`PythonOperator` first** | Fastest path to a working pipeline; upgrade to `KubernetesPodOperator` when needed. |
| **`shared/` as a plain package** | Stays cloud-agnostic; zero extra dependencies; importable anywhere Python runs. |
| **Streamlit dashboard** | Lightweight, Python-native, zero-JS setup; perfect for data teams and portfolio demos. |
| **Reuse Airflow's PostgreSQL** | Avoids deploying a second database; the `weather_observations` table is isolated from Airflow metadata. |

See [docs/architecture.md](docs/architecture.md) for the full architecture
diagram and deeper rationale.

---

## Useful Commands

A curated cheatsheet lives in [docs/commands.md](docs/commands.md). Highlights:

```bash
# Cluster status
kubectl get nodes
kubectl get pods -n data-platform

# Tail Airflow scheduler logs
kubectl logs -f sts/airflow-scheduler -n data-platform

# Restart Airflow after config changes
helm upgrade airflow apache-airflow/airflow -n data-platform

# Tear everything down
helm uninstall airflow -n data-platform
kind delete cluster --name data-platform
```

---

## CI / GitHub Actions

Every push and PR runs a two-job pipeline defined in
[`.github/workflows/ci.yml`](.github/workflows/ci.yml):

| Job | ~Duration | What it does |
|-----|-----------|-------------|
| **lint-and-test** | 30 s | Ruff lint + format check, `py_compile` on the DAG, 12 unit tests via pytest |
| **smoke-test** | 8–12 min | Spins up a kind cluster → installs Airflow via Helm → copies DAG → triggers a run → verifies data in PostgreSQL → builds and deploys the dashboard |

Run the fast checks locally:

```bash
pip install ruff pytest psycopg2-binary
ruff check .             # lint
ruff format --check .    # format
pytest tests/ -v         # unit tests
```

---

## Troubleshooting

Common issues and their fixes are documented in
[docs/troubleshooting.md](docs/troubleshooting.md). Quick links:

- [`kind` not found after `go install`](#prerequisites)
- [Pods stuck in `Pending` / `CrashLoopBackOff`](docs/troubleshooting.md#pods-stuck-in-pending)
- [DAG not showing in Airflow UI](docs/troubleshooting.md#dag-not-visible)
- [Port-forward drops after a few minutes](docs/troubleshooting.md#port-forward-drops)

---

## Cleanup

Three levels of cleanup, from lightest to full teardown:

```bash
# Level 1 — Remove Airflow only (keep the cluster for other experiments)
helm uninstall airflow -n data-platform

# Level 2 — Also remove the namespace and all its resources
kubectl delete namespace data-platform

# Level 3 — Delete the entire kind cluster (removes everything)
kind delete cluster --name data-platform

# Optional — reclaim disk space used by pulled container images
docker system prune -f
```

> **Tip:** kind clusters are disposable. To start fresh, just run the
> [Quick-Start Setup](#quick-start-setup) again (~3 min on a modern machine).

See [docs/commands.md](docs/commands.md#cleanup) for the full cleanup
reference.

---

## TODOs

- [x] ~~Replace the `print("Transformed row:", row)` stub with a real load
      into PostgreSQL.~~
- [x] ~~Add a dashboard to visualise pipeline results.~~
- [ ] Package `shared/` as a pip-installable package (or mount as a volume)
      so `pipeline_dag.py` can import it cleanly.
- [ ] Add resource requests / limits and a `KubernetesPodOperator` variant
      so each task runs in its own pod.
- [ ] Add a Helm `values.yaml` override file for reproducible installs.
- [ ] Set up `dags.gitSync` to auto-pull DAGs from this repo.
- [x] ~~Add CI (GitHub Actions) to lint the DAG and run a `kind` smoke test.~~
