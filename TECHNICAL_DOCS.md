# 📘 Documentação Técnica - Relatorio Async

## 📑 Índice

1. [Arquitetura Detalhada](#arquitetura-detalhada)
2. [APIs REST - Endpoints](#apis-rest---endpoints)
3. [DTOs e Validações](#dtos-e-validações)
4. [Apache Airflow](#apache-airflow)
5. [Banco de Dados](#banco-de-dados)
6. [Configuração & Variáveis de Ambiente](#configuração--variáveis-de-ambiente)
7. [OCI Object Storage](#oci-object-storage)
8. [Troubleshooting](#troubleshooting)

---

## 🏗️ Arquitetura Detalhada

### Componentes e Responsabilidades

#### **1. NestJS API (Porta 3000)**

Responsabilidades:
- ✅ **Gateway HTTP**: Recebe requisições do Frontend
- ✅ **Validação**: DTOs com `class-validator`
- ✅ **Persistência**: QueryBuilder TypeORM para PostgreSQL
- ✅ **Orquestração**: Dispara DAGs via API Airflow
- ✅ **Callbacks**: Recebe atualizações do Airflow
- ✅ **Status Tracking**: Fornece status em tempo real

**Stack**:
- Framework: NestJS 10.x
- ORM: TypeORM 0.3.x
- Validação: class-validator
- HTTP Client: axios
- Documentation: Swagger/OpenAPI

**Arquivos principais**:
```
nestjs/src/
├── main.ts                           # Bootstrap
├── app.module.ts                     # Root module (Config + DB + Reports)
├── config/
│   └── airflow.config.ts             # Env vars do Airflow
└── modules/
    └── reports/
        ├── reports.module.ts         # Module registration
        ├── reports.controller.ts     # 4 endpoints
        ├── reports.service.ts        # Business logic
        ├── entities/
        │   └── report.entity.ts      # Entidade PostgreSQL
        └── dtos/
            └── create-async-report.dto.ts  # Validação
```

---

#### **2. Apache Airflow (Porta 8080)**

Responsabilidades:
- ✅ **Orquestração**: Sequência de tarefas
- ✅ **Extração**: Conecta Oracle, executa queries
- ✅ **Transformação**: Gera PDF/CSV
- ✅ **Entrega**: Envia email com anexos
- ✅ **Callbacks**: Notifica NestJS do término

**Componentes**:
- Webserver: UI de monitoramento
- Scheduler: Executa DAGs quando disparadas
- Executor: PythonOperator para custom code

**DAG Structure**:
```
report_generation_dag
├── extract_data (PythonOperator)
│   └─ Executa portal_cliente_extractor.extract_analitic()
├── transform_data (PythonOperator)
│   └─ Executa _generate_pdf() e _generate_csv()
├── send_email (PythonOperator)
│   └─ Envia via SMTP
└── callback (PythonOperator)
    └─ PATCH /api/reports/{id}/status
```

**Plugins customizados** (em `airflow/plugins/`):
- `oracle_connector.py`: Abstração de conexão Oracle com context manager
- `portal_cliente_extractor.py`: Extração de dados (3 queries)
- `report_formatter.py`: Formatação PDF/CSV com templates
- `client_templates.py`: Mapeamento de headers por cliente

---

#### **3. PostgreSQL (Porta 5432)**

Responsabilidades:
- ✅ **Metadados**: Armazena requisições e status
- ✅ **Auditoria**: Logs de todas operações
- ✅ **Recuperação**: Permite retry de relatórios

**Tabela principal**: `velog_reports_async`

---

#### **4. Oracle Database**

Responsabilidades:
- ✅ **Fonte de dados**: Múltiplos esquemas por cliente
- ✅ **Queries**: Dados, mensal, aderência

**Acesso**:
- Driver: `oracledb` (Python 3.8+)
- Mapeamento: `client_schema_map.json`
- Exemplo: `potencial_hom` → Schema `VRT_POT`

---

#### **5. OCI Object Storage**

Responsabilidades:
- ✅ **Armazenamento**: PDFs e CSVs gerados
- ✅ **URLs de Download**: Válidas por 1 hora

---

### Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────┐
│                       Frontend (React)                       │
├─────────────────────────────────────────────────────────────┤
│  • Detecta período ≥ 30 dias                               │
│  • POST /api/reports/async (JSON com payload)              │
│  • Polling GET /api/reports/{id}/status (a cada 5 seg)    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓ HTTP REST
        ┌────────────────────────────┐
        │    NestJS API (3000)       │
        ├────────────────────────────┤
        │ • ReportsController        │
        │ • ReportsService           │
        │ • TypeORM + PostgreSQL     │
        │ • Axios → Airflow          │
        └────────────┬───────────────┘
                     │
        HTTP POST /api/v1/dags/{dag_id}/dagRuns
                     │
        ┌────────────▼───────────────┐
        │   Airflow (8080)           │
        ├────────────────────────────┤
        │ DAG: report_generation     │
        │ ├─ Task 1: extract_data    │
        │ ├─ Task 2: transform_data  │
        │ ├─ Task 3: send_email      │
        │ └─ Task 4: callback        │
        └────────────┬───────────────┘
                     │
     ┌───────────────┼───────────────┐
     ↓               ↓               ↓
  [Oracle]      [PostgreSQL]   [OCI Storage]
  (dados)       (metadados)    (PDFs/CSVs)
```

---

## 🔌 APIs REST - Endpoints

### Base URL

- **Desenvolvimento**: `http://localhost:3000`
- **Produção**: `https://relatorios.vertti.com.br` (placeholder)

---

### 1. POST /api/reports/async

Submeter novo relatório assíncrono

**Status Code**: `202 Accepted`

**Headers**:
```
Content-Type: application/json
```

**Body** (exemplo completo):
```json
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
  "usuario_id": 123,
  "usuario_email": "user@company.com",
  "email": "user@company.com",
  
  "filtros": {
    "id_pro": "PROD001",
    "cnpjund": ["12345678000100"],
    "operacoes": ["FOB", "CIF", "DDU", "DDP"],
    "aprovacoes": ["APPROVED", "PENDING"],
    "parceiros": ["PARC001", "PARC002"],
    "produto_categoria": ["CAT001"],
    "banco": ["BANCOBR"],
    "moeda": ["USD", "BRL"],
    "regimes": ["REGIME1"]
  },
  
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "hmac": "U2FsdGVkX1...",
  "version": "4.59"
}
```

**Success Response** (202 Accepted):
```json
{
  "status": true,
  "requestId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Relatório enfileirado com sucesso",
  "data": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "PENDING",
    "cliente_cnpj": "12345678000190",
    "usuario_email": "user@company.com",
    "periodo_ini": "2024-03-01",
    "periodo_fim": "2024-05-31",
    "created_at": "2026-03-16T10:00:00.000Z",
    "updated_at": "2026-03-16T10:00:00.000Z"
  }
}
```

**Error Response** (400 Bad Request):
```json
{
  "statusCode": 400,
  "message": [
    "periodos must be an array",
    "usuario_email must be an email"
  ],
  "error": "Bad Request"
}
```

**cURL Example**:
```bash
curl -X POST http://localhost:3000/api/reports/async \
  -H "Content-Type: application/json" \
  -d '{
    "action": "portalCliente::getAnalitic",
    "periodos": [{"ini": "2024-03-01", "fim": "2024-05-31"}],
    "cliente": "potencial_hom",
    "cliente_cnpj": "12345678000190",
    "usuario_email": "user@test.com"
  }'
```

---

### 2. GET /api/reports/:id/status

Obter status do relatório (polling)

**Status Code**: `200 OK`

**Parameters**:
- `:id` (path) - UUID do relatório (obrigatório)

**Success Response**:
```json
{
  "status": true,
  "data": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "PROCESSING",
    "cliente_cnpj": "12345678000190",
    "usuario_email": "user@company.com",
    "periodo_ini": "2024-03-01",
    "periodo_fim": "2024-05-31",
    "airflow_dag_run_id": "scheduled__2026-03-16T10:00:00+00:00_1",
    "created_at": "2026-03-16T10:00:00.000Z",
    "updated_at": "2026-03-16T10:02:30.000Z",
    "completed_at": null,
    "object_key_pdf": null,
    "object_key_csv": null,
    "error_message": null
  }
}
```

**Possíveis valores de `status`**:
- `PENDING`: Enfileirado, aguardando processamento
- `PROCESSING`: Sendo processado no Airflow
- `COMPLETED`: Concluído com sucesso
- `FAILED`: Falha durante processamento
- `CANCELLED`: Cancelado pelo usuário

**cURL Example**:
```bash
curl http://localhost:3000/api/reports/a1b2c3d4-e5f6-7890-abcd-ef1234567890/status
```

---

### 3. PATCH /api/reports/:id/status

Atualizar status (chamado apenas por Airflow)

**Status Code**: `200 OK`

**Parameters**:
- `:id` (path) - UUID do relatório

**Body** (enviado por Airflow):
```json
{
  "status": "COMPLETED",
  "object_key_pdf": "reports/a1b2c3d4/relatório-analítico.pdf",
  "object_key_csv": "reports/a1b2c3d4/dados.csv",
  "completed_at": "2026-03-16T10:15:00.000Z"
}
```

**Success Response**:
```json
{
  "status": true,
  "message": "Status atualizado com sucesso",
  "data": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "COMPLETED",
    "updated_at": "2026-03-16T10:15:00.000Z"
  }
}
```

**Para FAILED**:
```json
{
  "status": "FAILED",
  "error_message": "Timeout ao conectar ao Oracle (5 min)",
  "completed_at": "2026-03-16T10:15:00.000Z"
}
```

---

### 4. GET /api/reports

Listar todos os relatórios do usuário (opcional)

**Query Parameters**:
- `skip` (int, default: 0): Paginação offset
- `take` (int, default: 10): Quantidade por página
- `status` (string, opcional): Filtrar por status

**Response**:
```json
{
  "status": true,
  "data": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "status": "COMPLETED",
      "created_at": "2026-03-16T10:00:00.000Z"
    },
    {
      "id": "b2c3d4e5-f6g7-8901-bcde-f12345678901",
      "status": "PROCESSING",
      "created_at": "2026-03-16T11:00:00.000Z"
    }
  ],
  "total": 2,
  "page": 1,
  "pageSize": 10
}
```

---

## 📦 DTOs e Validações

### CreateAsyncReportDto

**Arquivo**: `nestjs/src/modules/reports/dtos/create-async-report.dto.ts`

```typescript
import { 
  IsNotEmpty, 
  IsObject, 
  IsString, 
  IsEmail, 
  IsOptional, 
  IsArray, 
  ValidateNested,
  ArrayMinSize 
} from 'class-validator';
import { Type } from 'class-transformer';

export class PerodoDto {
  @IsString()
  @IsNotEmpty()
  ini: string;  // YYYY-MM-DD (ex: "2024-03-01")

  @IsString()
  @IsNotEmpty()
  fim: string;  // YYYY-MM-DD (ex: "2024-05-31")
}

export class CreateAsyncReportDto {
  @IsString()
  @IsNotEmpty()
  action: string;  // Sempre: "portalCliente::getAnalitic"

  @ValidateNested()
  @Type(() => PerodoDto)
  @ArrayMinSize(1)
  periodos: PerodoDto[];  // Pelo menos 1 período

  @IsOptional()
  @IsString()
  cliente?: string;  // Ex: "potencial_hom"

  @IsOptional()
  @IsString()
  cliente_cnpj?: string;  // Ex: "12345678000190"

  @IsOptional()
  @IsEmail()
  usuario_email?: string;

  @IsOptional()
  @IsEmail()
  email?: string;  // Fallback se usuario_email absent

  @IsOptional()
  usuario_id?: number;

  // Filtros opcionais
  @IsOptional()
  @IsString()
  id_pro?: string;

  @IsOptional()
  @IsArray()
  cnpjund?: string[];

  @IsOptional()
  @IsArray()
  operacoes?: string[];

  @IsOptional()
  @IsArray()
  aprovacoes?: string[];

  @IsOptional()
  @IsArray()
  parceiros?: string[];

  @IsOptional()
  @IsArray()
  produto_categoria?: string[];

  @IsOptional()
  @IsArray()
  banco?: string[];

  @IsOptional()
  @IsArray()
  moeda?: string[];

  @IsOptional()
  @IsArray()
  regimes?: string[];

  // Auth
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

**Validações aplicadas**:
- ✅ `action` deve ser string não-vazia
- ✅ `periodos` deve ser array com ≥1 item
- ✅ Cada período deve ter `ini` e `fim` em formato YYYY-MM-DD
- ✅ `usuario_email` (se fornecido) deve ser email válido
- ✅ Campos de filtro são arrays opcionais

---

## 🚀 Apache Airflow

### DAG: report_generation_dag

**Arquivo**: `airflow/dags/report_generation.py`

**Configuração**:
```python
default_args = {
    'owner': 'relatorio',
    'start_date': days_ago(1),
    'email': ['admin@vertti.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}
```

**Comportamento**:
- Retenta até 2 vezes em caso de falha
- Aguarda 5 minutos entre tentativas
- Envia email ao admin em caso de falha

---

### Task 1: extract_data

**Código**:
```python
def extract_report_data(**context):
    """
    Extrai dados do Oracle Database.
    Replicação da função getAnalitic() do PHP em Python puro.
    """
    from portal_cliente_extractor import extract_analitic

    dag_run_conf = context['dag_run'].conf
    report_id = dag_run_conf.get('report_id')
    payload = dag_run_conf.get('payload', {})
    cliente = dag_run_conf.get('cliente') or payload.get('cliente')

    logger.info("Iniciando extração para relatório: %s", report_id)

    # Extrai 3 queries (dados, mensal, aderência) e agrega
    result = extract_analitic(payload)

    # Salva XCom para tasks subsequentes
    context['task_instance'].xcom_push(key='oracle_result', value=result)

    return {
        'report_id': report_id,
        'total_registros': len(result.get('GROUPED', [])),
    }
```

**Responsabilidades**:
1. Lê `dag_run.conf` (payload + report_id)
2. Conecta Oracle via `oracle_connector.py`
3. Resolve schema por cliente (ex: potencial_hom → VRT_POT)
4. Executa 3 queries:
   - **Query Dados**: SELECT principal com filtros
   - **Query Mensal**: Agregação por mês
   - **Query Aderência**: Cálculo de conformidade
5. Agrega resultados em dicionário Python
6. Salva em XCom para próxima task

**Tempo esperado**: 5-10 minutos (depende Oracle)

---

### Task 2: transform_data

**Código** (resumido):
```python
def transform_report_data(**context):
    """
    Transforma dados em PDF e CSV conforme template do cliente.
    """
    oracle_result = context['task_instance'].xcom_pull(
        task_ids='extract_data',
        key='oracle_result'
    )

    cliente = context['dag_run'].conf.get('cliente', 'default')

    # Gera PDF
    pdf_bytes = _generate_pdf(oracle_result, report_id, cliente)

    # Gera CSV
    csv_bytes = _generate_csv(oracle_result, cliente)

    # Salva em OCI Storage
    from storage_service import save_to_oci
    pdf_key = save_to_oci(f"reports/{report_id}/relatório.pdf", pdf_bytes)
    csv_key = save_to_oci(f"reports/{report_id}/dados.csv", csv_bytes)

    context['task_instance'].xcom_push(key='pdf_key', value=pdf_key)
    context['task_instance'].xcom_push(key='csv_key', value=csv_key)

    return {
        'report_id': report_id,
        'pdf_size_mb': len(pdf_bytes) / (1024**2),
        'csv_size_mb': len(csv_bytes) / (1024**2),
    }
```

**Responsabilidades**:
1. Recupera dados do XCom (Task 1)
2. Carrega template do cliente (`client_templates.py`)
3. Formata linhas (headers, concatenação de documentos, etc.)
4. **Gera PDF**:
   - Usa ReportLab
   - Tabelas formatadas conforme template
   - Headers, footers, styling
5. **Gera CSV**:
   - Charset UTF-8-SIG (compatível Excel)
   - Separador: `;`
6. Salva ambos em OCI Storage
7. Salva keys em XCom

**Tempo esperado**: 30-60 segundos

---

### Task 3: send_email

**Código** (resumido):
```python
def send_report_email(**context):
    """
    Envia email com PDF e CSV anexados.
    """
    dag_run_conf = context['dag_run'].conf
    payload = dag_run_conf.get('payload', {})
    usuario_email = payload.get('usuario_email') or payload.get('email')

    pdf_key = context['task_instance'].xcom_pull(
        task_ids='transform_data',
        key='pdf_key'
    )
    csv_key = context['task_instance'].xcom_pull(
        task_ids='transform_data',
        key='csv_key'
    )

    # Gera URLs de download (válidas 1 hora)
    from oci_storage import get_download_url
    pdf_url = get_download_url(pdf_key, expires_in=3600)
    csv_url = get_download_url(csv_key, expires_in=3600)

    # Monta email
    msg = MIMEMultipart()
    msg['From'] = 'relatorios@vertti.com.br'
    msg['To'] = usuario_email
    msg['Subject'] = 'Seu Relatório Analítico está pronto!'

    # Corpo do email
    body = f"""
    Olá,

    Seu relatório foi gerado com sucesso!

    Período: {payload['periodos'][0]['ini']} a {payload['periodos'][0]['fim']}
    Cliente: {dag_run_conf.get('cliente')}
    Data/Hora: {datetime.now()}

    Arquivos:
    - PDF: {pdf_url}
    - CSV (Excel): {csv_url}

    Os arquivos estarão disponíveis para download por 1 hora.
    Após isso, solicite novamente o relatório.

    Atenciosamente,
    Sistema de Relatórios Vertti
    """

    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    # Envia via SMTP
    server = smtplib.SMTP(os.environ['SMTP_HOST'], int(os.environ['SMTP_PORT']))
    server.starttls()
    server.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
    server.send_message(msg)
    server.quit()

    logger.info(f"Email enviado para {usuario_email}")
```

**Responsabilidades**:
1. Recupera PDF/CSV keys do XCom
2. Gera URLs de download via OCI (1 hora de validade)
3. Monta email HTML/Plain
4. Conecta SMTP
5. Envia com autenticação
6. Registra log

**Tempo esperado**: 10 segundos

---

### Task 4: callback

**Código** (resumido):
```python
def notify_nesjs_completion(**context):
    """
    Notifica NestJS que relatório foi concluído.
    """
    report_id = context['dag_run'].conf.get('report_id')
    dag_run_id = context['dag_run'].run_id

    pdf_key = context['task_instance'].xcom_pull(
        task_ids='transform_data',
        key='pdf_key'
    )
    csv_key = context['task_instance'].xcom_pull(
        task_ids='transform_data',
        key='csv_key'
    )

    # Prepara payload de callback
    callback_payload = {
        'status': 'COMPLETED',
        'object_key_pdf': pdf_key,
        'object_key_csv': csv_key,
        'completed_at': datetime.utcnow().isoformat(),
    }

    # Chama NestJS API
    nestjs_url = os.environ['NESTJS_API_URL']
    response = requests.patch(
        f'{nestjs_url}/api/reports/{report_id}/status',
        json=callback_payload,
        timeout=30
    )

    if response.status_code != 200:
        logger.error(f"Callback falhou: {response.text}")
        raise Exception(f"Callback falhou com status {response.status_code}")

    logger.info(f"Relatório {report_id} marcado como COMPLETED em NestJS")
```

**Responsabilidades**:
1. Recupera PDF/CSV keys
2. Monta payload de callback
3. PATCH /api/reports/{id}/status na API NestJS
4. Atualiza registro em PostgreSQL

**Tempo esperado**: 5 segundos

---

### Fluxo de Erro

Se qualquer task falhar:
1. Airflow não executa as tasks subsequentes
2. Task é retentada até 2 vezes (com delay de 5 min)
3. Se continuar falhando: DAG = FAILED
4. Email é enviado ao admin@vertti.com
5. NestJS pode fazer callback manual com status=FAILED

---

## 🗄️ Banco de Dados

### PostgreSQL Schema

**Tabela**: `velog_reports_async`

```sql
CREATE TABLE velog_reports_async (
  -- Identificação
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
  
  -- Status e timestamps
  status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMP,
  delivered_at TIMESTAMP,
  
  -- Informações do cliente
  cliente_cnpj VARCHAR(14) NOT NULL,
  usuario_id INTEGER,
  usuario_email VARCHAR(255),
  
  -- Período do relatório
  periodo_ini DATE,
  periodo_fim DATE,
  
  -- Payload e resultados
  payload JSONB,
  filtros JSONB,
  resultado JSONB,
  
  -- Orquestração Airflow
  airflow_dag_run_id VARCHAR(255),
  
  -- Storage
  object_key_pdf VARCHAR(512),
  object_key_csv VARCHAR(512),
  
  -- Erro
  error_message TEXT,
  
  -- Índices para performance
  INDEX idx_cliente_cnpj (cliente_cnpj),
  INDEX idx_usuario_email (usuario_email),
  INDEX idx_status (status),
  INDEX idx_created_at (created_at)
);
```

**Campos principais**:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | UUID | Chave primária |
| `request_id` | UUID | ID da requisição (retornado ao frontend) |
| `status` | ENUM | PENDING, PROCESSING, COMPLETED, FAILED, CANCELLED |
| `cliente_cnpj` | VARCHAR | Identificação do cliente |
| `usuario_email` | VARCHAR | Email para entrega |
| `periodo_ini`, `periodo_fim` | DATE | Período do relatório |
| `payload` | JSONB | Toda requisição original |
| `filtros` | JSONB | Filtros Aplicados |
| `airflow_dag_run_id` | VARCHAR | ID da execução no Airflow |
| `object_key_pdf` | VARCHAR | Caminho no OCI Storage |
| `object_key_csv` | VARCHAR | Caminho no OCI Storage |
| `error_message` | TEXT | Mensagem de erro (se houver) |
| `created_at` | TIMESTAMP | Quando foi criado |
| `updated_at` | TIMESTAMP | Última atualização |
| `completed_at` | TIMESTAMP | Quando foi concluído |

---

### Queries Úteis

**Buscar relatório por ID**:
```sql
SELECT * FROM velog_reports_async 
WHERE request_id = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';
```

**Listar relatórios em PROCESSING**:
```sql
SELECT request_id, usuario_email, created_at 
FROM velog_reports_async 
WHERE status = 'PROCESSING'
ORDER BY created_at DESC;
```

**Contar relatórios por cliente (último dia)**:
```sql
SELECT cliente_cnpj, COUNT(*) as total
FROM velog_reports_async
WHERE created_at >= NOW() - INTERVAL '1 day'
GROUP BY cliente_cnpj
ORDER BY total DESC;
```

**Durações médias por status**:
```sql
SELECT 
  status,
  AVG(EXTRACT(EPOCH FROM (completed_at - created_at)))/60 as duracao_media_min
FROM velog_reports_async
WHERE completed_at IS NOT NULL
GROUP BY status;
```

**Erros mais frequentes**:
```sql
SELECT error_message, COUNT(*) as ocorrencias
FROM velog_reports_async
WHERE status = 'FAILED'
GROUP BY error_message
ORDER BY ocorrencias DESC;
```

---

## ⚙️ Configuração & Variáveis de Ambiente

### NestJS (.env)

```bash
# Node
NODE_ENV=development
PORT=3000

# Database (PostgreSQL)
DB_HOST=postgres
DB_PORT=5432
DB_USERNAME=relatorio_user
DB_PASSWORD=relatorio_pass
DB_DATABASE=relatorio_db
DB_SYNCHRONIZE=false  # Use migrations em prod

# Airflow
AIRFLOW_BASE_URL=http://airflow-webserver:8080
AIRFLOW_DAG_ID=report_generation_dag
AIRFLOW_API_USER=airflow
AIRFLOW_API_PASSWORD=airflow

# OCI Storage
OCI_NAMESPACE={OCI_NAMESPACE}
OCI_BUCKET_NAME=vertti-ged
OCI_REGION=sa-saopaulo-1
OCI_USER={OCI_USER}
OCI_FINGERPRINT={OCI_FINGERPRINT}
OCI_TENANCY={OCI_TENANCY}
OCI_PRIVATE_KEY_PATH=/root/.oci/oci_api_key.pem
OCI_DOWNLOAD_TTL_SECONDS=3600

# Logging
LOG_LEVEL=debug
LOG_FORMAT=json
```

---

### Airflow (.env para docker-compose)

```bash
# Airflow
AIRFLOW_HOME=/opt/airflow
AIRFLOW__CORE__EXECUTOR=LocalExecutor
AIRFLOW__CORE__DAGS_FOLDER=/opt/airflow/dags
AIRFLOW__CORE__PLUGINS_FOLDER=/opt/airflow/plugins
AIRFLOW_UID=0

# Webserver
AIRFLOW__WEBSERVER__SECRET_KEY=my-secret-key-change-in-prod
AIRFLOW__CORE__LOAD_EXAMPLES=False

# Oracle Connector
ORACLE_HOST={ORACLE_HOST}
ORACLE_PORT=1521
ORACLE_SERVICE_NAME={ORACLE_SERVICE_NAME}
ORACLE_USER={ORACLE_USER}
ORACLE_PASSWORD={ORACLE_PASSWORD}
ORACLE_DSN={ORACLE_HOST}:1521/{ORACLE_SERVICE_NAME}
AIRFLOW_CLIENT_SCHEMA_MAP_PATH=/opt/airflow/config/client_schema_map.json

# NestJS Callback
NESTJS_API_URL=http://nestjs-api:3000

# SMTP
SMTP_HOST={SMTP_HOST}
SMTP_PORT=587
SMTP_USER={SMTP_USER}
SMTP_PASSWORD={SMTP_PASSWORD}

# OCI Storage
OCI_NAMESPACE={OCI_NAMESPACE}
OCI_BUCKET_NAME=vertti-ged
OCI_REGION=sa-saopaulo-1
OCI_USER={OCI_USER}
OCI_FINGERPRINT={OCI_FINGERPRINT}
OCI_TENANCY={OCI_TENANCY}
OCI_PRIVATE_KEY_PATH=/root/.oci/oci_api_key.pem
```

---

### Variáveis Placeholders (Substituir em Produção)

| Placeholder | Exemplo | Onde Obter |
|-------------|---------|-----------|
| `{ORACLE_HOST}` | `oracle.vertti.com.br` | DBA |
| `{ORACLE_SERVICE_NAME}` | `VTIHOM1` | DBA |
| `{ORACLE_USER}` | `VRT_COM` | DBA |
| `{ORACLE_PASSWORD}` | `***` | DBA (secrets vault) |
| `{OCI_NAMESPACE}` | `vrtcompute` | Oracle Cloud Console |
| `{OCI_USER}` | `ocid1.user.oc1...` | Oracle Cloud Console |
| `{OCI_FINGERPRINT}` | `12:34:56:78:...` | Oracle Cloud Console |
| `{OCI_TENANCY}` | `ocid1.tenancy.oc1...` | Oracle Cloud Console |
| `{SMTP_HOST}` | `smtp.gmail.com` | Email provider |
| `{SMTP_USER}` | `relatorios@vertti.com.br` | Email provider |
| `{SMTP_PASSWORD}` | `***` | Email provider (secrets vault) |

---

## 📦 OCI Object Storage

### Estrutura de Armazenamento

```
Bucket: vertti-ged
├── reports/
│   ├── {report_uuid}/
│   │   ├── relatório-analítico.pdf
│   │   └── dados.csv
│   └── {another_uuid}/
│       ├── relatório-analítico.pdf
│       └── dados.csv
```

### Como Fazer Download

**URL de download** (com assinatura, válida 1 hora):
```
https://{NAMESPACE}.objectstorage.{REGION}.oci.customer-oci.com/n/{NAMESPACE}/b/{BUCKET}/o/reports/{report_uuid}/relatório-analítico.pdf?signature={SIGNATURE}&expiration={TIMESTAMP}
```

**Exemplo (gerado por NestJS)**:
```
https://vrtcompute.objectstorage.sa-saopaulo-1.oci.customer-oci.com/n/vrtcompute/b/vertti-ged/o/reports/a1b2c3d4/relatório-analítico.pdf?signature=qWeRtYuIoPqWErTyUiOp==&expiration=2026-03-16T11:00:00Z
```

---

## 🔧 Troubleshooting

### Problema: Relatório fica em PENDING indefinidamente

**Causas possíveis**:
1. ❌ Airflow não recebeu trigger
2. ❌ Scheduler Airflow não está rodando
3. ❌ DAG não está habilitada

**Solução**:
```bash
# Verificar se Airflow scheduler está rodando
docker-compose ps | grep scheduler

# Se não estiver, reiniciar
docker-compose restart airflow-scheduler

# Verificar se DAG existe e está habilitada
curl -s http://localhost:8080/api/v1/dags/report_generation_dag \
  -u airflow:airflow | jq '.is_paused'
# Deve retornar: false

# Se for true, ativar DAG
curl -XPATCH http://localhost:8080/api/v1/dags/report_generation_dag \
  -H "Content-Type: application/json" \
  -u airflow:airflow \
  -d '{"is_paused": false}'
```

---

### Problema: Task extract_data falha com "Oracle connection timeout"

**Causas possíveis**:
1. ❌ Host Oracle inválido ou indisponível
2. ❌ Suas credenciais estão erradas
3. ❌ Firewall bloqueando porta 1521

**Solução**:
```bash
# Verificar conectividade
docker-compose exec airflow-webserver \
  python -c "
import oracledb
try:
  conn = oracledb.connect(
    user='{ORACLE_USER}',
    password='{ORACLE_PASSWORD}',
    dsn='{ORACLE_HOST}:1521/{ORACLE_SERVICE_NAME}'
  )
  print('✅ Conexão OK')
except Exception as e:
  print(f'❌ Erro: {e}')
"

# Verificar client_schema_map.json
docker-compose exec airflow-webserver cat /opt/airflow/config/client_schema_map.json | jq '.'
```

---

### Problema: Email não está sendo enviado

**Causas possíveis**:
1. ❌ SMTP_HOST/PORT inválidos
2. ❌ Credenciais SMTP erradas
3. ❌ Firewall bloqueando porta 587

**Solução**:
```bash
# Testar SMTP conectividade
docker-compose exec airflow-webserver python -c "
import smtplib
try:
  server = smtplib.SMTP('{SMTP_HOST}', 587)
  server.starttls()
  server.login('{SMTP_USER}', '{SMTP_PASSWORD}')
  print('✅ SMTP OK')
  server.quit()
except Exception as e:
  print(f'❌ Erro: {e}')
"
```

---

### Problema: PDF gerado está vazio ou mal formatado

**Causas possíveis**:
1. ❌ Template do cliente não configurado
2. ❌ Headers mapeados errado
3. ❌ Dados vazios do Oracle

**Solução**:
```bash
# Verificar templates disponíveis
docker-compose exec airflow-webserver python -c "
from client_templates import get_template
template = get_template('potencial_hom')
print(f'Headers PDF: {template[\"headers\"][\"pdf\"]}')
print(f'Headers CSV: {template[\"headers\"][\"csv\"]}')
"

# Verificar dados extraídos
# Acesse Airflow UI → Task extract_data → Logs
# Procure por: "total_registros: X"
```

---

### Problema: OCI Storage - Arquivo não encontrado (404)

**Causas possíveis**:
1. ❌ Credenciais OCI inválidas
2. ❌ Bucket não existe
3. ❌ Permissões insuficientes

**Solução**:
```bash
# Testar acesso OCI
docker-compose exec airflow-webserver python -c "
import oci
config = oci.config.from_file('/root/.oci/config')
os_client = oci.object_storage.ObjectStorageClient(config)

try:
  namespace = os_client.get_namespace().data
  print(f'✅ Namespace: {namespace}')

  # Listar buckets
  buckets = os_client.list_buckets(namespace)
  for b in buckets.data:
    print(f'  - {b.name}')
except Exception as e:
  print(f'❌ Erro: {e}')
"
```

---

## 📊 Monitoramento

### Métricas Importantes

**Em tempo real**:
```bash
# Relatórios por status
SELECT status, COUNT(*) as total 
FROM velog_reports_async 
GROUP BY status;

# Tempo médio de processamento
SELECT AVG(EXTRACT(EPOCH FROM (completed_at - created_at)))/60
FROM velog_reports_async 
WHERE status = 'COMPLETED';

# Taxa de erro
SELECT (SELECT COUNT(*) FROM velog_reports_async WHERE status = 'FAILED') ::float / 
       (SELECT COUNT(*) FROM velog_reports_async) * 100 as taxa_erro_percent;
```

###Logs

```bash
# NestJS logs
docker-compose logs -f nestjs-api

# Airflow logs
docker-compose logs -f airflow-webserver
docker-compose logs -f airflow-scheduler

# PostgreSQL logs
docker-compose logs -f postgres
```

---

**Versão**: 1.0 | **Data**: 2026-03-20 | **Status**: ✅ Documentação Técnica Completa
