from datetime import datetime, timedelta, timezone

from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator

with DAG(
    dag_id="data_quality",
    description="Hourly data quality checks on ClickHouse: ERROR fails the task, WARN skips it",
    start_date=datetime(2026, 11, 1, tzinfo=timezone.utc),
    schedule="40 * * * *",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
    tags=["twitch", "quality"],
) as dag:
    BashOperator(
        task_id="quality_checks",
        bash_command="python /opt/airflow/src/quality_checks.py",
        skip_on_exit_code=99,
    )