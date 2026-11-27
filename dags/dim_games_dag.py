from datetime import datetime, timedelta, timezone

from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator

with DAG(
    dag_id="dim_games",
    description="Twitch games + IGDB genres: raw in S3, then dim_games in ClickHouse",
    start_date=datetime(2026, 11, 1, tzinfo=timezone.utc),
    schedule="0 6 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=2)},
    tags=["twitch", "dimension"],
) as dag:
    fetch = BashOperator(
        task_id="fetch_games_to_raw",
        bash_command="python /opt/airflow/src/ingest_games.py",
    )
    load = BashOperator(
        task_id="load_dim_games",
        bash_command="python /opt/airflow/src/load_games.py",
    )
    fetch >> load