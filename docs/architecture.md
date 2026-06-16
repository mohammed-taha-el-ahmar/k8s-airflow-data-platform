# Architecture

```mermaid
flowchart LR
    subgraph Kubernetes cluster
        S[Airflow scheduler] --> T1[Task: ingest pod]
        T1 --> T2[Task: transform pod]
    end
    T1 --> O[(Object storage)]
    T2 --> W[(Warehouse)]
```

This repo is the orchestration-focused counterpart to `aws-data-pipeline`,
`gcp-data-pipeline`, and `azure-data-pipeline` — same `shared/` ingest +
transform logic, but the scheduling/triggering layer is Airflow on
Kubernetes instead of EventBridge / Cloud Scheduler / Data Factory.
