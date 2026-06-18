# Troubleshooting

Common issues you may hit while running this project, and how to fix them.

---

## `kind` Not Found After `go install`

**Symptom:**

```
zsh: command not found: kind
```

**Cause:** `go install` puts binaries in `$(go env GOPATH)/bin` (defaults to
`~/go/bin`), which isn't in your shell's `PATH`.

**Fix:**

```bash
# Quick fix for the current session
export PATH="$HOME/go/bin:$PATH"

# Permanent fix — add to ~/.zshrc (or ~/.bashrc)
echo 'export PATH="$HOME/go/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**Verify:** `which kind` should print `~/go/bin/kind`.

---

## Docker Not Running

**Symptom:**

```
ERROR: failed to create cluster: ...
Cannot connect to the Docker daemon at unix:///var/run/docker.sock
```

**Fix:** Start Docker Desktop (or `colima start` if using Colima), then
retry `kind create cluster --name data-platform`.

---

## Pods Stuck in `Pending` {#pods-stuck-in-pending}

**Symptom:** `kubectl get pods -n data-platform` shows one or more pods in
`Pending` state for several minutes.

**Common causes & fixes:**

| Cause | How to check | Fix |
|-------|-------------|-----|
| Insufficient CPU/memory | `kubectl describe pod <NAME> -n data-platform` → look for `FailedScheduling` event | Increase Docker Desktop resources (≥ 4 CPU, ≥ 8 GB RAM recommended) |
| PVC not bound | `kubectl get pvc -n data-platform` shows `Pending` | kind ships a default `StorageClass`; if missing, re-create the cluster |
| Image pull error | `describe pod` shows `ImagePullBackOff` | Check internet connectivity; retry (`kubectl delete pod <NAME> -n data-platform`) |

---

## Pods in `CrashLoopBackOff`

**Symptom:** A pod repeatedly restarts.

**Debug steps:**

```bash
# 1. Check why it crashed
kubectl logs <POD_NAME> -n data-platform --previous

# 2. Look for OOMKilled
kubectl describe pod <POD_NAME> -n data-platform | grep -A2 "Last State"

# 3. If the DB migration failed (common with airflow-migrations job)
kubectl logs job/airflow-run-airflow-migrations -n data-platform
```

**Common fixes:**
- **OOMKilled** → Give Docker Desktop more memory (≥ 8 GB).
- **DB migration timeout** → Delete the release and reinstall:
  ```bash
  helm uninstall airflow -n data-platform
  helm install airflow apache-airflow/airflow -n data-platform \
    --set executor=LocalExecutor --timeout 10m
  ```

---

## DAG Not Visible in the Airflow UI {#dag-not-visible}

**Symptom:** You open `http://localhost:8080` but
`multicloud_pipeline_local` is not listed.

**Checklist:**

1. **File not copied yet** — In Airflow 3.x, DAGs must be present in both
   the **scheduler** and **dag-processor** pods:
   ```bash
   SCHEDULER=$(kubectl get pods -n data-platform \
     -l component=scheduler -o jsonpath='{.items[0].metadata.name}')
   DAG_PROC=$(kubectl get pods -n data-platform \
     -l component=dag-processor -o jsonpath='{.items[0].metadata.name}')
   kubectl exec $SCHEDULER -c scheduler     -n data-platform -- ls /opt/airflow/dags/
   kubectl exec $DAG_PROC  -c dag-processor -n data-platform -- ls /opt/airflow/dags/
   ```
2. **Import error** — The dag-processor silently hides DAGs with import errors.
   Check:
   ```bash
   kubectl exec $SCHEDULER -c scheduler -n data-platform -- \
     airflow dags list-import-errors
   ```
   If it says `No module named 'shared'`, copy the `shared/` directory to
   **both** pods:
   ```bash
   for POD in $SCHEDULER $DAG_PROC; do
     kubectl cp shared/ data-platform/$POD:/opt/airflow/dags/shared/
   done
   ```
3. **DAG is paused** — New DAGs default to paused. Click the toggle in the
   UI, or:
   ```bash
   kubectl exec $SCHEDULER -n data-platform -- \
     airflow dags unpause multicloud_pipeline_local
   ```
4. **Scheduler hasn't picked it up yet** — The file watcher interval
   defaults to 30 s. Wait a moment, or restart both the scheduler and
   dag-processor:
   ```bash
   kubectl rollout restart sts/airflow-scheduler -n data-platform
   kubectl rollout restart deploy/airflow-dag-processor -n data-platform
   ```

---

## Port-Forward Drops After a Few Minutes {#port-forward-drops}

**Symptom:** `kubectl port-forward` exits with
`error: lost connection to pod`.

**Why:** `kubectl port-forward` is a debugging tool, not a production proxy.
It drops idle connections.

**Workarounds:**

```bash
# Re-run automatically when it drops
while true; do
  kubectl port-forward svc/airflow-api-server 8080:8080 -n data-platform
  echo "Connection lost — reconnecting in 2s…"
  sleep 2
done
```

Or use a `NodePort` service instead:

```bash
kubectl patch svc airflow-api-server -n data-platform \
  -p '{"spec": {"type": "NodePort"}}'
```

---

## Helm Install Times Out

**Symptom:**

```
Error: timed out waiting for the condition
```

**Cause:** The Airflow migration job or database init takes too long on a
resource-constrained machine.

**Fix:**

```bash
# 1. Check what's still running
kubectl get pods -n data-platform

# 2. Increase timeout and retry
helm uninstall airflow -n data-platform
helm install airflow apache-airflow/airflow \
  -n data-platform \
  --set executor=LocalExecutor \
  --timeout 15m
```

Also ensure Docker Desktop has **≥ 4 CPU cores** and **≥ 8 GB memory**
allocated (Settings → Resources).

---

## `kubectl` Uses the Wrong Context

**Symptom:** Commands target the wrong cluster or return
`The connection to the server localhost:8080 was refused`.

**Fix:**

```bash
# List available contexts
kubectl config get-contexts

# Switch to the kind context
kubectl config use-context kind-data-platform

# Verify
kubectl cluster-info
```

---

## Stale Cluster / Starting Fresh

When in doubt, tear everything down and rebuild — kind clusters are
disposable:

```bash
kind delete cluster --name data-platform
kind create cluster --name data-platform
kubectl apply -f manifests/namespace.yaml
helm install airflow apache-airflow/airflow \
  -n data-platform --set executor=LocalExecutor --timeout 10m
```

Total time: ~3 minutes on a modern machine.

See [docs/commands.md — Cleanup](commands.md#cleanup) for the full graduated
cleanup reference.

---

## Airflow 3.x vs 2.x Gotchas

The latest Helm chart installs **Airflow 3.x** by default. Several things
changed from 2.x tutorials you may find online:

| What changed | Airflow 2.x | Airflow 3.x |
|-------------|-------------|-------------|
| **Web UI service** | `svc/airflow-webserver` | `svc/airflow-api-server` |
| **DAG parsing** | Done by the scheduler | Dedicated `dag-processor` pod |
| **Scheduler resource** | `Deployment` | `StatefulSet` |
| **PythonOperator import** | `airflow.operators.python` | `airflow.providers.standard.operators.python` |
| **DAG file copies** | Copy to scheduler pod only | Copy to **both** scheduler and dag-processor pods |

**Symptom examples:**

```
# "Service not found" when port-forwarding
Error from server (NotFound): services "airflow-webserver" not found
→ Fix: use svc/airflow-api-server

# DAG copied but not showing up
→ Fix: also copy to the dag-processor pod

# DeprecatedImportWarning in logs
→ Fix: use airflow.providers.standard.operators.python.PythonOperator
```
