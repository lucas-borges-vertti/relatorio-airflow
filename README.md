# Relatorio Async - Airflow Runtime

## Visão Geral

Este repositório hoje mantém o runtime de processamento assíncrono do relatório, centrado em Airflow.

O stack local versionado aqui contém:

- Airflow webserver com DAGs, plugins e configuração do extrator Oracle
- PostgreSQL interno do Airflow para metadados da plataforma
- Templates de ambiente para homologação e produção

O backend HTTP de negócio não é mais mantido neste repositório. A migração está documentada em [RELATORIO_MIGRATION_PLAN.md](RELATORIO_MIGRATION_PLAN.md).

## O Que Este Repositório Faz

- Executa a DAG `report_generation_dag`
- Consulta Oracle diretamente em Python
- Resolve o schema por cliente usando `airflow/config/client_schema_map.json`
- Gera CSV e PDF
- Envia email
- Faz upload e callback para uma API externa configurada por `NESTJS_API_URL`

## Arquitetura Atual

```text
API externa / frontend
    ↓ trigger da DAG com payload
Airflow
├── extract_data      -> Oracle direto via Python
├── transform_data    -> gera CSV e PDF
├── send_email        -> entrega por email
├── callback_success  -> PATCH status no backend externo
└── callback_failure  -> PATCH erro no backend externo
    ↓
airflow-postgres
    ↓
metadados internos do Airflow
```

## Estrutura Relevante

- `airflow/dags/report_generation.py`: DAG principal
- `airflow/plugins/oracle_connector.py`: conexão Oracle e resolução de parâmetros
- `airflow/plugins/portal_cliente_extractor.py`: queries e agregação
- `airflow/config/client_schema_map.json`: mapa `cliente -> schema Oracle`
- `docker-compose.yml`: stack local do Airflow
- `SETUP.md`: guia operacional do ambiente

## Ambientes

O projeto usa um `docker-compose.yml` único e arquivos de ambiente separados.

Templates versionados:

- `.env.example`
- `.env.hml.example`
- `.env.prod.example`

Arquivos reais esperados no servidor:

- `.env.hml`
- `.env.prod`

Principais variáveis:

- `APP_ENV`
- `ORACLE_HOST`
- `ORACLE_PORT`
- `ORACLE_USER`
- `ORACLE_PASSWORD`
- `ORACLE_SERVICE_NAME`
- `ORACLE_DSN`
- `NESTJS_API_URL`
- `REPORTS_PUBLIC_URL`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `WHATSAPP_API_URL`
- `WHATSAPP_API_KEY`

## Subir Localmente

Exemplo com homologação:

```bash
cp .env.hml.example .env.hml
docker compose --env-file .env.hml config
docker compose --env-file .env.hml up -d --build
```

Exemplo com produção:

```bash
cp .env.prod.example .env.prod
docker compose --env-file .env.prod config
docker compose --env-file .env.prod up -d --build
```

## Inicialização do Airflow

Criar usuário inicial:

```bash
docker compose --env-file .env.hml exec -it airflow-webserver airflow users create \
  --username airflow \
  --firstname Airflow \
  --lastname Admin \
  --role Admin \
  --email admin@vertti.com \
  --password airflow
```

Migrar banco de metadados:

```bash
docker compose --env-file .env.hml exec airflow-webserver airflow db migrate
```

UI local do Airflow:

- URL: `http://localhost:8081`
- Usuário: `airflow`
- Senha: `airflow`

## Como o Cliente e o Schema São Resolvidos

O cliente vem no payload do `dag_run.conf`.

Fluxo resumido:

1. A DAG lê `cliente` de `dag_run.conf` ou de `payload.cliente`
2. `portal_cliente_extractor.py` chama `resolve_schema_by_cliente(cliente)`
3. `oracle_connector.py` carrega `airflow/config/client_schema_map.json`
4. O `dbUser` mapeado vira o schema Oracle usado nas queries
5. Se não houver mapeamento, o fallback é `ORACLE_USER`

Exemplo:

- `cliente = rhall`
- schema resolvido = `VTI_RHL`

## Como o Banco Oracle É Resolvido

A conexão Oracle usa as variáveis de ambiente do container Airflow.

Prioridade:

1. `ORACLE_DSN`, se definido
2. `ORACLE_HOST` + `ORACLE_PORT` + `ORACLE_SERVICE_NAME`

O usuário de conexão vem de `ORACLE_USER`, mas o schema efetivo das queries pode ser sobrescrito pelo mapeamento por cliente.

## Dependência Externa Importante

Mesmo sem um NestJS local neste stack, o Airflow ainda depende de uma API externa compatível para:

- upload de arquivos
- callback de status
- links públicos de download

Essa integração é feita via `NESTJS_API_URL`.

## Logs Úteis

```bash
docker compose --env-file .env.hml logs -f airflow-webserver
docker compose --env-file .env.hml logs -f airflow-postgres
docker compose --env-file .env.hml exec airflow-webserver env | grep ORACLE_
docker compose --env-file .env.hml exec airflow-webserver env | grep NESTJS_API_URL
```

## Arquivos de Referência

- [SETUP.md](SETUP.md): operação do stack e variáveis de ambiente
- [RELATORIO_MIGRATION_PLAN.md](RELATORIO_MIGRATION_PLAN.md): contexto da migração do backend

## Observações

- O `docker-compose.yml` deste repositório sobe apenas Airflow e o Postgres interno do Airflow
- O repositório não deve mais ser tratado como fonte de verdade da API HTTP de negócio
- Se o backend externo mudar de contrato, a DAG pode precisar de ajuste nos endpoints de upload e callback
