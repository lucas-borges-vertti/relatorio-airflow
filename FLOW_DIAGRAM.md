# Fluxo Completo: Relatórios Assíncronos (NestJS + Airflow)

## 🔄 Sequência de Invocação

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TEMPO: 0 seg - Usuário Clica                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  React (PortalCliente)                                              │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ 1. Detecta período: 01/03 até 31/03 = 31 dias (>= 30) │       │
│  │ 2. Modal "Relatório Assíncrono" aparece                 │       │
│  │ 3. Usuario clica "Solicitar"                            │       │
│  │ 4. Frontend valida payload                              │       │
│  │ 5. POST /api/reports/async com payload                 │       │
│  │    {                                                     │       │
│  │      "action": "portalCliente::getAnalitic",           │       │
│  │      "periodos": [{"ini": "2024-03-01", ...}],        │       │
│  │      "cliente_cnpj": "12.345.678/0001-90",             │       │
│  │      "usuario_email": "user@company.com"               │       │
│  │    }                                                     │       │
│  └──────────────────────────────────────────────────────────┘       │
│                              │                                       │
│                              ↓                                       │
│  Rede HTTP (localhost:3000 ou vertti.com.br)                        │
│                              │                                       │
└──────────────────────────────┼───────────────────────────────────────┘
                               │
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                  TEMPO: 1-2 seg - NestJS Processa                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  NestJS API (localhost:3000)                                        │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ ReportsController.submitAsyncReport()                    │       │
│  │                                                           │       │
│  │ 1. Validar DTO                                          │       │
│  │    ├─ action: string ✓                                 │       │
│  │    ├─ periodos: [{ini, fim}] ✓                        │       │
│  │    └─ cliente_cnpj: string ✓                          │       │
│  │                                                           │       │
│  │ 2. Chamar ReportsService.createAsyncReport()           │       │
│  │    ├─ Gerar requestId = UUID                           │       │
│  │    ├─ Criar ReportEntity {                             │       │
│  │    │   id, request_id, status=PENDING,               │       │
│  │    │   payload, cliente_cnpj, user, periodos       │       │
│  │    │ }                                                 │       │
│  │    └─ INSERT em BD: velog_reports_async               │       │
│  │                                                           │       │
│  │ 3. Trigger Airflow DAG                                │       │
│  │    ├─ POST http://airflow:8080/api/v1/dags/report_generation_dag/dagRuns │
│  │    ├─ Auth: airflow:airflow                           │       │
│  │    └─ Body:                                             │       │
│  │        {                                               │       │
│  │          "conf": {                                     │       │
│  │            "report_id": "uuid-xxx",                   │       │
│  │            "payload": {...},                          │       │
│  │            "cliente_cnpj": "..."                      │       │
│  │          }                                             │       │
│  │        }                                               │       │
│  │                                                           │       │
│  │ 4. Retornar HTTP 202 Accepted:                        │       │
│  │    {                                                   │       │
│  │      "status": true,                                  │       │
│  │      "requestId": "uuid-xxx",                         │       │
│  │      "data": { status: "PENDING", ... }             │       │
│  │    }                                                   │       │
│  │                                                           │       │
│  │ ⏱️  TEMPO TOTAL: ~200ms                               │       │
│  └──────────────────────────────────────────────────────────┘       │
│                              │                                       │
└──────────────────────────────┼───────────────────────────────────────┘
                               │
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                 TEMPO: 2-3 seg - React Recebe Response              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  React Frontend                                                      │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ 1. Toast de sucesso:                                    │       │
│  │    "Relatório enfileirado com sucesso!"                │       │
│  │                                                           │       │
│  │ 2. Guardar requestId em estado                         │       │
│  │                                                           │       │
│  │ 3. Modal muda para "Acompanhamento"                   │       │
│  │    ├─ Mostra: status PENDING                          │       │
│  │    ├─ Botão "Atualizar Status"                        │       │
│  │    └─ Auto-poll a cada 5 seg ← GET /status           │       │
│  │                                                           │       │
│  └──────────────────────────────────────────────────────────┘       │
│                              │                                       │
└──────────────────────────────┼───────────────────────────────────────┘
                               │
   WAIT ~2-5 min.              │
   Airflow está processando    ↓

┌─────────────────────────────────────────────────────────────────────┐
│             TEMPO: 2-5 min - Airflow DAG em Execução                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Airflow Scheduler/Executor                                         │
│  (localhost:8080)                                                   │
│                                                                       │
│  DAG: report_generation_dag                                         │
│  Run ID: dag_run_20260316T100000_xxxxx                             │
│  └─ Timeout: 5 min por task default                                │
│                                                                       │
│  TASK 1: extract_data (2-3 min) ⏳                                  │
│  ┌──────────────────────────────────────────────────────┐           │
│  │ python_callable: extract_report_data()               │           │
│  │                                                       │           │
│  │ 1. Ler conf (report_id, payload, cliente)          │           │
│  │                                                       │           │
│  │ 2. Resolver schema pelo cliente                     │           │
│  │    Ex.: potencial_hom -> VRT_POT                     │           │
│  │                                                       │           │
│  │ 3. Python executa queries Oracle diretamente        │           │
│  │    ├─ Query Oracle (volumes, qualidade, etc)       │           │
│  │    ├─ Aplica filtros (operacao, parceiro, etc)     │           │
│  │    └─ Retorna JSON com dados                        │           │
│  │                                                       │           │
│  │ 4. Salvar resultado em XCom (Airflow cache)         │           │
│  │    context['ti'].xcom_push(key='php_result', ...)  │           │
│  │                                                       │           │
│  │ 5. Log sucesso                                       │           │
│  │                                                       │           │
│  └──────────────────────────────────────────────────────┘           │
│                              │                                       │
│                              ↓                                       │
│                                                                       │
│  TASK 2: transform_data (30-60 seg) ⏳                              │
│  ┌──────────────────────────────────────────────────────┐           │
│  │ python_callable: transform_report_data()             │           │
│  │                                                       │           │
│  │ 1. Ler resultado do Task 1 via XCom                 │           │
│  │    php_result = context['ti'].xcom_pull(...)       │           │
│  │                                                       │           │
│  │ 2. Gerar PDF                                         │           │
│  │    ├─ Template + dados                              │           │
│  │    └─ Save: /reports/{report_id}/relatorio.pdf      │           │
│  │                                                       │           │
│  │ 3. Gerar XML                                         │           │
│  │    ├─ Template + dados                              │           │
│  │    └─ Save: /reports/{report_id}/relatorio.xml      │           │
│  │                                                       │           │
│  │ 4. Upload para CDN (futuro)                         │           │
│  │    ├─ AWS S3 ou similar                            │           │
│  │    └─ Gerar public URLs                            │           │
│  │                                                       │           │
│  │ 5. Salvar URLs em XCom para Task 4                 │           │
│  │    {pdf_url, xml_url, gerado_em}                   │           │
│  │                                                       │           │
│  └──────────────────────────────────────────────────────┘           │
│                              │                                       │
│                              ↓                                       │
│                                                                       │
│  TASK 3: send_email (10 seg) ⏳                                     │
│  ┌──────────────────────────────────────────────────────┐           │
│  │ python_callable: send_report_to_email()              │           │
│  │                                                       │           │
│  │ 1. Ler config: usuario_email, pdf_url, xml_url      │           │
│  │                                                       │           │
│  │ 2. Enviar email via SendGrid/AWS SES:              │           │
│  │    ├─ To: usuario_email                            │           │
│  │    ├─ Subject: "Seu relatório está pronto"         │           │
│  │    ├─ Body: HTML template                          │           │
│  │    ├─ Attachments: PDF                             │           │
│  │    └─ Links: para baixar XML                        │           │
│  │                                                       │           │
│  │ 3. Log entrega                                       │           │
│  │                                                       │           │
│  │ 4. XCom: delivery_status = DELIVERED               │           │
│  │                                                       │           │
│  └──────────────────────────────────────────────────────┘           │
│                              │                                       │
│                              ↓                                       │
│                                                                       │
│  TASK 4: callback_success (5 seg) ✅                                │
│  ┌──────────────────────────────────────────────────────┐           │
│  │ python_callable: callback_nestjs_success()           │           │
│  │ Trigger Rule: all_success (só executa se OK)        │           │
│  │                                                       │           │
│  │ 1. PATCH http://nestjs-api:3000/api/reports/{...}/status │      │
│  │    {                                                 │           │
│  │      "status": "COMPLETED",                         │           │
│  │      "airflow_dag_run_id": "dag_run_...",          │           │
│  │      "resultado": {                                 │           │
│  │        "pdf_url": "...",                            │           │
│  │        "xml_url": "..."                             │           │
│  │      }                                               │           │
│  │    }                                                 │           │
│  │                                                       │           │
│  │ 2. NestJS atualiza BD (velog_reports_async):       │           │
│  │    ├─ UPDATE status = COMPLETED                     │           │
│  │    ├─ UPDATE resultado = {...}                      │           │
│  │    ├─ UPDATE completed_at = NOW()                   │           │
│  │    └─ UPDATE updated_at = NOW()                     │           │
│  │                                                       │           │
│  │ 3. Log sucesso                                       │           │
│  │                                                       │           │
│  └──────────────────────────────────────────────────────┘           │
│                              │                                       │
│         [OU ERRO]            ↓         [OU ERRO]                     │
│                                                                       │
│  TASK 4b: callback_failure (5 seg) ❌ (se alguma task falhar)       │
│  ┌──────────────────────────────────────────────────────┐           │
│  │ python_callable: callback_nestjs_failure()           │           │
│  │ Trigger Rule: one_failed (executa se houver erro)   │           │
│  │                                                       │           │
│  │ 1. Capturar mensagem de erro do contexto            │           │
│  │                                                       │           │
│  │ 2. PATCH http://nestjs-api:3000/api/reports/{...}/status       │           │
│  │    {                                                 │           │
│  │      "status": "FAILED",                            │           │
│  │      "error_message": "PHP timeout after 300s"      │           │
│  │    }                                                 │           │
│  │                                                       │           │
│  │ 3. NestJS atualiza BD:                              │           │
│  │    ├─ UPDATE status = FAILED                        │           │
│  │    ├─ UPDATE error_message = "..."                  │           │
│  │    ├─ UPDATE completed_at = NOW()                   │           │
│  │    └─ Retry automático em Airflow (2x)             │           │
│  │                                                       │           │
│  └──────────────────────────────────────────────────────┘           │
│                              │                                       │
└──────────────────────────────┼───────────────────────────────────────┘
                               │
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│         TEMPO: 2-5 min + 30 seg - React Polling Detecta Mudança     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  React polling GET /api/reports/{requestId}/status (a cada 5s)    │
│                                                                       │
│  Sequência de status que React vê:                                  │
│  PENDING    → PENDING → PENDING  (while Airflow processando)        │
│           → PROCESSING → PROCESSING → PROCESSING                    │
│           → COMPLETED (quando sucesso) ou FAILED (se erro)         │
│                                                                       │
│  Quando COMPLETED:                                                  │
│  ┌──────────────────────────────────────────────────────┐           │
│  │ {                                                    │           │
│  │   "status": "COMPLETED",                           │           │
│  │   "resultado": {                                   │           │
│  │     "pdf_url": "https://cdn.vertti.com/reports/uuid/rel.pdf",
│  │     "xml_url": "https://cdn.vertti.com/reports/uuid/rel.xml",   │
│  │     "gerado_em": "2026-03-16T10:05:00Z",          │           │
│  │     "total_registros": 1523                        │           │
│  │   },                                                │           │
│  │   "completed_at": "2026-03-16T10:05:00Z",         │           │
│  │   "delivered_at": "2026-03-16T10:05:10Z"          │           │
│  │ }                                                   │           │
│  └──────────────────────────────────────────────────────┘           │
│                              │                                       │
│  Modal muda para:                                                   │
│  "✅ Relatório Gerado!"                                             │
│  ├─ Links para baixar:                                             │
│  │  ├─ PDF: botão verde                               │           │
│  │  └─ XML: botão azul                                │           │
│  └─ Resumo: 1.523 registros em 5 min                  │           │
│                                                                       │
│  [Usuário clica em PDF]                                             │
│  └─ Download iniciado                                               │
│                                                                       │
│  [Usuário clica em XML]                                             │
│  └─ Download iniciado                                               │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘


LEGENDA:
┌─┐ = Componente
│ │ = Conteúdo
└─┘ = Fim
─➜  = Fluxo
⏳  = Tempo
✅  = Sucesso
❌  = Erro
```

---

## 📊 Estados & Transições

```
Estados possíveis:
┌────────┐
│PENDING │──┐    (aguardando Airflow processar)
└────────┘  │
            ├──→ ┌────────────┐
            │    │ PROCESSING │──┐  (Airflow executando DAG)
            │    └────────────┘  │
            │                    ├──→ ┌───────────┐
            │                    │    │ COMPLETED │  (sucesso)
            │                    │    └───────────┘
            │                    │           │
            │                    │           ↓
            │                    │    ┌───────────────┐
            │                    │    │ delivered_at  │  (eventual)
            │                    │    └───────────────┘
            │                    │
            │                    └──→ ┌────────┐
            │                         │ FAILED │  (erro Airflow)
            │                         └────────┘
            │
            └──→ ┌──────────┐
                 │CANCELLED │  (user cancelou)
                 └──────────┘
```

---

## 💾 Database State Evolution

```
Momento 1: POST submete (status: 202)
┌──────────────────────────────────────────┐
│ velog_reports_async                      │
├──────────────────────────────────────────┤
│ id           UUID(1233-4567)             │
│ request_id   UUID(1233-4567)             │
│ status       PENDING                     │
│ payload      {action, periodos, ...}     │
│ criado_em    2026-03-16 10:00:00         │
│ atualizado_em 2026-03-16 10:00:00        │
│ resultado    NULL                        │
│ erro         NULL                        │
└──────────────────────────────────────────┘

Momento 2: Airflow dispara (status: PROCESSING)
┌──────────────────────────────────────────┐
│ status       PROCESSING                  │
│ airflow_dag_run_id  dag_run_20260316_... │
│ atualizado_em 2026-03-16 10:00:05        │
│ (resto igual)                            │
└──────────────────────────────────────────┘

Momento 3: Completo (status: COMPLETED)
┌──────────────────────────────────────────┐
│ status       COMPLETED                   │
│ resultado    {                           │
│              "pdf_url": "...",           │
│              "xml_url": "..."            │
│            }                             │
│ completed_at 2026-03-16 10:05:00         │
│ atualizado_em 2026-03-16 10:05:00        │
│ delivered_at 2026-03-16 10:05:10         │
│ erro         NULL                        │
└──────────────────────────────────────────┘
```

---

**Total de tempo esperado**: ~5 minutos (2-3 min extract + 30-60 seg transform + 10 seg email + 5 seg callback)
