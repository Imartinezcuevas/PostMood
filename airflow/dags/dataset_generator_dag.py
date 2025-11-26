# airflow/dags/dataset_generator_dag.py
from airflow import DAG
from airflow.sensors.python import PythonSensor
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.utils.dates import days_ago
from docker.types import Mount
from datetime import timedelta
import logging
import os

default_args = {
    "owner": "postmood",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id='dataset_generator',
    default_args=default_args,
    schedule_interval=None,
    start_date=days_ago(1),
    catchup=False,
    tags=['dataset'],
) as dag:
    def check_new_corrections():
        # imports aqui
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(
            host="postgres",
            port=5432,
            dbname="postmood",
            user="postmood",
            password="postmood"
        )
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT last_post_id FROM dataset_generation_log ORDER BY id DESC LIMIT 1")
                last = cur.fetchone()
                last_id = last['last_post_id'] if last else 0

                cur.execute("SELECT COUNT(*) as cnt FROM sentiment_corrections WHERE id > %s", (last_id,))
                count = cur.fetchone()['cnt']
                logging.info(f"New corrections since last_id={last_id}: {count}")
                return count >= 50
        finally:
            conn.close()

    wait_for_50 = PythonSensor(
        task_id='wait_for_50_corrections',
        python_callable=check_new_corrections,
        poke_interval=60,
        timeout=24*3600,
        mode='poke'
    )

    generate_dataset = DockerOperator(
        task_id='generate_dataset',
        image='dataset-generator:latest',
        api_version='auto',
        auto_remove=True,
        command='python main.py',
        docker_url='unix://var/run/docker.sock',
        network_mode='postmood_postmood-net',
        mount_tmp_dir=False,
        mounts=[
            Mount(source='dataset_output', target='/app/output', type='volume')
        ]
    )

    wait_for_50 >> generate_dataset
