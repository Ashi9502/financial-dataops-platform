from datetime import timedelta

import pendulum
from airflow.sdk import dag, task


@dag(
    dag_id="transactions_incremental_ingestion",
    schedule=None,
    start_date=pendulum.datetime(
        2026,
        10,
        1,
        tz="UTC",
    ),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=20),
    tags=[
        "financial-dataops",
        "incremental-ingestion",
        "dbt",
        "data-quality",
    ],
)
def transactions_incremental_ingestion():

    @task(
        task_id="extract_transactions",
        retries=2,
        retry_delay=timedelta(seconds=15),
    )
    def extract_transactions():
        from src.ingestion.extract_transactions import main

        main()

    @task(
        task_id="load_transactions",
        retries=2,
        retry_delay=timedelta(seconds=15),
    )
    def load_transactions():
        from src.ingestion.load_transactions import main

        main()

    @task(
        task_id="sync_reference_data",
        retries=2,
        retry_delay=timedelta(seconds=15),
    )
    def sync_reference_data():
        from src.ingestion.sync_reference_data import main

        main()

    @task(
        task_id="dbt_build",
        retries=1,
        retry_delay=timedelta(seconds=15),
    )
    def dbt_build():
        import os
        import subprocess

        env = os.environ.copy()

        env["DBT_ENGINE_TARGET_PATH"] = "/tmp/dbt-target"
        env["DBT_ENGINE_LOG_PATH"] = "/tmp/dbt-logs"

        subprocess.run(
            [
                "/opt/airflow/dataops-venv/bin/dbt",
                "build",
                "--project-dir",
                "/opt/airflow/project/dbt",
                "--profiles-dir",
                "/opt/airflow/project/dbt",
            ],
            check=True,
            env=env,
            cwd="/opt/airflow/project",
        )

    @task(
        task_id="gx_quality_gate",
        retries=0,
    )
    def gx_quality_gate():
        import os
        import subprocess

        env = os.environ.copy()
        env["PYTHONPATH"] = "/opt/airflow/project"

        subprocess.run(
            [
                "/opt/airflow/dataops-venv/bin/python",
                "-m",
                "src.quality.run_quality_gates",
            ],
            check=True,
            env=env,
            cwd="/opt/airflow/project",
        )

    extract = extract_transactions()
    load = load_transactions()
    reference = sync_reference_data()
    transform = dbt_build()
    quality = gx_quality_gate()

    extract >> load >> reference >> transform >> quality


transactions_incremental_ingestion()
