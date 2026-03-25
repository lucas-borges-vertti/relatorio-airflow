# 🔧 TECH PRESENTATION - Relatorio Async
## Apresentação Técnica para Devs & Tech Leads (30-45 minutos)

### Estrutura: 25 Slides Técnicos

---

## 📌 SLIDE 1: Capa Técnica

**Título**
```
RELATORIO ASYNC
Arquitetura de Geração Assíncrona de Relatórios
```

**Subtítulo**
```
NestJS + Apache Airflow + PostgreSQL + Oracle
Implementação em produção para 20+ clientes
```

**Autor**: Backend Team
**Data**: 2026-03-20

**Tempo**: 1 min

---

## 🎯 SLIDE 2: Escopo da Apresentação

**O que vamos cobrir**:

1. ✅ **Contexto & Problema** (Slides 3-5)
2. ✅ **Arquitetura Detalhada** (Slides 6-10)
3. ✅ **Fluxo Técnico Completo** (Slides 11-15)
4. ✅ **Deep Dives** (Slides 16-22)
   - NestJS: Controllers, Services, DTOs
   - Airflow: DAGs, Tasks, Operators customizados
   - Database: Schema e queries
5. ✅ **Deployment & Monitoring** (Slides 23-25)

**Tempo**: 1 min

---

## ❌ SLIDE 3: Problema Original

**Contexto Inicial**:

```
📊 Requisitos de Negócio:
  - Relatórios para períodos ≥ 30 dias
  - Processamento complexo no Oracle
  - Centenas de clientes/dia
  - Entrega por email (PDF + CSV)

❌ Solução Anterior (Síncrona):
  - Chamada PHP → Oracle (5-15 min)
  - Browser travado inteiro tempo
  - Timeout em períodos >20 min
  - UX horrível
  - Browser/Servidor inescalável

📈 Desafio:
  - Suportar picos (N requisições simultâneas)
  - Sem bloquear interface
  - Garantir entrega (retry + logs)
```

**Código Antigo (Pseudo-código)**:
```php
//❌ Síncrono (travava browser)
$result = $oracle->query("SELECT ...", timeout=5min);
$pdf = generatePDF($result);
header("Content-Type: application/pdf");
echo $pdf;
// Browser esperava 5-15 minutos!
```

**Tempo**: 2 min

---

## ✅ SLIDE 4: Decisão Arquitetural

**Por que Padrão Assíncrono?**

| Critério | Síncrono ❌ | Assíncrono ✅ |
|----------|-----------|-----------|
| Latência resposta | 5-15 min | 2 seg |
| Thread pool | 1 ocupada/req | Async client |
| Escalabilidade | N threads = problema | ∞ requisições |
| Confiabilidade | Timeout = perda | Retry + logs |
| UX | Travado | Responsivo |
| Monitoramento | Difícil | XCom + DB |

**Padrão Escolhido: HTTP 202 Accepted + Polling**

```
Frontend                API               Airflow
  │                      │                    │
  ├──POST /reports/───→  │                    │
  │                      ├──Valida────┐      │
  │                      ├──Persiste──┤      │
  │                      ├──Dispara——→├─ DAG │
  │  ←──202 + ID──────── │              │     │
  │ (requestId)          │              │     │
  │                      │              ← ✅ Pronto!
  │                      │ ← PATCH callback
  ├─ GET status ────────→ │             │
  │ (a cada 5 seg)        ← status:     │
  │         PENDING/PROCESSING/COMPLETED
```

**Alternativas Rejeitadas**:
- ❌ WebSocket: Overkill, stateful
- ❌ Message Queue (RabbitMQ): Complexidade extra
- ❌ gRPC: Incompatível com portal cliente (REST)

**Tempo**: 2 min

---

## 🏗️ SLIDE 5: Padrões & Conceitos

**Padrões Utilizados**:

```
1. REQUEST-RESPONSE ASSÍNCRONO
   ┌─────────────────────────────┐
   │ HTTP 202 Accepted           │
   │ + Polling (GET status)      │
   │ + Callback (PATCH result)   │
   └─────────────────────────────┘

2. TASK QUEUE (Airflow DAG)
   ┌──────────────────────────────┐
   │ extract_data                 │
   │       ↓ XCom                  │
   │ transform_data               │
   │       ↓ XCom                  │
   │ send_email                   │
   │       ↓                       │
   │ callback (NestJS)            │
   └──────────────────────────────┘

3. SAGA PATTERN (Auditoria)
   CREATE →  status=PENDING
         →  status=PROCESSING
         →  status=COMPLETED (ou FAILED)
   Rollback via error_message + retry

4. ADAPTER PATTERN
   ┌─────────────────────────┐
   │ OracleConnector         │
   │ (abstrai conexão)       │
   │ Schema mapping por      │
   │ cliente                 │
   └─────────────────────────┘
```

**Princípios SOLID**:
- ✅ **S**: ReportsService (responsabilidade única)
- ✅ **O**: Extensível para novos formatos (PDF/CSV/XLSX)
- ✅ **L**: DTOs validam contrato
- ✅ **I**: Separação NestJS/Airflow (não acoplado)
- ✅ **D**: Inversão de dependência (DI no NestJS)

**Tempo**: 2 min

---

## 🎯 SLIDE 6: Arquitetura em Alto Nível

**Componentes Principais**:

```
┌─────────────┐
│   FRONTEND  │ React Portal Cliente
│ (Port ~)   │ Detecta período ≥30 dias
└──────┬──────┘
       │ HTTP/REST
       ↓
┌──────────────────────────┐
│  NESTJS API (Port 3000)  │
├──────────────────────────┤
│ • Controllers (4 endpoints)
│ • Services (Business Logic)
│ • TypeORM (PostgreSQL)
│ • Axios (Airflow HTTP)
└──────┬───────────────────┘
       ├── INSERT/UPDATE ──→ PostgreSQL (metadata)
       └── HTTP POST ──────→ Airflow DAG trigger
                              │
                              ↓ (via API)
                    ┌─────────────────┐
                    │  AIRFLOW (8080) │
                    ├─────────────────┤
                    │ Task 1: Extract │ → Oracle
                    │ Task 2: Transform│ → ReportLab
                    │ Task 3: Send    │ → SMTP
                    │ Task 4: Callback│ → NestJS
                    └───────┬─────────┘
                            │
        ┌───────────────────┼───────────────┐
        ↓                   ↓               ↓
    ┌────────┐      ┌────────────┐   ┌──────────┐
    │ Oracle │      │PostgreSQL  │   │OCI Store │
    │(conteúdo)     │(metadata)  │   │(PDFs)    │
    └────────┘      └────────────┘   └──────────┘
```

**Padrão de Comunicação**:
- Frontend ↔ NestJS: **REST HTTP**
- NestJS ↔ Airflow: **REST HTTP** (API Airflow)
- Airflow ↔ Oracle: **TCP oracledb** (nativo)
- Airflow ↔ NestJS: **Callback HTTP PATCH**
- Airflow ↔ OCI: **AWS SDK** (S3-compatible)

**Tempo**: 2 min

---

## 📊 SLIDE 7: Diagrama de Sequência

**Sequência Técnica Completa**:

```
Frontend              NestJS                 Airflow
   │                    │                       │
   │ POST /async        │                       │
   ├───────────────────→│                       │
   │                    ├── Valida DTO          │
   │                    ├── INSERT BD           │
   │                    │ POST /api/v1/dags/...
   │                    ├──────────────────────→│
   │                    │ Airflow accepts       │
   │  202 Accepted      │                       │
   │←──requestId────────┤                       │
   │                    │                       │
   │ GET /status        │                       │ Task 1: extract
   ├───────────────────→│                       ├─→ Oracle
   │  {status:PENDING}  │                       │  SELECT ... (5-10min)
   │←───────────────────┤                       │
   │                    │                       │ Task 2: transform
   │ (polling loop)     │                       ├─ ReportLab (30-60s)
   │ GET /status        │                       │ OCI upload
   ├───────────────────→│                       │
   │  {PROCESSING}      │                       │ Task 3: send_email
   │←───────────────────┤                       ├─ SMTP (10s)
   │                    │                       │
   │                    │                       │ Task 4: callback
   │                    │ PATCH /api/.../status │
   │                    │←──────────────────────┤
   │                    │  {COMPLETED, keys}    │
   │                    ├── UPDATE BD           │
   │                    │                       │
   │ GET /status        │                       │
   ├───────────────────→│                       │
   │ {COMPLETED,keys}   │                       │
   │←───────────────────┤                       │
   │ ✅ Download link   │                       │
```

**Timing**:
- **Fase 1** (Frontend →  Request): 0-2 seg
- **Fase 2** (NestJS validation): 2-4 seg
- **Fase 3** (Airflow processing): 10-15 min
  - extract_data: 5-10 min (depende Oracle)
  - transform_data: 30-60 seg
  - send_email: 10 seg
  - callback: 5 seg

**Tempo**: 3 min

---

## 🗄️ SLIDE 8: Stack Tecnológico Detalhado

**Versões & Dependências**:

```
├─ FRONTEND
│  ├─ React 18.x
│  ├─ TypeScript 5.x
│  └─ Axios (HTTP client)
│
├─ BACKEND (NestJS)
│  ├─ @nestjs/core 10.x
│  ├─ @nestjs/common 10.x
│  ├─ @nestjs/swagger (OpenAPI docs)
│  ├─ typeorm 0.3.x (ORM)
│  ├─ class-validator (DTO validation)
│  ├─ class-transformer
│  ├─ axios (Airflow client)
│  └─ pg (PostgreSQL driver)
│
├─ AIRFLOW
│  ├─ apache-airflow 2.8.1
│  ├─ oracledb (Oracle client)
│  ├─ reportlab (PDF generation)
│  ├─ pandas (data manipulation)
│  ├─ oci (OCI SDK)
│  └─ requests (HTTP)
│
├─ DATABASES
│  ├─ PostgreSQL 16 (container)
│  ├─ Oracle Database (external)
│  └─ OCI Object Storage (external)
│
└─ INFRASTRUCTURE
   ├─ Docker & Docker Compose
   ├─ Node.js 20 runtime
   ├─ Python 3.11 (Airflow)
   └─ Alpine Linux (base images)
```

**Motivação Stack**:
- ✅ **NestJS**: TypeScript native, dependency injection, scalable MVC
- ✅ **Airflow**: Industry-standard orchestration, monitoring, retry built-in
- ✅ **PostgreSQL**: Transactional integrity, JSONB for flexible payload
- ✅ **Oracle**: Existing contract, multi-schema per client
- ✅ **Docker**: Environment parity (dev = prod)

**Tempo**: 2 min

---

## 🔌 SLIDE 9: Módulos NestJS

**Estrutura de Módulos**:

```
AppModule (Root)
├── ConfigModule (Airflow, DB credentials)
│   └── airflow.config.ts (env vars)
│
├── TypeOrmModule (PostgreSQL)
│   ├── ReportEntity
│   └── Migrations (auto-managed)
│
├── ReportsModule
│   ├── ReportsController (4 endpoints)
│   │   ├── POST /api/reports/async
│   │   ├── GET /api/reports/:id/status
│   │   ├── PATCH /api/reports/:id/status
│   │   └── GET /api/reports (list)
│   │
│   ├── ReportsService
│   │   ├── createAsyncReport()
│   │   ├── getReportById()
│   │   ├── updateReportStatus()
│   │   └── triggerAirflowDAG()
│   │
│   ├── CreateAsyncReportDto (validation)
│   │
│   └── ReportEntity (ORM mapping)
│
└── DatabaseModule (future extensions)
```

**Dependency Injection**:
```typescript
// Controllers usam Services via constructor injection
@Controller('api/reports')
export class ReportsController {
  constructor(
    private readonly reportsService: ReportsService
  ) {}

  @Post('async')
  async submitAsyncReport(@Body() dto: CreateAsyncReportDto) {
    return this.reportsService.createAsyncReport(dto);
  }
}
```

**Tempo**: 2 min

---

## 🔗 SLIDE 10: Integração com Airflow

**Como NestJS Dispara Airflow**:

```typescript
// NestJS Service
async triggerAirflowDAG(report: ReportEntity) {
  const dagRunConf = {
    report_id: report.id,
    payload: report.payload,
    cliente: report.payload.cliente,
  };

  try {
    // HTTP POST para Airflow API
    const response = await this.httpService.post(
      `${this.configService.get('AIRFLOW_BASE_URL')}/api/v1/dags/report_generation_dag/dagRuns`,
      { conf: dagRunConf },
      {
        auth: {
          username: this.configService.get('AIRFLOW_API_USER'),
          password: this.configService.get('AIRFLOW_API_PASSWORD'),
        },
      }
    ).toPromise();

    // Salva Airflow run_id
    report.airflow_dag_run_id = response.data.dag_run_id;
    await this.reportsRepository.save(report);

  } catch (error) {
    // Log e re-throw
    logger.error('Falha ao disparar DAG', error);
    throw new BadRequestException('Erro ao processar relatório');
  }
}
```

**Estrutura Payload Airflow**:
```json
{
  "conf": {
    "report_id": "a1b2c3d4-...",
    "payload": {
      "action": "portalCliente::getAnalitic",
      "periodos": [{"ini": "...", "fim": "..."}],
      "cliente": "potencial_hom",
      "usuario_email": "...",
      "filtros": {...}
    },
    "cliente": "potencial_hom"
  }
}
```

**Tempo**: 2 min

---

##  🚀 SLIDE 11: Apache Airflow DAG

**Definição da DAG**:

```python
default_args = {
    'owner': 'relatorio',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'email_on_failure': True,
}

dag = DAG(
    'report_generation_dag',
    default_args=default_args,
    schedule_interval=None,  # Triggered via API
    catchup=False,
)

# Task 1: Extract
task_extract = PythonOperator(
    task_id='extract_data',
    python_callable=extract_report_data,
    dag=dag,
)

# Task 2: Transform
task_transform = PythonOperator(
    task_id='transform_report_data',
    python_callable=transform_report_data,
    dag=dag,
)

# Task 3: Send Email
task_send = PythonOperator(
    task_id='send_report_email',
    python_callable=send_report_email,
    dag=dag,
)

# Task 4: Callback
task_callback = PythonOperator(
    task_id='notify_nesjs',
    python_callable=notify_nesjs_completion,
    dag=dag,
)

# Dependencies (linear sequence)
task_extract >> task_transform >> [ task_send, task_callback ]
```

**Características**:
- ✅ Triggered via API (não scheduled)
- ✅ 2 retries com delay de 5 min
- ✅ Email em falha
- ✅ Task dependencies lineares

**Tempo**: 2 min

---

## 📥 SLIDE 12: Task 1 - Extract Data (Detalhada)

**Código Simplificado**:

```python
def extract_report_data(**context):
    """
    Extrai dados do Oracle Database.
    Replica getAnalitic() do PHP.
    """
    dag_run_conf = context['dag_run'].conf
    report_id = dag_run_conf.get('report_id')
    payload = dag_run_conf.get('payload', {})
    cliente = dag_run_conf.get('cliente')

    logger.info(f"Iniciando extração para: {report_id}")

    # Importa função de extração
    from portal_cliente_extractor import extract_analitic

    # Liga e executa 3 queries no Oracle
    try:
        oracle_result = extract_analitic(payload)
    except OracleError as e:
        logger.error(f"Erro Oracle: {e}")
        raise

    # Salva resultado em XCom (intercomunicação tasks)
    context['task_instance'].xcom_push(
        key='oracle_result',
        value=oracle_result
    )

    logger.info(f"✅ Extração concluída. Registros: {len(oracle_result)}")

    return {
        'report_id': report_id,
        'total_rows': len(oracle_result)
    }
```

**Queries Executadas**:
```sql
-- Query 1: Dados principais
SELECT col1, col2, ... FROM VRT_POT.TAB_DADOS
WHERE data >= :ini AND data <= :fim AND ...

-- Query 2: Agregação mensal
SELECT mes, SUM(valor) FROM VRT_POT.TAB_MENSAL
GROUP BY mes ORDER BY mes

-- Query 3: Aderência (conformidade)
SELECT codigo, taxa_aderencia FROM VRT_POT.TAB_ADERENCIA
WHERE ...
```

**Schema Mapping**:
```json
{
  "potencial_hom": {"dbUser": "VRT_POT"},
  "jbs_hom": {"dbUser": "VRT_JBS"},
  ...
}
```

**Tempo Esperado**: 5-10 minutos (depende volume Oracle)

**Tempo em slide**: 2 min

---

## 🎨 SLIDE 13: Task 2 - Transform Data (PDF/CSV)

**Geração PDF com ReportLab**:

```python
def _generate_pdf(oracle_result, report_id, cliente='default'):
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    from client_templates import get_template

    # Carrega template (headers, styling, etc.)
    template = get_template(cliente)
    headers = template['headers']['pdf']

    # Formata dados
    rows = oracle_result.get('GROUPED', [])
    formatted_rows = format_rows_for_output(rows, headers)

    # Cria PDF em memória
    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, topMargin=1*cm)

    # Monta tabela
    table_data = [headers] + formatted_rows
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))

    # Builds PDF
    doc.build([table])
    pdf_bytes = pdf_buffer.getvalue()

    return pdf_bytes
```

**Geração CSV**:
```python
def _generate_csv(oracle_result, cliente='default'):
    import io
    from client_templates import get_template

    template = get_template(cliente)
    headers = template['headers']['csv']
    rows = oracle_result.get('GROUPED', [])

    output = io.StringIO()

    # Headers
    output.write(';'.join([h['label'] for h in headers]) + '\n')

    # Rows
    formatted = format_rows_for_output(rows, headers)
    for row in formatted:
        values = [str(row.get(h['key'], '')) for h in headers]
        output.write(';'.join(values) + '\n')

    return output.getvalue().encode('utf-8-sig')  # UTF-8 com BOM
```

**Templates por Cliente**:
```python
# client_templates.py
TEMPLATES = {
    'potencial_hom': {
        'headers': {
            'pdf': [
                {'key': 'numero', 'label': 'Número'},
                {'key': 'data', 'label': 'Data'},
                {'key': 'valor', 'label': 'Valor (USD)'},
                ...
            ],
            'csv': [...]
        },
        'concatDocumentos': True,  # Junta múltiplos docs
    },
    'jbs_hom': {...},
    ...
}
```

**Tempo Esperado**: 30-60 segundos

**Tempo em slide**: 2 min

---

## 💾 SLIDE 14: Task 3 & 4 - Email e Callback

**Envio de Email**:

```python
def send_report_email(**context):
    """Envia email com PDF/CSV anexados."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email.mime.text import MIMEText
    from email import encoders

    dag_run_conf = context['dag_run'].conf
    payload = dag_run_conf.get('payload', {})
    usuario_email = payload.get('usuario_email')

    # Recupera PDFs/CSVs do XCom
    pdf_bytes = context['task_instance'].xcom_pull(
        task_ids='transform_report_data',
        key='pdf_bytes'
    )
    csv_bytes = context['task_instance'].xcom_pull(
        task_ids='transform_report_data',
        key='csv_bytes'
    )

    # Monta email
    msg = MIMEMultipart()
    msg['From'] = os.environ['SMTP_FROM']
    msg['To'] = usuario_email
    msg['Subject'] = 'Seu Relatório Analítico está pronto!'

    # Body
    body_text = f"""
    Olá,

    Seu relatório foi gerado com sucesso!

    Período: {payload['periodos'][0]['ini']} a {payload['periodos'][0]['fim']}
    Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}

    Os arquivos estão em anexo.

    Atenciosamente,
    Sistema de Relatórios Vertti
    """
    msg.attach(MIMEText(body_text, 'plain', 'utf-8'))

    # Anexa PDF
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(pdf_bytes)
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment; filename=relatório.pdf')
    msg.attach(part)

    # Anexa CSV
    part = MIMEBase('text', 'csv')
    part.set_payload(csv_bytes.decode('utf-8'))
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment; filename=dados.csv')
    msg.attach(part)

    # Envia
    server = smtplib.SMTP(os.environ['SMTP_HOST'], int(os.environ['SMTP_PORT']))
    server.starttls()
    server.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
    server.send_message(msg)
    server.quit()

    logger.info(f"Email enviado para {usuario_email}")
```

**Callback para NestJS**:

```python
def notify_nesjs_completion(**context):
    """Notifica NestJS que relatório foi concluído."""
    import requests

    report_id = context['dag_run'].conf.get('report_id')
    pdf_key = context['task_instance'].xcom_pull(
        task_ids='transform_report_data',
        key='pdf_key'
    )
    csv_key = context['task_instance'].xcom_pull(
        task_ids='transform_report_data',
        key='csv_key'
    )

    # Monta payload de callback
    callback_payload = {
        'status': 'COMPLETED',
        'object_key_pdf': pdf_key,
        'object_key_csv': csv_key,
        'completed_at': datetime.utcnow().isoformat(),
    }

    # Chama NestJS API
    nesjs_url = os.environ['NESTJS_API_URL']
    response = requests.patch(
        f'{nesjs_url}/api/reports/{report_id}/status',
        json=callback_payload,
        timeout=30
    )

    if response.status_code != 200:
        logger.error(f"Callback falhou: {response.text}")
        raise Exception("Callback não foi confirmado")

    logger.info(f"✅ Relatório {report_id} marcado COMPLETED")
```

**Tempo em slide**: 3 min

---

## 🗄️ SLIDE 15: PostgreSQL Schema

**Tabela velog_reports_async**:

```sql
CREATE TABLE velog_reports_async (
  -- Primary Key & Identification
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),

  -- Status & Timestamps
  status VARCHAR(50) NOT NULL DEFAULT 'PENDING'
    CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED')),
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMP,
  delivered_at TIMESTAMP,

  -- Client & User Information
  cliente_cnpj VARCHAR(14) NOT NULL,
  usuario_id INTEGER,
  usuario_email VARCHAR(255) NOT NULL,

  -- Report Period
  periodo_ini DATE NOT NULL,
  periodo_fim DATE NOT NULL,

  -- Data Storage
  payload JSONB NOT NULL,  -- Original request (full)
  filtros JSONB,            -- Parsed filters
  resultado JSONB,          -- Final result metadata

  -- Airflow Integration
  airflow_dag_run_id VARCHAR(255),

  -- Storage References (OCI)
  object_key_pdf VARCHAR(512),
  object_key_csv VARCHAR(512),

  -- Error Tracking
  error_message TEXT,

  -- Indexes for Query Performance
  CREATE INDEX idx_cliente_cnpj ON velog_reports_async(cliente_cnpj);
  CREATE INDEX idx_usuario_email ON velog_reports_async(usuario_email);
  CREATE INDEX idx_status ON velog_reports_async(status);
  CREATE INDEX idx_created_at ON velog_reports_async(created_at DESC);
  CREATE INDEX idx_request_id ON velog_reports_async(request_id);
);
```

**Status Flow (State Machine)**:

```
PENDING ──(Airflow dispara)──→ PROCESSING
   ↑                               │
   │                               ├──(sucesso)──→ COMPLETED
   │                               │
   │                               └──(erro)──→ FAILED
   └────────(retry)────────────────┘

CANCELLED (manual cancellation)
```

**Queries Úteis**:

```sql
-- Relatórios em processamento
SELECT request_id, usuario_email, created_at
FROM velog_reports_async
WHERE status IN ('PENDING', 'PROCESSING')
ORDER BY created_at DESC;

-- Taxa de erro
SELECT COUNT(*) FILTER (WHERE status = 'FAILED') as failed,
       COUNT(*) FILTER (WHERE status = 'COMPLETED') as completed
FROM velog_reports_async
WHERE created_at >= NOW() - INTERVAL '7 days';

-- Duração média por cliente
SELECT cliente_cnpj,
       AVG(EXTRACT(EPOCH FROM (completed_at - created_at))/60) as media_duracao_min
FROM velog_reports_async
WHERE status = 'COMPLETED'
GROUP BY cliente_cnpj
ORDER BY media_duracao_min DESC;
```

**Tempo em slide**: 2 min

---

## 🔌 SLIDE 16: DTOs & Validação

**CreateAsyncReportDto**:

```typescript
import { 
  IsNotEmpty, 
  IsArray, 
  ValidateNested,
  IsEmail,
  IsOptional,
  ArrayMinSize,
  IsString,
  IsObject
} from 'class-validator';
import { Type } from 'class-transformer';

export class PerodoDto {
  @IsString()
  @IsNotEmpty()
  ini: string;  // YYYY-MM-DD

  @IsString()
  @IsNotEmpty()
  fim: string;  // YYYY-MM-DD

  // Validate period logic (opcional)
  @ValidateIf(o => o.ini && o.fim)
  @IsValidPeriod()  // Custom validator
  validatePeriod() {
    return true;
  }
}

export class CreateAsyncReportDto {
  @IsString()
  @IsNotEmpty()
  action: string;  // "portalCliente::getAnalitic"

  @IsArray()
  @ValidateNested()
  @Type(() => PerodoDto)
  @ArrayMinSize(1)
  periodos: PerodoDto[];

  @IsOptional()
  @IsString()
  cliente?: string;

  @IsOptional()
  @IsString()
  cliente_cnpj?: string;

  @IsOptional()
  @IsEmail()
  usuario_email?: string;

  @IsOptional()
  @IsEmail()
  email?: string;

  @IsOptional()
  @IsObject()
  filtros?: {
    id_pro?: string;
    cnpjund?: string[];
    operacoes?: string[];
    aprovacoes?: string[];
    [key: string]: any;
  };

  @IsOptional()
  @IsString()
  token?: string;

  @IsOptional()
  @IsString()
  hmac?: string;

  @IsOptional()
  @IsString()
  version?: string;
}
```

**Custom Validator (Exemplo)**:

```typescript
import { ValidatorConstraint, ValidatorConstraintInterface } from 'class-validator';

@ValidatorConstraint({ name: 'isValidPeriod', async: false })
export class IsValidPeriodConstraint implements ValidatorConstraintInterface {
  validate(obj: any): boolean {
    if (!obj.ini || !obj.fim) return true;

    const ini = new Date(obj.ini);
    const fim = new Date(obj.fim);

    // Periodo minimo: 1 dia
    return ini < fim && (fim.getTime() - ini.getTime()) >= 1000 * 60 * 60 * 24;
  }

  defaultMessage(): string {
    return 'Período inválido (fim deve ser > ini)';
  }
}
```

**Tempo em slide**: 2 min

---

## 🔐 SLIDE 17: Segurança & Validação

**Validação de Payload**:

```
POST /api/reports/async
├── 1. DTO Validation (class-validator)
│   ├─ Tipos corretos
│   ├─ Campos obrigatórios
│   └─ Ranges/constraints
│
├── 2. Business Logic Validation
│   ├─ Cliente existe?
│   ├─ Usuário autorizado?
│   └─ Período válido?
│
├── 3. HMAC Signature Check (future)
│   ├─ Valida token do frontend
│   └─ Garante autenticidade
│
└── 4. Rate Limiting (implementar depois)
    ├─ Máximo X requests/usuario/hora
    └─ Proteção contra spam
```

**Princípios Implementados**:

```
✅ Input Validation (classe-validator)
✅ SQL Injection Prevention (ORM + parameterized queries)
✅ CORS (configurável por env)
✅ Rate Limiting (middleware pronto para adicionar)
✅ Logging (todos endpoints logam)
✅ Error Handling (não expõe stack traces em prod)
✅ Database Encryption (variáveis sensíveis em secrets)
```

**Exemplo de Error Response**:

```json
{
  "statusCode": 400,
  "message": [
    "periodos must be an array",
    "usuario_email must be a valid email address"
  ],
  "error": "Bad Request"
}
```

**Tempo em slide**: 2 min

---

## 🚀 SLIDE 18: Deployment (Docker)

**Dockerfile NestJS**:

```dockerfile
# Base multi-stage build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Final image (smaller)
FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
RUN npm install -g npm @nestjs/cli

# Copy apenas build
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package*.json ./

EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD node -e "require('http').get('http://localhost:3000/health', (r) => {if (r.statusCode !== 200) throw new Error(r.statusCode)})"

CMD ["node", "dist/main.js"]
```

**docker-compose.yml**:

```yaml
version: '3.9'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: relatorio_user
      POSTGRES_PASSWORD: relatorio_pass
      POSTGRES_DB: relatorio_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U relatorio_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  nestjs-api:
    build:
      context: ./nestjs
      dockerfile: Dockerfile
    environment:
      NODE_ENV: production
      DB_HOST: postgres
      DB_PORT: 5432
      DB_USERNAME: relatorio_user
      DB_PASSWORD: relatorio_pass
      DB_DATABASE: relatorio_db
      AIRFLOW_BASE_URL: http://airflow-webserver:8080
      AIRFLOW_API_USER: airflow
      AIRFLOW_API_PASSWORD: airflow
    ports:
      - "3000:3000"
    depends_on:
      postgres:
        condition: service_healthy

  airflow-webserver:
    image: apache/airflow:2.8.1
    # ... (configuration omitted for brevity)
    ports:
      - "8080:8080"
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  postgres_data:

networks:
  - relatorio_network
```

**Deploy Steps**:

```bash
# 1. Build images
docker-compose build

# 2. Up services
docker-compose up -d

# 3. Verify health
docker-compose ps
curl http://localhost:3000/health
curl http://localhost:8080/health

# 4. Check logs
docker-compose logs -f nestjs-api
```

**Tempo em slide**: 2 min

---

## 📊 SLIDE 19: Monitoring & Logs

**O que Monitorar**:

```
┌──────────────────────────────────────┐
│ Métricas NestJS                      │
├──────────────────────────────────────┤
│ • HTTP request latency (P50, P95)    │
│ • error rates                        │
│ • database connection pool           │
│ • airflow API call success rate      │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ Métricas Airflow                     │
├──────────────────────────────────────┤
│ • DAG execution time                 │
│ • task success/failure rate          │
│ • oracle query duration              │
│ • scheduled vs actual execution time │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ Métricas PostgreSQL                  │
├──────────────────────────────────────┤
│ • connection count                   │
│ • slow queries (>1sec)               │
│ • disk usage                         │
│ • replication lag (if applicable)    │
└──────────────────────────────────────┘
```

**Logging Strategy**:

```
NestJS:
  ├─ Request/Response logging (middleware)
  ├─ Error stack traces (dev only)
  ├─ Duration de queries
  └─ Airflow trigger results

Airflow:
  ├─ Task execution logs (XCom)
  ├─ Oracle query logs
  ├─ Email delivery confirmation
  └─ Callback response status

PostgreSQL:
  ├─ Slow query log
  ├─ Error log
  └─ Audit log de status updates
```

**Exemplo Logger NestJS**:

```typescript
@Injectable()
export class LoggerService {
  private readonly logger = new Logger('RelatorioAsync');

  logRequest(method: string, url: string) {
    this.logger.log(`${method} ${url}`);
  }

  logReportCreation(reportId: string, clienteCnpj: string) {
    this.logger.log(`Report created: ${reportId} for ${clienteCnpj}`);
  }

  logAirflowTrigger(dagRunId: string, success: boolean) {
    const level = success ? 'log' : 'error';
    this.logger[level](`Airflow trigger: ${dagRunId} - ${success}`);
  }

  logError(error: Error, context?: string) {
    this.logger.error(`${context}: ${error.message}`, error.stack);
  }
}
```

**Tempo em slide**: 2 min

---

## 🔧 SLIDE 20: Troubleshooting Comum

**Problema 1: "Report stuck in PENDING"**

```
Causas Possíveis:
1. Airflow scheduler não está rodando
   → docker-compose ps | grep scheduler
   → docker-compose logs airflow-scheduler

2. DAG está pausada
   → Airflow UI: http://localhost:8080
   → Procure "report_generation_dag"
   → Toggle "Off" para ativar

3. NestJS não conseguiu fazer API call para Airflow
   → Verificar conectividade: curl http://airflow:8080/health
   → Ver logs NestJS: docker-compose logs nestjs-api

Solução:
- Reiniciar scheduler: docker-compose restart airflow-scheduler
- Ativar DAG na UI
- Verificar AIRFLOW_BASE_URL env var
```

**Problema 2: "Task extract_data fails with Oracle timeout"**

```
Causas Possíveis:
1. Host Oracle inválido ou indisponível
2. Credenciais erradas
3. Firewall bloqueando porta 1521
4. Query está toooo slow

Solução:
- Testar conexão Oracle direto
  docker-compose exec airflow python -c "
    import oracledb
    conn = oracledb.connect(
      user='VRT_POT',
      password='***',
      dsn='oracle_host:1521/VTIHOM1'
    )
    print('✅ OK')
  "

- Aumentar timeout em oracle_connector.py
- Adicionar índices no Oracle para queries
- Limitar período de dados (se possível)
```

**Problema 3: "Email não foi enviado"**

```
Causas Possíveis:
1. SMTP credenciais erradas
2. Firewall bloqueia SMTP port
3. Email destinatário inválido

Solução:
- Testar SMTP direto
  docker-compose exec airflow python -c "
    import smtplib
    server = smtplib.SMTP('smtp_host', 587)
    server.starttls()
    server.login('user', 'pass')
    print('✅ SMTP OK')
  "

- Verificar logs Airflow task "send_email"
- Checar spam folder do destinatário
```

**Tempo em slide**: 3 min

---

## 🏁 SLIDE 21: Performance Tuning

**Gargalos Identificados**:

```
Fase Extract (5-10 min): 90% do tempo total
├─ Causa: Oracle query é pesada
├─ Solução:
│  ├─ Índices no Oracle (dbuser, data, status)
│  ├─ Particionamento de tabelas (por data)
│  ├─ Materialized views para agregações
│  └─ Query result caching

Fase Transform (30-60 seg): ~5% do tempo
├─ Causa: ReportLab é single-threaded
├─ Solução:
│  ├─ Usar multiprocessing para múltiplos PDFs
│  └─ Cache templates compilados

Fase Send (10 seg): ~1% do tempo
├─ OK - não requer otimização

Callback (5 seg): <1% do tempo
├─ OK - network latency apenas
```

**Recomendações NestJS**:

```typescript
// 1. Database Connection Pooling
export const typeOrmConfig: TypeOrmModuleOptions = {
  type: 'postgres',
  host: process.env.DB_HOST,
  // ...
  extra: {
    max: 20,  // Pool size
    idleTimeoutMillis: 30000,
  },
};

// 2. Axios Timeout & Retry
const axiosConfig = {
  timeout: 30000,  // 30 sec
  httpAgent: new http.Agent({ keepAlive: true }),
  httpsAgent: new https.Agent({ keepAlive: true }),
};

// 3. Caching (se necessário)
// import { CacheModule } from '@nestjs/cache-manager';
// CacheModule.register({ ttl: 300 })  // 5 min
```

**Recomendações Airflow**:

```python
# 1. Aumentar pool (parallelização)
from airflow.models import Pool
Pool.create(
    name='oracle_queries',
    slots=5,  # Máximo 5 queries Oracle simultâneas
)

# 2. Aumentar DAG parallelization
dag.max_active_runs = 3  # Máximo 3 execuções simultâneas

# 3. Task XCom compression
os.environ['AIRFLOW__CORE__XCOM_ENABLE_COMPRESSION'] = 'True'
```

**Tempo em slide**: 2 min

---

## 📈 SLIDE 22: Escalabilidade Futura

**Arquitetura Current vs Future**:

```
CURRENT (Production Now):
┌────────────────────────────────┐
│  Single NestJS Instance (1)    │
├────────────────────────────────┤
│  Single Airflow Instance (1)   │
│  └─ LocalExecutor              │
├────────────────────────────────┤
│  Single PostgreSQL Instance (1)│
└────────────────────────────────┘

FUTURE (Scalable):
┌────────────────────────────────┐
│  NestJS Load Balancer (3)      │
│  ├─ API Pod 1                  │
│  ├─ API Pod 2                  │
│  └─ API Pod 3                  │
├────────────────────────────────┤
│  Airflow Cluster (Distributed) │
│  ├─ Webserver                  │
│  ├─ Scheduler                  │
│  ├─ Worker 1 (DAG processor)   │
│  ├─ Worker 2 (DAG processor)   │
│  └─ Executor: Celery          │
├────────────────────────────────┤
│  PostgreSQL Primary (Write)    │
│  ├─ PostgreSQL Replica 1 (Read)│
│  └─ PostgreSQL Replica 2 (Read)│
├────────────────────────────────┤
│  Redis (Session cache)         │
└────────────────────────────────┘

K8s Orchestration:
- NestJS: HPA (Horizontal Pod Autoscaling)
- Airflow: Multiple workers with CeleryExecutor
- PostgreSQL: Patroni for HA
```

**Próximos Steps**:

```
Phase 1 (Q2 2026): Airflow Cluster
├─ CeleryExecutor
├─ RabbitMQ / Redis broker
└─ Multiple worker nodes

Phase 2 (Q3 2026): Kubernetes
├─ NestJS deployment
├─ Airflow Helm chart
└─ Auto-scaling policies

Phase 3 (Q4 2026): Multi-Region
├─ OCI region failover
├─ Cross-region PostgreSQL replication
└─ CDN for file delivery
```

**Tempo em slide**: 2 min

---

## 🎓 SLIDE 23: Lições Aprendidas

**O que Funcionou Bem**:

```
✅ Http 202 + Polling (simples, funcional)
✅ Airflow DAGs (confiável, observable)
✅ PostgreSQL JSONB (flexível para payload)
✅ XCom para intercomunicação (genial)
✅ Docker Compose (dev environment parity)
✅ TypeORM migrations (database versioning)
✅ Separation of concerns (NestJS vs Airflow)
```

**Desafios & Soluções**:

```
❌ Problema: Oracle queries muito lentas
✅ Solução: Índices + Materialized views

❌ Problema: XCom payload muito grande (límite)
✅ Solução: Salvar dados em OCI, passar apenas keys

❌ Problema: Email delivery não confirmado
✅ Solução: Callback HTTP PATCH + retry logic

❌ Problema: Múltiplos clientes com schemas
✅ Solução: client_schema_map.json + dynamic schema

❌ Problema: Timezone issues (dates)
✅ Solução: enforce UTC em tudo, NLS_DATE_FORMAT em Oracle
```

**O que Faríamos Diferente**:

```
🔄 Usar gRPC em vez de REST (para NestJS ↔ Airflow)
   → Mas: REST é mais simples para polling

🔄 Implement Kafka message queue (em vez de HTTP)
   → Mas: Overhead para volume atual

🔄 Use Kubernetes from start
   → Mas: Overkill para MVP

✨ Manter KISS (Keep It Simple, Stupid)
   → REST HTTP é suficiente agora
   → Escalar quando necessário
```

**Tempo em slide**: 2 min

---

## 🔮 SLIDE 24: Roadmap Técnico

**Q2 2026 (Próximos 3 meses)**:

```
□ Dashboard de histórico (NestJS + React)
  └─ Lista relatórios por usuário
  └─ Filtros: status, período, cliente
  └─ Re-download de relatórios antigos

□ Performance: Cache Redis
  └─ Cache client_template compilados
  └─ Cache client_schema_map

□ Suporte novo formato: XLSX
  └─ usar openpyxl
  └─ Adicionar em client_templates

□ Observabilidade: Prometheus + Grafana
  └─ Métricas NestJS
  └─ Métricas Airflow
```

**Q3 2026 (Meses 4-6)**:

```
□ WhatsApp delivery (em vez de email)
  └─ Integração com Tawk.to ou Twilio
  └─ Link de download via WhatsApp

□ Agendamento de relatórios
  └─ Novo endpoint POST /api/reports/schedule
  └─ Airflow ClusterScheduler

□ Real-time progress updates
  └─ WebSocket (ou SSE) em vez de polling
  └─ Task progress por percentual
```

**Q4 2026 (Meses 7-9)**:

```
□ Machine Learning predictions
  └─ Integrar ML model (forecast)
  └─ Adicionar seção "Projeção" em relatório

□ Public API para extensores
  └─ OAuth2 + API keys
  └─ Rate limiting
  └─ SDK em Python/JS

□ Airflow Cluster (multi-worker)
  └─ CeleryExecutor
  └─ RabbitMQ broker
```

**Tempo em slide**: 2 min

---

## ❓ SLIDE 25: Q&A / Discussão

**Perguntas Esperadas & Respostas**:

**P: Por que não usar Event-Driven Archbggg?**
```
R: Padrão assíncrono via HTTP 202 é suficiente.
   Event-driven (Kafka) seria overkill para volume atual.
   Scale quando necessário.
```

**P: E se Airflow cair durante processamento?**
```
R: Task retry (2x automático). Se falhar:
   - Status = FAILED em PostgreSQL
   - Email ao usuário
   - Pode reprocessar manualmente
   - Logs completos para debug
```

**P: Como integrar com sistema de autenticação?**
```
R: Adicionar JWT middleware:
   - Frontend envia token em Authorization header
   - NestJS valida token
   - Extrair user_id do token
   - Verificar permissões por cliente
```

**P: Versioning da API?**
```
R: Atualmente: /api/v1/reports
   Estratégia:
   - New endpoints: /api/v2/reports-async (não quebrar v1)
   - Manter v1 por 2 anos
   - Migrar clientes gradualmente
```

**P: Como fazer disaster recovery?**
```
R: Backup strategy:
   - PostgreSQL: Automated daily backups
   - OCI Storage: Geo-redundant replication
   - Recovery Time Objective: 4 hours
   (Documentar em SETUP.md depois)
```

**Discussão Aberta**:
- Críticas arquitetura?
- Sugestões melhorias?
- Concerns de produção?
- Cases de uso novos?

**Tempo**: 5 min (aberto)

---

## 📚 REFERÊNCIAS & RECURSOS

**Documentação Oficial**:
- NestJS: https://docs.nestjs.com
- Airflow: https://airflow.apache.org/docs
- PostgreSQL: https://www.postgresql.org/docs
- Oracle: https://docs.oracle.com/en/database
- ReportLab: https://www.reportlab.com/docs/reportlab-userguide.pdf

**Diagrama Interativo**:
- Abrir: [ARCHITECTURE_DIAGRAM.html](./ARCHITECTURE_DIAGRAM.html)

**Documentação Técnica Completa**:
- Ver: [TECHNICAL_DOCS.md](./TECHNICAL_DOCS.md)

**Como Funciona (Para Não-Técnicos)**:
- Ver: [HOW_IT_WORKS.md](./HOW_IT_WORKS.md)

**Exemplos de Código**:
- `nestjs/src/modules/reports/`
- `airflow/dags/report_generation.py`
- `airflow/plugins/`

---

## 🎤 NOTAS PARA APRESENTADOR

**Tempo Total**: 30-45 minutos

**Breakdown Recomendado**:
- Slides 1-5 (Contexto): 8 min
- Slides 6-10 (Arquitetura): 7 min
- Slides 11-15 (Fluxo Técnico): 10 min
- Slides 16-22 (Deep Dives): 12 min
- Slides 23-25 (Lições + Q&A): 5 min

**Dicas**:

1. **Começa com o "Por Quê"** (slides 3-5)
   - Antes de despejar arquitetura, explica problema
   - Audiência precisa se importar

2. **Mostrar código real** (de verdade)
   - Copy-paste dos arquivos reais
   - Não pseudo-código genérico

3. **Live Demo (opcional)**
   - Se tiver tempo: fazer requisição curl
   - Mostrar Airflow UI rodando
   - Mostrar PostgreSQL query

4. **Interatividade**
   - Pausar a cada seção para perguntas
   - "Alguém tem questão?"
   - Não correr (é muita informação)

5. **Conhecer a audiência**
   - Devs: Focar em código/arquitetura
   - POs: Focar em benefícios/timeline
   - Tech Leads: Tudo + riscos/escalabilidade

---

**Versão**: 1.0 | **Data**: 2026-03-20 | **Slides**: 25 | **Duração**: 30-45 min
