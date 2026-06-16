"""
Airflow DAG: orchestrates the same ingest -> transform pipeline as the
AWS/GCP/Azure projects, but running on Kubernetes via Airflow instead of
cloud-native triggers.

Requires shared/ to be importable from the Airflow worker (see k8s/README.md).
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from shared.ingest import fetch_data, to_raw_record
from shared.transform import transform_record

default_args = {
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="multicloud_pipeline_local",
    description="Ingest + transform, orchestrated on Kubernetes via Airflow",
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

        # TODO: load `row` into the warehouse of your choice
        # (local Postgres, Redshift, BigQuery, or Azure SQL).
        print("Transformed row:", row)

    ingest = PythonOperator(task_id="ingest", python_callable=_ingest)
    transform = PythonOperator(task_id="transform", python_callable=_transform)

    ingest >> transform
