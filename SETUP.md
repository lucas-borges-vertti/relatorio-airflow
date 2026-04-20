# Airflow

## Ambientes Docker

Use um compose base unico e selecione o ambiente com um arquivo de variaveis dedicado.

Arquivos sugeridos:

- `.env.hml` para homologacao
- `.env.prod` para producao

Os templates versionados sao:

- `.env.hml.example`
- `.env.prod.example`
- `.env.example` como base generica

Suba o stack sempre com `--env-file` explicito:

```bash
docker compose --env-file .env.hml up -d --build
docker compose --env-file .env.prod up -d --build
```

Valide a resolucao das variaveis antes de subir:

```bash
docker compose --env-file .env.hml config
docker compose --env-file .env.prod config
```

Setar airflow user no docker-compose:

```bash
docker compose --env-file .env.hml exec -it airflow-webserver airflow users create \
  --username airflow \
  --firstname Airflow \
  --lastname Admin \
  --role Admin \
  --email admin@vertti.com \
  --password airflow
```

## Environment Variables

Definir no arquivo de ambiente selecionado:

```
APP_ENV=hml
ORACLE_HOST=10.100.20.xxx
ORACLE_PORT=1521
ORACLE_USER=VRT_HML_USER
ORACLE_PASSWORD=preencher
ORACLE_SERVICE_NAME=VTIHOM1
NESTJS_API_URL=http://host-gateway:4500
REPORTS_PUBLIC_URL=http://localhost:4500
SMTP_USER=no-reply@example.com
SMTP_PASSWORD=preencher
SMTP_FROM=no-reply@example.com
WHATSAPP_API_URL=https://api-whatsapp.example.com
WHATSAPP_API_KEY=preencher
```

## Inicializar DB do Airflow

```bash
docker compose --env-file .env.hml exec airflow-webserver airflow db migrate
```

## Notes

- DAG ID: `report_generation_dag`
- Schedule: None (somente disparado via API)
- Retries: 2 com 5 min delay entre tentativas
