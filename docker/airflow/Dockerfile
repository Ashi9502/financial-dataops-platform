FROM apache/airflow:3.3.2

# Packages required directly by Airflow Python tasks.
RUN pip install --no-cache-dir \
    "apache-airflow==3.3.2" \
    "psycopg[binary]==3.3.6" \
    "boto3==1.43.110" \
    "pandas==3.0.6" \
    "PyYAML==6.0.3" \
    "pyarrow==26.0.0"

# Keep dbt / GX isolated from Airflow's dependency environment.
RUN python -m venv /opt/airflow/dataops-venv \
    && /opt/airflow/dataops-venv/bin/pip install \
        --no-cache-dir \
        --upgrade pip \
    && /opt/airflow/dataops-venv/bin/pip install \
        --no-cache-dir \
        "dbt-postgres==1.11.0" \
        "great-expectations[postgresql]==1.24.0"


USER airflow
RUN pip install --no-cache-dir     "apache-airflow==3.3.2"     "apache-airflow-providers-openlineage==2.20.2"
