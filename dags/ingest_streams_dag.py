from datetime import datetime, timedelta, timezone

from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator

with DAG(
    dag_id="ingest_streams",
    description="Twitch top-2000 snapshot to MinIO raw layer",
    start_date=datetime(2026, 11, 1, tzinfo=timezone.utc),
    schedule="*/10 * * * *",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=1)},
    tags=["twitch", "raw"],
) as dag:
    BashOperator(
        task_id="ingest_streams",
        bash_command="python /opt/airflow/src/ingest_streams.py",
    )