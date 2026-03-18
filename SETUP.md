# Airflow

Setar airflow user no docker-compose:

```bash
docker-compose exec -it airflow-webserver airflow users create \
  --username airflow \
  --firstname Airflow \
  --lastname Admin \
  --role Admin \
  --email admin@vertti.com \
  --password airflow
```

## Environment Variables

Adicionar em docker-compose.yml ou .env:

```
AIRFLOW_UID=50000
AIRFLOW_GID=0
AIRFLOW__CORE__LOAD_EXAMPLES=false
AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow_user:airflow_pass@airflow_postgres:5432/airflow_db
AIRFLOW__API__AUTH_BACKENDS=airflow.api.auth.backend.basic_auth
```

## Inicializar DB do Airflow

```bash
docker-compose exec airflow-webserver airflow db migrate
```

## Notes

- DAG ID: `report_generation_dag`
- Schedule: None (somente disparado via API)
- Retries: 2 com 5 min delay entre tentativas
