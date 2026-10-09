from datetime import timedelta

import pendulum
from airflow.sdk import dag, get_current_context, task


@dag(
    dag_id="settlement_reconciliation",
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
        "settlements",
        "reconciliation",
        "dbt",
    ],
)
def settlement_reconciliation():

    @task(
        task_id="load_settlement_file",
        retries=2,
        retry_delay=timedelta(seconds=15),
    )
    def load_settlement_file():
        import re
        import sys
        from pathlib import Path

        from src.ingestion.load_settlement_file import main

        context = get_current_context()
        dag_run = context["dag_run"]
        conf = dag_run.conf or {}

        file_name = conf.get(
            "file_name",
            "settlements_baseline.csv",
        )

        scenario = conf.get(
            "scenario",
            "baseline",
        )

        if Path(file_name).name != file_name:
            raise ValueError(
                "file_name must be a plain filename."
            )

        if not re.fullmatch(
            r"[a-z0-9_]+",
            scenario,
        ):
            raise ValueError(
                "scenario may contain only "
                "lowercase letters, numbers, "
                "and underscores."
            )

        file_path = (
            "/opt/airflow/project/"
            "data/raw/partner_settlements/"
            f"{file_name}"
        )

        if not Path(file_path).is_file():
            raise FileNotFoundError(file_path)

        print(f"settlement_file={file_name}")
        print(f"settlement_scenario={scenario}")

        original_argv = sys.argv[:]

        try:
            sys.argv = [
                "load_settlement_file",
                "--file",
                file_path,
                "--scenario",
                scenario,
            ]

            main()

        finally:
            sys.argv = original_argv

    @task(
        task_id="dbt_reconciliation_build",
        retries=1,
        retry_delay=timedelta(seconds=15),
    )
    def dbt_reconciliation_build():
        import os
        import subprocess

        env = os.environ.copy()

        env["DBT_ENGINE_TARGET_PATH"] = (
            "/tmp/dbt-settlement-target"
        )

        env["DBT_ENGINE_LOG_PATH"] = (
            "/tmp/dbt-settlement-logs"
        )

        subprocess.run(
            [
                "/opt/airflow/dataops-venv/bin/dbt",
                "build",
                "--project-dir",
                "/opt/airflow/project/dbt",
                "--profiles-dir",
                "/opt/airflow/project/dbt",
                "--select",
                "+fct_reconciliation",
            ],
            check=True,
            env=env,
            cwd="/opt/airflow/project",
        )

    @task(
        task_id="reconciliation_assertions",
        retries=0,
    )
    def reconciliation_assertions():
        import os
        import subprocess

        env = os.environ.copy()

        env["DBT_ENGINE_TARGET_PATH"] = (
            "/tmp/dbt-settlement-test-target"
        )

        env["DBT_ENGINE_LOG_PATH"] = (
            "/tmp/dbt-settlement-test-logs"
        )

        subprocess.run(
            [
                "/opt/airflow/dataops-venv/bin/dbt",
                "test",
                "--project-dir",
                "/opt/airflow/project/dbt",
                "--profiles-dir",
                "/opt/airflow/project/dbt",
                "--select",
                "assert_reconciliation_scenario_matrix",
            ],
            check=True,
            env=env,
            cwd="/opt/airflow/project",
        )

    load = load_settlement_file()
    transform = dbt_reconciliation_build()
    assertions = reconciliation_assertions()

    load >> transform >> assertions


settlement_reconciliation()
