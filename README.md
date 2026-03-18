# Relatorio Async - NestJS + Airflow

## Visão Geral

Sistema de geração de relatórios assíncronos que integra:

- **NestJS API**: Gerencia requisições, armazena status em BD PostgreSQL, dispara DAGs Airflow
- **Airflow**: Orquestra workflow completo (extração → transformação → entrega)
- **PostgreSQL**: Persistência de dados das requisições (relatórios)
- **Oracle Database**: Fonte dos dados consultada diretamente pelo Airflow em Python

## Arquitetura

```
Web Frontend (React)
    ↓
POST /api/reports/async
    ↓
NestJS API
├── Validar payload
├── Salvar em BD (status=PENDING)
├── Dispara Airflow DAG via API
└── Retorna requestId
    ↓
Airflow DAG (report_generation_dag)
├── Task 1: extract_data → Consulta Oracle direto via Python (schema dinâmico por cliente)
├── Task 2: transform_data → Gera PDF/XML
├── Task 3: send_email → Entrega ao cliente
└── Callback: Atualiza status em NestJS via PATCH /api/reports/{id}/status
    ↓
Web pode fazer polling em GET /api/reports/{id}/status
```

## Responsabilidades

### NestJS
- ✅ Receber requisições assíncronas (POST /api/reports/async)
- ✅ Validar payloads (action, periodos, etc.)
- ✅ Persistir em BD PostgreSQL (velog_reports_async)
- ✅ Disparar DAG Airflow via API HTTP
- ✅ Retornar requestId imediatamente
- ✅ Fornecer status em tempo real (GET /api/reports/{id}/status)
- ✅ Receber callbacks do Airflow e atualizar BD

### Airflow
- ✅ Orquestrar workflow de geração (extract → transform → deliver)
- ✅ Extrair dados direto do Oracle via Python (sem chamada ao PHP)
- ✅ Resolver schema Oracle por `cliente` (ex.: `potencial_hom` -> `VRT_POT`)
- ✅ Transformar dados em PDF/XML per template
- ✅ Entregar via Email (futuro: WhatsApp)
- ✅ Executar retries automáticos (2 retries com 5min delay)
- ✅ Notificar NestJS quando concluído (callback)
- ✅ Logs persistentes por execução

### PostgreSQL
- ✅ Tabela `velog_reports_async`: Requisições + status + timestamps
- ✅ Rastreabilidade completa (created_at, updated_at, completed_at, delivered_at)
- ✅ Dados de entrada (payload) + resultado (PDF/XML URLs)

## Instalação & Execução

### Pré-requisitos
- Docker & Docker Compose
- Node.js 22+ (para desenvolvimento local)

### Setup

```bash
cd /home/lucas/projetos/relatorio

# 1. Criar arquivo .env
cp nestjs/.env.example nestjs/.env

# 2. Build e start dos containers
docker-compose up -d

# 3. NestJS vai criar tabelas automaticamente (TypeORM synchronize=true)

# 4. Airflow precisa de setup inicial
docker-compose exec -it airflow-webserver airflow db init
docker-compose exec -it airflow-webserver airflow users create \
  --username airflow \
  --password airflow \
  --firstname Airflow \
  --lastname Admin \
  --role Admin \
  --email admin@vertti.com

# 5. Verificar status
docker-compose ps
```

## Endpoints NestJS

### 1. Submeter Relatório Assíncrono
```bash
POST http://localhost:3000/api/reports/async

Body:
{
  "action": "portalCliente::getAnalitic",
  "periodos": [
    {
      "ini": "2024-03-01",
      "fim": "2024-05-31"
    }
  ],
  "cliente_cnpj": "12345678000190",
  "usuario_email": "user@company.com",
  "usuario_id": "123",
  "filtros": {...},
  "version": "4.59",
  "token": "xxx",
  "hmac": "yyy"
}

Response (202 Accepted):
{
  "status": true,
  "requestId": "uuid-xxx",
  "message": "Relatório enfileirado com sucesso",
  "data": {
    "id": "uuid-xxx",
    "status": "PENDING",
    "created_at": "2026-03-16T10:00:00Z"
  }
}
```

### 2. Verificar Status
```bash
GET http://localhost:3000/api/reports/{id}/status

Response:
{
  "status": true,
  "data": {
    "id": "uuid-xxx",
    "status": "PROCESSING" | "COMPLETED" | "FAILED",
    "periodo_ini": "2024-03-01",
    "periodo_fim": "2024-05-31",
    "resultado": {
      "pdf_url": "...",
      "xml_url": "..."
    },
    "delivered_at": null,
    "created_at": "2026-03-16T10:00:00Z",
    "updated_at": "2026-03-16T10:05:00Z"
  }
}
```

### 3. Listar Pendentes
```bash
GET http://localhost:3000/api/reports/pending?limit=10

Response:
{
  "status": true,
  "count": 3,
  "data": [...]
}
```

## Fluxo de Execução

1. **Web Frontend**
   - Usuário seleciona período ≥ 30 dias
   - Modal async aparece
   - Frontend submete POST /api/reports/async

2. **NestJS Recebe**
   - Valida payload
   - Cria registro em BD (status=PENDING)
   - Dispara Airflow DAG via POST /api/v1/dags/{dagId}/dagRuns
   - Retorna requestId (202 Accepted)

3. **Airflow Processa**
  - Task 1: extract_data → Consulta Oracle direto por Python usando schema do cliente
   - Task 2: transform_data → Gera PDF/XML
   - Task 3: send_email → Envia ao cliente
   - Task 4 (callback): Atualiza NestJS com resultado/status

## Mapeamento de cliente para schema

- O campo `cliente` do payload é a chave de resolução de schema no Airflow.
- O mapa versionado está em `airflow/config/client_schema_map.json`.
- Exemplo: `potencial_hom` usa schema `VRT_POT`.

4. **Web Faz Polling**
   - GET /api/reports/{requestId}/status
   - Mostra progresso: PENDING → PROCESSING → COMPLETED
   - Quando COMPLETED, mostra link para PDF/XML

## Configuração Airflow (UI)

1. Acessar http://localhost:8080
2. User: airflow / Pass: airflow
3. DAG "report_generation_dag" deve estar listado
4. Status por padrão é PAUSED (expected)

## Configuração de Email (SMTP)

O envio da task `send_email` usa variáveis do ambiente do Airflow:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`

Exemplo local já parametrizado no `.env` com `smtp.velog.com.br:587`.

## Logs

- **NestJS**: `docker-compose logs -f nestjs-api`
- **Airflow**: `docker-compose logs -f airflow-webserver`
- **Airflow DB**: `docker-compose exec airflow-webserver cat /opt/airflow/logs/report_generation_dag/...`

## Próximos Passos

1. **Python Transformations** → Implementar geração PDF/XML
2. **Email Service** → Integrar com SendGrid/AWS SES
3. **Bull MQ** → Adicionar se volume de requests crescer
4. **Webhooks** → Notificação em tempo real (WebSocket)
5. **Retry Strategy** → Refinar política por tipo de erro
