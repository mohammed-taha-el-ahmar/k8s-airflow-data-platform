# Kubernetes capstone — Airflow on K8s

> Part of a multi-cloud data engineering pattern — see `PORTFOLIO.md` in the
> companion repos for the cross-cloud comparison. Same `shared/` ingest +
> transform logic as `aws-data-pipeline`, `gcp-data-pipeline`, and
> `azure-data-pipeline`.

A separate "containerized data platform" project: orchestrate the same
`shared/ingest.py` + `shared/transform.py` logic with Airflow running on
Kubernetes, instead of cloud-native serverless triggers. This is the piece
that demonstrates container orchestration on top of pure cloud-service
knowledge.

No need for a managed cluster (EKS/GKE/AKS) to demonstrate this — `kind` or
`minikube` is enough for a portfolio project, and keeps it free.

## Setup (local cluster)

```bash
# 1. Create a local cluster
kind create cluster --name data-platform

# 2. Create the namespace
kubectl apply -f manifests/namespace.yaml

# 3. Install Airflow via the official Helm chart
helm repo add apache-airflow https://airflow.apache.org
helm install airflow apache-airflow/airflow --namespace data-platform

# 4. Add dags/pipeline_dag.py to the DAGs folder (via the chart's
#    dags.gitSync config, or copy into the scheduler pod for a quick demo)
```

## What this demonstrates

- Packaging `shared/` as an installable dependency for Airflow tasks
  (rather than reimplementing logic per cloud)
- Running the **same pipeline pattern** as the AWS/GCP/Azure projects, but
  with you owning the orchestration layer instead of relying on
  EventBridge / Cloud Scheduler / ADF triggers
- A natural extension point: have `transform` load into whichever warehouse
  you want (the local Postgres from `docker/`, or any of the cloud
  warehouses, via credentials passed as Kubernetes secrets)

## TODOs

- [ ] Package `shared/` (e.g. as a small pip-installable package or a
      mounted volume) so `dags/pipeline_dag.py` can import it.
- [ ] Replace the `print("Transformed row:", row)` placeholder in the
      `transform` task with a real load into your chosen warehouse.
- [ ] Add resource requests/limits and a `KubernetesPodOperator` variant if
      you want each task to run in its own pod (closer to a "real" data
      platform than the default `PythonOperator`).
