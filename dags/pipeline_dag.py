"""
Airflow DAG: orchestrates the same ingest -> transform pipeline as the
AWS/GCP/Azure projects, but running on Kubernetes via Airflow instead of
cloud-native triggers.

Requires shared/ to be importable from the Airflow worker (see k8s/README.md).
"""

from datetime import datetime, timedelta

from airflow import DAG

try:
    # Airflow 3.x
    from airflow.providers.standard.operators.python import PythonOperator
except ImportError:
    # Airflow 2.x fallback
    from airflow.operators.python import PythonOperator

from shared.ingest import fetch_data, to_raw_record
from shared.load import load_row
from shared.transform import transform_record

default_args = {
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="multicloud_pipeline_local",
    description="Ingest + transform + load, orchestrated on Kubernetes via Airflow",
    schedule="@hourly",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
) as dag:

    def _ingest(**context):
        raw = to_raw_record(fetch_data())
        context["ti"].xcom_push(key="raw", value=raw)

    def _transform(**context):
        raw = context["ti"].xcom_pull(key="raw", task_ids="ingest")
        row = transform_record(raw)
        context["ti"].xcom_push(key="row", value=row)

    def _load(**context):
        row = context["ti"].xcom_pull(key="row", task_ids="transform")
        row_id = load_row(row)
        print(f"Loaded row id={row_id}: {row}")

    ingest = PythonOperator(task_id="ingest", python_callable=_ingest)
    transform = PythonOperator(task_id="transform", python_callable=_transform)
    load = PythonOperator(task_id="load", python_callable=_load)

    ingest >> transform >> load
