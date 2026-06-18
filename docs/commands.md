# Commands Cheatsheet

Quick-reference for the most common operations in this project.

---

## Cluster Lifecycle (kind)

```bash
# Create the cluster
kind create cluster --name data-platform

# List clusters
kind get clusters

# Delete the cluster (tears down everything)
kind delete cluster --name data-platform

# Re-create from scratch (nuclear option)
kind delete cluster --name data-platform && kind create cluster --name data-platform
```

---

## Namespace

```bash
# Create the namespace
kubectl apply -f manifests/namespace.yaml

# Set as default so you can omit -n data-platform
kubectl config set-context --current --namespace=data-platform

# List all resources in the namespace
kubectl get all -n data-platform
```

---

## Helm — Airflow Install & Upgrade

```bash
# Add the repo (first time only)
helm repo add apache-airflow https://airflow.apache.org
helm repo update

# Install Airflow
helm install airflow apache-airflow/airflow \
  --namespace data-platform \
  --set executor=LocalExecutor \
  --timeout 10m

# Check release status
helm status airflow -n data-platform

# Show current values
helm get values airflow -n data-platform

# Upgrade (after changing values)
helm upgrade airflow apache-airflow/airflow \
  -n data-platform \
  --set executor=LocalExecutor \
  --timeout 10m

# Uninstall Airflow (keeps the namespace)
helm uninstall airflow -n data-platform
```

### Install with a custom values file

```bash
helm install airflow apache-airflow/airflow \
  -n data-platform \
  -f manifests/airflow-values.yaml \
  --timeout 10m
```

---

## Pod Inspection

```bash
# List pods (wide view with node / IP)
kubectl get pods -n data-platform -o wide

# Watch pods until all are Running
kubectl get pods -n data-platform -w

# Describe a specific pod (events, conditions, mounts)
kubectl describe pod <POD_NAME> -n data-platform

# Get pod resource usage (requires metrics-server)
kubectl top pods -n data-platform
```

---

## Logs

```bash
# Tail scheduler logs (live) — scheduler is a StatefulSet in Airflow 3.x
kubectl logs -f sts/airflow-scheduler -n data-platform

# Tail API server logs (replaces webserver in Airflow 3.x)
kubectl logs -f deploy/airflow-api-server -n data-platform

# Last 50 lines from a specific pod
kubectl logs --tail=50 <POD_NAME> -n data-platform

# Logs from the previous (crashed) container
kubectl logs <POD_NAME> -n data-platform --previous
```

---

## Port-Forwarding

```bash
# Airflow UI (API server) → http://localhost:8080
kubectl port-forward svc/airflow-api-server 8080:8080 -n data-platform

# Streamlit Dashboard → http://localhost:8501
kubectl port-forward svc/dashboard 8501:8501 -n data-platform

# Both at once (background the first)
kubectl port-forward svc/airflow-api-server 8080:8080 -n data-platform &
kubectl port-forward svc/dashboard 8501:8501 -n data-platform &

# Kill all backgrounded port-forwards
pkill -f "port-forward.*data-platform"
```

Default credentials: **admin / admin**

---

## DAG Management

```bash
# Identify both pods that need DAG files (Airflow 3.x)
SCHEDULER=$(kubectl get pods -n data-platform \
  -l component=scheduler -o jsonpath='{.items[0].metadata.name}')
DAG_PROC=$(kubectl get pods -n data-platform \
  -l component=dag-processor -o jsonpath='{.items[0].metadata.name}')

# Copy DAG + shared package into both pods
for POD in $SCHEDULER $DAG_PROC; do
  kubectl cp dags/pipeline_dag.py  data-platform/$POD:/opt/airflow/dags/pipeline_dag.py
  kubectl cp shared/               data-platform/$POD:/opt/airflow/dags/shared/
done

# Verify files are present
kubectl exec $SCHEDULER  -c scheduler     -n data-platform -- ls /opt/airflow/dags/
kubectl exec $DAG_PROC   -c dag-processor -n data-platform -- ls /opt/airflow/dags/

# Manually trigger a DAG run
kubectl exec $SCHEDULER -c scheduler -n data-platform -- \
  airflow dags trigger multicloud_pipeline_local

# List DAGs known to Airflow
kubectl exec $SCHEDULER -c scheduler -n data-platform -- airflow dags list

# Check recent DAG runs
kubectl exec $SCHEDULER -c scheduler -n data-platform -- \
  airflow dags list-runs multicloud_pipeline_local

# Check for import errors (silent failures that hide DAGs)
kubectl exec $SCHEDULER -c scheduler -n data-platform -- \
  airflow dags list-import-errors

# Unpause a DAG
kubectl exec $SCHEDULER -c scheduler -n data-platform -- \
  airflow dags unpause multicloud_pipeline_local

# Run a single task in test/foreground mode (great for debugging)
kubectl exec $SCHEDULER -c scheduler -n data-platform -- \
  airflow tasks test multicloud_pipeline_local transform 2026-06-18
```

---

## Dashboard

```bash
# Build the Docker image
docker build -t pipeline-dashboard:latest dashboard/

# Load the image into kind (so the cluster can use it)
kind load docker-image pipeline-dashboard:latest --name data-platform

# Deploy (or re-deploy after code changes)
kubectl apply -f manifests/dashboard.yaml

# Check the pod is running
kubectl get pods -n data-platform -l app=dashboard

# View logs
kubectl logs -f deploy/dashboard -n data-platform

# Port-forward → http://localhost:8501
kubectl port-forward svc/dashboard 8501:8501 -n data-platform

# Rebuild & redeploy after changing dashboard/app.py
docker build -t pipeline-dashboard:latest dashboard/
kind load docker-image pipeline-dashboard:latest --name data-platform
kubectl rollout restart deploy/dashboard -n data-platform
```

---

## PostgreSQL (data warehouse)

```bash
# Query the weather_observations table
kubectl exec airflow-postgresql-0 -n data-platform -- \
  env PGPASSWORD=postgres psql -U postgres -c \
  "SELECT * FROM weather_observations ORDER BY ingested_at DESC;"

# Count rows
kubectl exec airflow-postgresql-0 -n data-platform -- \
  env PGPASSWORD=postgres psql -U postgres -c \
  "SELECT count(*) FROM weather_observations;"

# Interactive psql session
kubectl exec -it airflow-postgresql-0 -n data-platform -- \
  env PGPASSWORD=postgres psql -U postgres
```

---

## Debugging

```bash
# Open a shell inside the scheduler pod
kubectl exec -it $SCHEDULER -n data-platform -- /bin/bash

# Test that shared/ is importable
kubectl exec -it $SCHEDULER -n data-platform -- \
  python -c "from shared.ingest import fetch_data; print(fetch_data())"

# Check Airflow config value
kubectl exec -it $SCHEDULER -n data-platform -- \
  airflow config get-value core executor

# Dump events for the namespace (useful for scheduling / image-pull issues)
kubectl get events -n data-platform --sort-by='.lastTimestamp'

# DNS test from inside a pod
kubectl exec -it $SCHEDULER -n data-platform -- nslookup airflow-postgresql
```

---

## Cleanup

Three graduated levels — pick the one that matches your intent.

### Level 1 — Remove Airflow (keep the cluster)

Use this to reinstall a different chart version or reset Airflow state.

```bash
# Uninstall the Helm release
helm uninstall airflow -n data-platform

# Verify — should show no pods
kubectl get pods -n data-platform

# If PVCs linger (Postgres data), delete them too
kubectl delete pvc --all -n data-platform
```

### Level 2 — Remove the namespace (keep the cluster)

Deletes all resources (pods, services, secrets, PVCs) in `data-platform`.

```bash
kubectl delete namespace data-platform

# Verify — namespace should be gone
kubectl get namespaces
```

### Level 3 — Delete the entire cluster

Removes the kind cluster and all Docker containers backing it.

```bash
kind delete cluster --name data-platform

# Verify — should no longer appear
kind get clusters

# Remove the kubeconfig context (optional, keeps config tidy)
kubectl config delete-context kind-data-platform 2>/dev/null
kubectl config delete-cluster kind-data-platform 2>/dev/null
```

### Reclaim disk space (optional)

```bash
# Remove unused Docker images, build cache, and stopped containers
docker system prune -f

# Nuclear option — also remove ALL unused images (not just dangling)
docker system prune -a -f

# Check how much space Docker is using
docker system df
```

### Start fresh

```bash
# Full reset in one shot
kind delete cluster --name data-platform \
  && kind create cluster --name data-platform \
  && kubectl apply -f manifests/namespace.yaml \
  && helm repo update \
  && helm install airflow apache-airflow/airflow \
       -n data-platform --set executor=LocalExecutor --timeout 10m
```

Total time: ~3 minutes on a modern machine.
