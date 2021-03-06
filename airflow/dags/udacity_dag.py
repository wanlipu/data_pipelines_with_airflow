from datetime import datetime, timedelta
import os
from airflow import DAG
from airflow.operators.dummy_operator import DummyOperator
from airflow.operators.subdag_operator import SubDagOperator
from airflow.operators import (StageToRedshiftOperator, LoadFactOperator, 
                               LoadDimensionOperator, DataQualityOperator, 
                               PostgresOperator)
from helpers import SqlQueries

start_date = datetime(2020, 3, 3)
default_args = {
    "owner": "udacity",
    "start_date": start_date,
    "depends_on_past": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "catchup": False,
    "email_on_retry": False
}

dag_id = "udacity_data_pipeline_project"
dag = DAG(dag_id,
          default_args=default_args,
          description="Load and transform data in Redshift with Airflow",
          schedule_interval="0 * * * *",
          max_active_runs=5
        )

start_operator = DummyOperator(
    task_id="Begin_execution",  
    dag=dag
)

create_redshift_tables = PostgresOperator(
    task_id="Create_tables",
    dag=dag,
    sql="create_tables.sql",
    postgres_conn_id="redshift"
)

stage_events_to_redshift = StageToRedshiftOperator(
    task_id="Stage_events",
    redshift_conn_id="redshift",
    aws_credentials_id="aws_credentials",
    table="staging_events",
    s3_bucket='udacity-dend',
    s3_key="log_data/",
    extra_params="format as json 's3://udacity-dend/log_json_path.json'",
    dag=dag
)

stage_songs_to_redshift = StageToRedshiftOperator(
    task_id="Stage_songs",
    redshift_conn_id="redshift",
    aws_credentials_id="aws_credentials",
    table="staging_songs",
    s3_bucket='udacity-dend',
    s3_key="song_data",
    extra_params="json 'auto' compupdate off region 'us-west-2'",
    dag=dag
)

load_songplays_table = LoadFactOperator(
    task_id="Load_songplays_fact_table",
    redshift_conn_id="redshift",
    table="songplays",
    sql_source=SqlQueries.songplay_table_insert,
    dag=dag
)

load_user_dimension_table = LoadDimensionOperator(
    task_id="Load_user_dim_table",
    redshift_conn_id="redshift",
    table="users",
    sql_source=SqlQueries.user_table_insert,
    dag=dag
)

load_song_dimension_table = LoadDimensionOperator(
    task_id="Load_song_dim_table",
    redshift_conn_id="redshift",
    table="songs",
    sql_source=SqlQueries.song_table_insert,
    dag=dag
)

load_artist_dimension_table = LoadDimensionOperator(
    task_id="Load_artist_dim_table",
    redshift_conn_id="redshift",
    table="artists",
    sql_source=SqlQueries.artist_table_insert,
    dag=dag
)

load_time_dimension_table = LoadDimensionOperator(
    task_id="Load_time_dim_table",
    redshift_conn_id="redshift",
    table="time",
    sql_source=SqlQueries.time_table_insert,
    dag=dag
)

run_quality_checks = DataQualityOperator(
    task_id="Run_data_quality_checks",
    redshift_conn_id="redshift",
    tables=["time", "artists"],
    sql_template = "SELECT COUNT(*) FROM {};",
    dag=dag
)

end_operator = DummyOperator(task_id="stop_execution",  dag=dag)


start_operator >> create_redshift_tables

create_redshift_tables >> stage_songs_to_redshift  >> load_songplays_table
create_redshift_tables >> stage_events_to_redshift >> load_songplays_table

load_songplays_table >> load_user_dimension_table   >> run_quality_checks
load_songplays_table >> load_song_dimension_table   >> run_quality_checks
load_songplays_table >> load_artist_dimension_table >> run_quality_checks
load_songplays_table >> load_time_dimension_table   >> run_quality_checks

run_quality_checks >> end_operator