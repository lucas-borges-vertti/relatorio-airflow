# 📊 Como o Projeto Relatorio Async Funciona

## 🎯 O que é este projeto?

O **Relatorio Async** é um sistema de **geração assíncrona de relatórios** que permite que usuários solicitem relatórios complexos **sem bloquear a interface**. Em vez de esperar minutos para um relatório ser gerado, o usuário:

1. Clica em "Solicitar Relatório"
2. Recebe um ID imediatamente (202 Accepted)
3. Acompanha o progresso via polling
4. Recebe o relatório por email quando pronto

---

## 🤔 Qual problema resolve?

Antes, quando um usuário solicitava um relatório com **período ≥ 30 dias**:
- ❌ A página ficava pendurada esperando a geração
- ❌ Riscos de timeout ou perda de conexão
- ❌ Péssima experiência de usuário (UX)
- ❌ Servidor bloqueado processando uma única requisição

Agora, com o padrão assíncrono:
- ✅ Resposta imediata (milissegundos)
- ✅ Processamento em background (minutos)
- ✅ Menu responsivo durante o processamento
- ✅ Servidor escalável (múltiplas requisições em paralelo)

---

## 🏗️ Arquitetura Geral (5 Tiers)

```
┌────────────────────────────────────────────────────────────────┐
│                    TIER 1: INTERFACE (React)                   │
│                         Frontend                                │
│  • Detecta período ≥30 dias                                    │
│  • Abre modal "Relatório Assíncrono"                           │
│  • Faz polling do status (a cada 5 segundos)                  │
└────────────────────────────────────────────────────────────────┘
                             ↓ POST /api/reports/async
                        (JSON com requisição)
                             ↓
┌────────────────────────────────────────────────────────────────┐
│                 TIER 2: API REST (NestJS)                      │
│                    Porta: 3000                                  │
│  • Valida payload (DTO com class-validator)                    │
│  • Persiste em PostgreSQL (velog_reports_async)               │
│  • Dispara DAG Airflow via API HTTP                            │
│  • Retorna requestId (202 Accepted)                            │
│  • Fornece status em tempo real (GET /api/reports/{id}/status) │
└────────────────────────────────────────────────────────────────┘
                             ↓
                    (Dispara DAG HTTP)
                             ↓
┌────────────────────────────────────────────────────────────────┐
│               TIER 3: ORQUESTRAÇÃO (Airflow)                   │
│                    Porta: 8080                                  │
│                                                                 │
│  DAG: report_generation_dag (4 tasks em sequência)             │
│  ├─ Task 1: extract_data                                       │
│  │  └─ Conecta no Oracle Database                              │
│  │  └─ Executa queries (dados, mensal, aderência)             │
│  │  └─ Agrega resultados em JSON                               │
│  │                                                              │
│  ├─ Task 2: transform_data                                     │
│  │  └─ Gera PDF conforme template do cliente                  │
│  │  └─ Gera CSV com dados tabulares                           │
│  │                                                              │
│  ├─ Task 3: send_email                                         │
│  │  └─ Entrega PDF/CSV ao email do usuário                    │
│  │                                                              │
│  └─ Task 4: callback                                           │
│     └─ Notifica NestJS com status final (COMPLETED/FAILED)     │
└────────────────────────────────────────────────────────────────┘
                             ↓
        (Coleta dados + Salva em OCI Storage)
                             ↓
┌────────────────────────────────────────────────────────────────┐
│                   TIER 4: DADOS                                │
│  ┌───────────────────┐       ┌──────────────────────────┐     │
│  │   PostgreSQL      │       │   Oracle Database        │     │
│  │   (Metadados)     │       │   (Dados dos Relatórios) │     │
│  │                   │       │                          │     │
│  │ • velog_reports_  │       │ • Múltiplos schemas      │     │
│  │   async           │       │ • Um por cliente         │     │
│  │ • Estado de cada  │       │ • Queries dinâmicas      │     │
│  │   relatório       │       │   por cliente            │     │
│  └───────────────────┘       └──────────────────────────┘     │
└────────────────────────────────────────────────────────────────┘
                             ↓
┌────────────────────────────────────────────────────────────────┐
│                 TIER 5: STORAGE (OCI)                          │
│  • Armazena PDFs gerados (object_key_pdf)                      │
│  • Armazena CSVs gerados (object_key_csv)                      │
│  • Fornece URLs de download por 1 hora                         │
└────────────────────────────────────────────────────────────────┘
```

---

## 📋 Fluxo Completo (Passo-a-Passo)

### 🕐 **FASE 1: Requisição no Frontend (T = 0-2 seg)**

```
1. Usuário detecta período ≥ 30 dias no filtro
   └─ Ex: de 2024-03-01 até 2024-05-31 (97 dias ✓)

2. Frontend abre modal: "Relatório Assíncrono"
   └─ Avisa que pode levar alguns minutos

3. Usuário clica "Solicitar"
   └─ Frontend valida payload completo

4. POST /api/reports/async
   └─ Body (exemplo):
   {
     "action": "portalCliente::getAnalitic",
     "periodos": [
       {
         "ini": "2024-03-01",
         "fim": "2024-05-31"
       }
     ],
     "cliente": "potencial_hom",
     "cliente_cnpj": "12345678000190",
     "usuario_email": "usuario@company.com",
     "usuario_id": "123",
     "filtros": {
       "produtos": ["PROD001"],
       "operacoes": ["FOB"]
     },
     "token": "eyJhbGc...",
     "hmac": "U2FsdG...",
     "version": "4.59"
   }
```

### 🔧 **FASE 2: Processamento na API (T = 2-4 seg)**

```
1. NestJS recebe POST /api/reports/async
   └─ ReportsController.submitAsyncReport()

2. Validação (CreateAsyncReportDto)
   ✅ action é string obrigatória
   ✅ periodos é array obrigatório com ini/fim (datas)
   ✅ usuario_email é string válida
   ✅ Se falharValidation → 400 Bad Request

3. Criar registro em BD (PostgreSQL)
   └─ INSERT velog_reports_async
   {
     id: uuid-generated,
     request_id: uuid-generated,
     status: "PENDING",
     payload: {...payload completo},
     cliente_cnpj: "12345678000190",
     usuario_email: "usuario@company.com",
     periodo_ini: "2024-03-01",
     periodo_fim: "2024-05-31",
     created_at: now(),
     updated_at: now(),
     airflow_dag_run_id: NULL (será preenchido depois)
   }

4. Disparar DAG Airflow via HTTP
   └─ POST http://{AIRFLOW_HOST}:8080/api/v1/dags/report_generation_dag/dagRuns
   {
     "conf": {
       "report_id": "uuid-from-step-3",
       "payload": {...},
       "cliente": "potencial_hom"
     }
   }

5. Retornar 202 Accepted
   └─ Response (imediato):
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

**Tempo total da fase 2**: ~2 segundos ⚡

### 🚀 **FASE 3: Orquestração no Airflow (T = 4 seg até T = 10 min)**

```
1. Airflow recebe trigger e inicia DAG executionTask 1: extract_data (~5-10 min, depende do Oracle)
   ├─ Lê payload do dag_run.conf
   ├─ Conecta ao Oracle Database
   │  └─ Resolve schema por cliente (potencial_hom → VRT_POT)
   ├─ Executa 3 queries:
   │  ├─ Query dados: SELECT * FROM dados WHERE ...
   │  ├─ Query mensal: SELECT [...] FROM mensal WHERE ...
   │  └─ Query aderência: SELECT [...] FROM aderencia WHERE ...
   ├─ Agrega e processa resultados em Python
   └─ Salva em XCom (intercomunicação entre tasks)

   Task 2: transform_data (~30-60 seg)
   ├─ Recupera dados do XCom
   ├─ Carrega template PDF/CSV por cliente (client_templates.py)
   ├─ Formata linhas conforme headers do template
   ├─ Gera PDF usando ReportLab
   ├─ Gera CSV com charset UTF-8-SIG (para Excel)
   └─ Prepara bytes para armazenamento

   Task 3: send_email (~10 seg)
   ├─ Monta email com PDF/CSV em anexo
   ├─ Envia via SMTP para usuario_email
   └─ Registra log de entrega

   Task 4: callback (~5 seg)
   ├─ Chamada HTTP PATCH /api/reports/{id}/status
   │  Body:
   │  {
   │    "status": "COMPLETED",
   │    "object_key_pdf": "reports/uuid-xxx/relatório.pdf",
   │    "object_key_csv": "reports/uuid-xxx/dados.csv",
   │    "completed_at": "2026-03-16T10:15:00Z"
   │  }
   └─ NestJS atualiza registro em PostgreSQL

**Tempo total da fase 3**: 10-15 minutos (depende de Oracle)
```

### 📱 **FASE 4: Acompanhamento no Frontend (T = 4 seg em diante)**

```
1. Usuário recebe requestId imediatamente
   └─ Modal mostra: "Seu relatório está sendo processado..."

2. Frontend faz polling a cada 5 segundos
   └─ GET /api/reports/{requestId}/status

3. Respostas possíveis:

   Status: PENDING (0-5 segundos)
   ├─ Modal mostra: "Enfileirado..."
   ├─ Usuário pode fechar e fazer outra coisa

   Status: PROCESSING (5 seg até 15 min)
   ├─ Modal mostra: "Extraindo dados do Oracle..."
   ├─ (ou "Formatando PDF..." ou "Enviando email...")

   Status: COMPLETED (após 15 min)
   ├─ Modal mostra: "✅ Relatório gerado!"
   ├─ Botão "Baixar" ou "Ver em nova aba"
   ├─ Email com PDF/CSV já foi enviado

   Status: FAILED (se houver erro)
   ├─ Modal mostra: "❌ Erro ao processar"
   ├─ Mostra error_message (ex: "Timeout conexão Oracle")
   ├─ Usuário pode tentar novamente

4. Quando COMPLETED, frontend oferece:
   └─ Botão de download direto de OCI Storage
   └─ URLde download válida por 1 hora
```

---

## 👥 Como Usar Este Sistema

### 📌 Para Usuários Finais

**Como solicitar um relatório:**

1. No Portal Cliente, acesse "Relatórios"
2. Preencha os filtros (produtos, operações, etc.)
3. Se o período for **≥ 30 dias**:
   - ℹ️ Você verá um aviso: "Relatório Assíncrono"
   - 📌 Clique em "Solicitar Relatório"
   - ✅ Receberá um ID imediatamente
4. Acompanhe o status:
   - 🔄 Widget no canto inferior mostra: "Processando..."
   - 📧 Você receberá um email quando o relatório estiver pronto
   - 💾 Baixe diretamente do email ou do Portal

**Se o processamento falhar:**
- ❌ Você receberá um email com a mensagem de erro
- 🔄 Verifique os logs ou contate o suporte

---

### 🛠️ Para Desenvolvedores

**Como instalar e rodar localmente:**

#### Pré-requisitos
```bash
# Você precisa ter:
- Docker & Docker Compose (versão 20+)
- Node.js 18+ (para desenvolvimento NestJS)
- Acesso ao Oracle Database ({ORACLE_HOST})
- Arquivo de credenciais OCI (.oci/oci_api_key.pem)
```

#### 1️⃣ Clonar e Configurar
```bash
git clone https://github.com/vertti/relatorio.git
cd relatorio

# Copiar arquivo de exemplo
cp .env.example .env

# Editar variáveis de ambiente (.env)
# Necessário:
# - ORACLE_HOST, ORACLE_USER, ORACLE_PASSWORD
# - OCI_NAMESPACE, OCI_BUCKET_NAME, OCI_USER, OCI_FINGERPRINT
```

#### 2️⃣ Iniciar Containers
```bash
# Build das imagens (primeira vez)
make build

# Subir todos os services
make up

# Verificar status
make ps
```

**O que sobe:**
- PostgreSQL (porta 5432) com `velog_reports_async` criada automaticamente
- NestJS API (porta 3000)
- Airflow Webserver (porta 8080)
- Airflow Scheduler

#### 3️⃣ Testar Criação de Relatório
```bash
# Terminal 1: Ver logs em tempo real
make logs-api

# Terminal 2: Fazer requisição
curl -X POST http://localhost:3000/api/reports/async \
  -H "Content-Type: application/json" \
  -d '{
    "action": "portalCliente::getAnalitic",
    "periodos": [{"ini": "2024-03-01", "fim": "2024-05-31"}],
    "cliente": "potencial_hom",
    "cliente_cnpj": "12345678000190",
    "usuario_email": "dev@test.com"
  }'

# Resposta:
{
  "status": true,
  "requestId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Relatório enfileirado com sucesso"
}

# Terminal 3: Conferir status (polling)
curl http://localhost:3000/api/reports/a1b2c3d4-e5f6-7890-abcd-ef1234567890/status

# Saída inicial:
{
  "status": true,
  "data": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "PENDING",
    "created_at": "2026-03-16T10:00:00Z"
  }
}

# 30 segundos depois:
{
  "status": true,
  "data": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "PROCESSING",
    "airflow_dag_run_id": "scheduled__2026-03-16T10:00:00+00:00_1"
  }
}

# 10 minutos depois:
{
  "status": true,
  "data": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "COMPLETED",
    "object_key_pdf": "reports/a1b2c3d4/relatório.pdf",
    "object_key_csv": "reports/a1b2c3d4/dados.csv",
    "completed_at": "2026-03-16T10:15:00Z"
  }
}
```

#### 4️⃣ Acompanhar no Airflow UI
```bash
# Abra no navegador:
http://localhost:8080/

# Login:
# User: airflow
# Pass: airflow

# Veja a DAG "report_generation_dag" rodando em tempo real
```

#### 5️⃣ Comandos Úteis
```bash
# Ver status dos containers
make ps

# Parar tudo
make down

# Limpar dados (banco resetado)
make clean

# Ver logs
make logs-api     # NestJS
make logs-airflow # Airflow

# Acessar shell do container
docker-compose exec nestjs-api sh
docker-compose exec postgres psql -U relatorio_user -d relatorio_db
```

---

## 📚 Glossário (Termos Técnicos)

| Termo | O que é | Exemplo |
|-------|--------|---------|
| **DAG** | Directed Acyclic Graph - sequência de tarefas no Airflow | report_generation_dag |
| **Task** | Unidade de trabalho em um DAG | extract_data, transform_data |
| **XCom** | Intercomunicação entre tasks no Airflow | Task 1 salva dados, Task 2 lê |
| **DTO** | Data Transfer Object - estrutura de validação | CreateAsyncReportDto |
| **Payload** | Corpo de uma requisição HTTP | {...campos do formulário...} |
| **HMAC** | Hash-based Message Authentication Code | Validação token frontend |
| **PostgreSQL** | Banco de dados relacional (metadados) | velog_reports_async |
| **Oracle** | Banco de dados relacional (dados) | Schema VRT_POT (cliente) |
| **OCI Storage** | Oracle Cloud Infrastructure (armazenamento) | Onde PDFs são guardados |
| **Schema** | Conjunto de tabelas em DB | VRT_POT = potencial_hom |
| **Client Type** | Tipo de cliente com mapeamento próprio | potencial_hom → VRT_POT |
| **Callback** | Requisição que volta depois | Airflow avisa NestJS quando pronto |
| **Status** | Estado do relatório | PENDING → PROCESSING → COMPLETED |
| **Polling** | Frontend consultando status repetido | A cada 5 segundos |
| **ReportLab** | Biblioteca Python para gerar PDFs | Gera PDF conforme template |
| **Class-Validator** | Validação de DTOs no NestJS | Verifica tipos e valores |

---

## ❓ Perguntas Frequentes (FAQ)

### **P: Quanto tempo leva para um relatório ficar pronto?**
**R:** Depende do volume de dados no Oracle:
- Pequeno (< 100K registros): 2-3 minutos
- Médio (100K-1M): 5-10 minutos
- Grande (> 1M): 10-30 minutos

O email é enviado automaticamente quando pronto.

---

### **P: Posso solicitar múltiplos relatórios ao mesmo tempo?**
**R:** Sim! Cada requisição tem seu próprio ID. O backend processa em paralelo (fila Airflow).

---

### **P: E se a conexão com Oracle falhar?**
**R:** 
- Airflow tenta automaticamente 2 vezes
- Aguarda 5 minutos entre tentativas
- Se falhar: status = FAILED + email com mensagem de erro

---

### **P: Posso baixar o relatório depois?**
**R:** Sim! URLs de download via OCI Storage funcionam por 1 hora. Você também pode:
- Solicitar novo relatório
- Pedir ao suporte para reenviar por email

---

### **P: Por que precisamos de período ≥ 30 dias?**
**R:** Relatórios com pouco período são rápidos (< 30 seg) e podem ser síncronos. Acima disso, o padrão assíncrono oferece melhor UX.

---

### **P: Quem pode acessar os relatórios?**
**R:** Apenas o usuário que solicitou (verificado pelo `usuario_email`). Não há compartilhamento entre clientes.

---

### **P: Como faço para adicionar um novo cliente ao sistema?**
**R:** Veja o arquivo `client_schema_map.json`:
```json
{
  "novo_cliente_hom": {
    "dbUser": "VRT_NEW",
    "name": "Novo Cliente - Homologação",
    "dbName": "VTIHOM1"
  }
}
```
E adicionar template em `client_templates.py`.

---

## 🔐 Segurança & Privacidade

- ✅ Validação HMAC de todos os payloads
- ✅ Banco de dados PostgreSQL com dados isolados por cliente
- ✅ URLs de download no OCI com expiração (1 hora)
- ✅ Logs auditáveis em todos os estágios
- ✅ Sem armazenamento temporário em disco (memória apenas)

---

## 📞 Próximos Passos / Suporte

- 📖 Documentação Técnica: veja [TECHNICAL_DOCS.md](TECHNICAL_DOCS.md)
- 🏗️ Diagrama Interativo: acesse [ARCHITECTURE_DIAGRAM.html](ARCHITECTURE_DIAGRAM.html)
- 💻 Setup Detalhado: veja [GETTING_STARTED.md](GETTING_STARTED.md)
- 📞 Suporte: contate o time de Backend

---

**Versão**: 1.0 | **Data**: 2026-03-20 | **Status**: ✅ Documentação Completa
