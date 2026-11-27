from datetime import datetime, timedelta, timezone

from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator

SPARK_ENV = (
    'export PYSPARK_SUBMIT_ARGS="--master local[2] --driver-memory 2g pyspark-shell" '
    "&& export PYSPARK_PYTHON=python && "
)

with DAG(
    dag_id="staging_and_load",
    description="raw JSON -> Spark -> staging Parquet -> ClickHouse (last 2 days, hourly)",
    start_date=datetime(2026, 11, 1, tzinfo=timezone.utc),
    schedule="15 * * * *",
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
        "execution_timeout": timedelta(minutes=30),
    },
    tags=["twitch", "staging"],
) as dag:
    spark_staging = BashOperator(
        task_id="spark_raw_to_staging",
        bash_command=SPARK_ENV + "python /opt/airflow/spark_jobs/write_staging.py --last-days 2",
    )
    load_clickhouse = BashOperator(
        task_id="load_staging_to_clickhouse",
        bash_command="python /opt/airflow/src/load_staging.py --last-days 2",
    )
    spark_staging >> load_clickhouse