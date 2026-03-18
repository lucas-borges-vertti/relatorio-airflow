# Estrutura Criada - NestJS + Airflow

## ✅ O que foi implementado

### 1. **NestJS API** (`/nestjs`)
Endpoints prontos:
- `POST /api/reports/async` → Recebe payload do React, salva em BD, dispara Airflow
- `GET /api/reports/:id/status` → Verifica status da requisição
- `GET /api/reports/pending` → Lista reports pendentes (para Airflow depois)
- `PATCH /api/reports/:id/status` → Callback do Airflow atualiza status

**Banco de Dados**: PostgreSQL com tabela `velog_reports_async`
- Campos: id, request_id, status, payload, cliente_cnpj, usuario_email, periodo_ini/fim, airflow_dag_run_id, resultado, timestamps

**Validação**: DTOs com class-validator para garantir payload correto

### 2. **Airflow DAG** (`/airflow/dags/report_generation.py`)
Workflow com 4 tarefas:
1. **extract_data** → Consulta Oracle direto via Python (schema por cliente)
2. **transform_data** → Transforma resultado em PDF/XML (template)
3. **send_email** → Envia ao cliente (placeholder para futuro)
4. **callback** → Notifica NestJS com resultado/erro

**Retries**: 2 tentativas com 5min de delay
**Schedule**: Desativado (somente disparado via API HTTP)

### 3. **Docker Compose**
3 containers:
- **postgres** (BD NestJS) - Port 5432
- **nestjs-api** - Port 3000
- **airflow-webserver** (+ BD Airflow separado) - Port 8080

Redes: Conectados via `relatorio_network`
Volumes: Persistência de dados + logs + DAGs

## 🚀 Como usar

### Pré-requisitos
```bash
docker --version     # Docker 20+
docker-compose --version  # Docker Compose 2+
```

### 1. Setup Inicial
```bash
cd /home/lucas/projetos/relatorio

# Copiar env template
cp nestjs/.env.example nestjs/.env

# Build e start
docker-compose up -d

# Visualizar logs
docker-compose logs -f
```

### 2. Inicializar Airflow (primeira vez)
```bash
# Criar usuário Airflow
docker-compose exec -it airflow-webserver airflow users create \
  --username airflow \
  --password airflow \
  --firstname Airflow \
  --lastname Admin \
  --role Admin \
  --email admin@vertti.com

# Acessar UI
# http://localhost:8080
# user: airflow / pass: airflow
```

### 3. Chamar API (teste)
```bash
# Submeter relatório assíncrono
curl -X POST http://localhost:3000/api/reports/async \
  -H "Content-Type: application/json" \
  -d '{
    "action": "portalCliente::getAnalitic",
    "periodos": [{"ini": "2024-03-01", "fim": "2024-05-31"}],
    "cliente_cnpj": "12345678000190",
    "usuario_email": "user@company.com",
    "usuario_id": "123"
  }'

# Resposta (202 Accepted):
# {
#   "status": true,
#   "requestId": "uuid-xxx",
#   "message": "Relatório enfileirado com sucesso",
#   "data": {...}
# }

# Verificar status
curl http://localhost:3000/api/reports/{requestId}/status
```

### 4. Monitorar Airflow
```bash
# UI: http://localhost:8080
# DAG: report_generation_dag
# Status esperado: Paused (normal)

# Trigger manualmente
curl -X POST http://localhost:8080/api/v1/dags/report_generation_dag/dagRuns \
  -u airflow:airflow \
  -H "Content-Type: application/json" \
  -d '{
    "conf": {
      "report_id": "uuid-xxx",
      "request_id": "uuid-xxx",
      "cliente": "potencial_hom",
      "cliente_cnpj": "12345678000190"
    }
  }'

### 5. Mapeamento cliente -> schema
O Airflow usa o campo `cliente` para resolver o schema Oracle no arquivo `airflow/config/client_schema_map.json`.
Exemplo: `potencial_hom` resolve para `VRT_POT`.
```

## 📁 Estrutura de Diretórios

```
/home/lucas/projetos/relatorio/
├── nestjs/
│   ├── src/
│   │   ├── main.ts
│   │   ├── app.module.ts
│   │   ├── modules/
│   │   │   └── reports/
│   │   │       ├── reports.controller.ts
│   │   │       ├── reports.service.ts
│   │   │       ├── entities/report.entity.ts
│   │   │       └── dtos/create-async-report.dto.ts
│   │   └── config/
│   │       └── airflow.config.ts
│   ├── package.json
│   ├── tsconfig.json
│   ├── Dockerfile
│   └── .env.example
├── airflow/
│   ├── dags/
│   │   └── report_generation.py
│   ├── plugins/
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
├── Makefile
├── README.md
└── .gitignore
```

## 🔧 Comandos Úteis

```bash
# Build tudo
make build

# Start/stop
make up
make down

# Logs
make logs          # Todos
make dev-logs      # NestJS
make airflow-logs  # Airflow

# Reiniciar
make restart

# Shell no container
make shell         # NestJS
make airflow-shell # Airflow

# Inicializar Airflow
make init-airflow

# Limpar volumes (destructivo)
make clean

# Health check
make health
```

## 🔌 Integração com React Frontend

Já implementado em `web/src/p/portalCliente/`:

1. `asyncReport.service.js` → POST para novo endpoint NestJS
2. `PortalCliente/index.js` → Modal para períodos ≥30 dias
3. Payload já padronizado (action + periodos + filtros)

**Mudança necessária**: Atualizar `REACT_APP_AIRFLOW_URL` para apontar para NestJS:

```bash
# web/.env ou .env.local
REACT_APP_AIRFLOW_URL=http://localhost:3000
```

## 🚨 Troubleshooting

### Airflow não sobe
```bash
# Verificar logs
docker-compose logs airflow-webserver

# Reiniciar BD Airflow
docker-compose down airflow_postgres
docker-compose up -d airflow_postgres
```

### NestJS não consegue conectar BD
```bash
# Verificar status do Postgres
docker-compose exec postgres psql -U relatorio_user -d relatorio_db -c "\dt"

# Reiniciar Postgres
docker-compose restart postgres
```

### Erro ao disparar Airflow DAG do NestJS
```bash
# Verificar credenciais Airflow
curl -u airflow:airflow http://localhost:8080/api/v1/dags

# Verificar DAG está loaded
# http://localhost:8080/home (UI)
```

## 📊 Próximos Passos

### Fase 2: Transformações Python
- [ ] Implementar geração PDF (WeasyPrint ou ReportLab)
- [ ] Implementar geração XML (StyleReport)
- [ ] Suportar múltiplos templates

### Fase 3: Entregas
- [ ] Email service (SendGrid/AWS SES)
- [ ] Webhooks (notificar cliente)
- [ ] WhatsApp (via Twilio)

### Fase 4: Otimizações
- [ ] Bull MQ para maior throughput
- [ ] Cache Redis
- [ ] Retry strategy por tipo de erro
- [ ] Metrics (Prometheus)

## 📝 Notas Importantes

1. **Responsabilidades separadas**:
   - NestJS = gateway + persistência + orquestração básica
   - Airflow = workflow complexo + transformações + entregas

2. **API Airflow credentials**:
   - User: `airflow`
   - Pass: `airflow`
   - Base URL: `http://airflow-webserver:8080`

3. **PostgreSQL**:
   - NestJS: `relatorio_db` (BD de aplicação)
   - Airflow: `airflow_db` (BD interna Airflow)
   - Separadas para isolamento

4. **Callback do Airflow**:
   - PATCH `/api/reports/{id}/status`
   - Atualiza BD com resultado/erro
   - Frontend faz polling em GET `/api/reports/{id}/status`

---

**Status**: ✅ Pronto para deploy local
**Próximas ações**: Testar fluxo completo → Adicionar transformações Python → Integrar email
