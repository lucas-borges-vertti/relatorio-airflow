# 📚 Documentação - Relatorio Async (NestJS + Airflow)

## Índice Rápido

### 1. **[GETTING_STARTED.md](GETTING_STARTED.md)** — Comece aqui! ⭐
   - Setup inicial
   - Primeiros passos
   - Comandos de desenvolvimento
   - Troubleshooting

### 2. **[API_REFERENCE.md](API_REFERENCE.md)** — Integração com APIs
   - Endpoints completos (5 routes)
   - Exemplos cURL + JavaScript
   - Status transitions
   - Error handling
   - Database schema

### 3. **[README.md](README.md)** — Visão Geral da Arquitetura
   - Conceito geral
   - Fluxo de execução
   - Responsabilidades separadas
   - Configuração

### 4. **[IMPLEMENTATION.md](IMPLEMENTATION.md)** — Resumo Técnico
   - Arquivos criados
   - Estrutura de diretórios
   - Checklist de implementação
   - Roadmap futuro

### 5. **[FRONTEND_INTEGRATION.md](FRONTEND_INTEGRATION.md)** — React Integration
   - Como integrar com web/portalCliente
   - Mudanças necessárias
   - Exemplos de código atualizado

### 6. **[Makefile](Makefile)** — Comandos Úteis
   ```bash
   make build        # Build images
   make up           # Start containers
   make logs         # View all logs
   make init-airflow # Setup Airflow
   ```

### 7. **[SETUP.md](SETUP.md)** — Notes técnicas
   - Variáveis de ambiente
   - Setup Airflow específico

---

## 🚀 Quick Start (3 minutos)

```bash
cd /home/lucas/projetos/relatorio

# 1. Build e start
docker-compose up -d

# 2. Init Airflow (uma vez)
docker-compose exec -it airflow-webserver airflow users create \
  --username airflow --password airflow --role Admin --email admin@vertti.com

# 3. Testn
curl -X POST http://localhost:3000/api/reports/async \
  -H "Content-Type: application/json" \
  -d '{
    "action": "portalCliente::getAnalitic",
    "periodos": [{"ini": "2024-03-01", "fim": "2024-05-31"}],
    "cliente_cnpj": "12345678000190",
    "usuario_email": "user@company.com"
  }'

# 4. Acessar UIs
# NestJS: http://localhost:3000/api/docs
# Airflow: http://localhost:8080 (airflow/airflow)
```

---

## 📖 Navegação por Tópico

### Iniciando
→ [GETTING_STARTED.md](GETTING_STARTED.md)

### Desenvolvimento Local
→ [Makefile](Makefile) + [README.md](README.md)

### Integrando com React
→ [FRONTEND_INTEGRATION.md](FRONTEND_INTEGRATION.md)

### Chamando APIs
→ [API_REFERENCE.md](API_REFERENCE.md)

### Entendendo a arquitetura
→ [README.md](README.md) + [IMPLEMENTATION.md](IMPLEMENTATION.md)

### Troubleshooting
→ [GETTING_STARTED.md](GETTING_STARTED.md#-troubleshooting)

---

## 🏗️ Estrutura do Projeto

```
/home/lucas/projetos/relatorio/
│
├── 📂 nestjs/                 # NestJS Application
│   ├── src/
│   │   ├── app.module.ts
│   │   ├── modules/reports/   # Report Management
│   │   └── config/
│   ├── package.json
│   ├── Dockerfile
│   └── .env.example
│
├── 📂 airflow/                # Airflow Workflows
│   ├── dags/
│   │   └── report_generation.py  # Main DAG
│   ├── Dockerfile
│   └── requirements.txt
│
├── 📄 docker-compose.yml      # Container Orchestration
├── 📄 Makefile                # Development Commands
├── 📄 README.md               # Architecture Overview
├── 📄 GETTING_STARTED.md      # Setup Instructions
├── 📄 API_REFERENCE.md        # Endpoint Documentation
├── 📄 FRONTEND_INTEGRATION.md # React Integration Guide
├── 📄 IMPLEMENTATION.md       # Technical Summary
└── 📄 SETUP.md                # Configuration Notes
```

---

## 🎯 Fluxo Principal

```
1. React Frontend
   └─ detecta período ≥30 dias
   └─ POST /api/reports/async

2. NestJS API
   └─ validação
   └─ salva em BD
   └─ dispara Airflow DAG
   └─ retorna requestId (202)

3. Airflow DAG (4 tarefas)
   └─ extract: chama PHP backend
   └─ transform: gera PDF/XML
   └─ email: entrega ao cliente
   └─ callback: notifica NestJS

4. React Polling
   └─ GET /api/reports/{id}/status
   └─ exibe progresso
   └─ baixa PDF quando COMPLETED
```

---

## 🛠️ Ferramentas & Tecnologias

| Ferramenta | Versão | Uso |
|-----------|--------|-----|
| **NestJS** | 10.0 | API Gateway + BD |
| **Airflow** | 2.8.1 | Orquestração Workflow |
| **PostgreSQL** | 16 | Persistência |
| **Docker** | 20+ | Containerização |
| **Node.js** | 22 | Runtime |
| **TypeScript** | 5.0 | Type Safety |
| **TypeORM** | 0.3 | ORM |
| **Axios** | 1.6 | HTTP Client |
| **Swagger** | 7.0 | API Docs |

---

## 📊 Endpoints Sumário

| Método | Path | Status | Descrição |
|--------|------|--------|-----------|
| POST | /api/reports/async | 202 | Submeter relatório |
| GET | /api/reports/:id/status | 200 | Verificar status |
| GET | /api/reports/pending | 200 | Listar pendentes |
| PATCH | /api/reports/:id/status | 200 | Update status (callback) |
| PATCH | /api/reports/:id/delivered | 200 | Marcar entregue |

**[Ver detalhes completos →](API_REFERENCE.md)**

---

## 🚦 Status de Implementação

✅ **Completo**:
- NestJS API com CRUD
- Integração Airflow (HTTP trigger + callbacks)
- PostgreSQL persistence
- Docker Compose setup
- API documentation (Swagger)
- Makefile utilities
- Frontend integration guide

🔄 **Próximos**:
- Transformações Python (PDF/XML)
- Email service
- Bull MQ (opcional, para escala)

❌ **Não Implementado**:
- Autenticação JWT
- Rate limiting
- Redis cache
- WebSocket real-time

---

## 📞 Contato & Suporte

- **Documentação Principal**: Este arquivo
- **Issues**: Consultar problema específico em GETTING_STARTED.md
- **Alterações**: Atualizar docs ao modificar APIs

---

## 📝 Histórico

| Data | Versão | Descrição |
|------|--------|-----------|
| 2026-03-16 | 1.0.0 | Initial release (NestJS + Airflow) |

---

**Última atualização**: 16 de março de 2026
**Status**: ✅ Pronto para Deploy
**Próxima ação**: Ler [GETTING_STARTED.md](GETTING_STARTED.md)
