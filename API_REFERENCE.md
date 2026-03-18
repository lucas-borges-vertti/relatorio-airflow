# API Reference - NestJS Relatórios Assíncronos

**Base URL**: `http://localhost:3000` (dev) ou `https://relatorios.vertti.com.br` (prod)

## Endpoints

### 1. POST /api/reports/async
Submeter novo relatório assíncrono

**Response**: `202 Accepted`

**Body** (application/json):
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
  "usuario_email": "user@company.com",
  "usuario_id": "123",

  // Filtros (opcional)
  "filtros": {
    "produtos": ["PROD001", "PROD002"],
    "operacoes": ["FOB", "CIF"],
    "aprovacoes": ["APPROVED"],
    "parceiros": ["PARC001"]
  },

  // Auth (do frontend)
  "token": "eyJhbGc...",
  "hmac": "U2FsdG...",
  "version": "4.59"
}
```

**Success Response**:
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

**Error Response** (400):
```json
{
  "status": false,
  "message": "periodos must be an array",
  "statusCode": 400
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
    "usuario_email": "user@company.com"
  }'
```

---

### 2. GET /api/reports/:id/status
Verificar status do relatório (polling)

**Response**: `200 OK`

**Parameters**:
- `id` (path) - UUID do relatório

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
    "airflow_dag_run_id": "dag_run_20260316_100000_xxxxx",
    "error_message": null,
    "resultado": null,
    "created_at": "2026-03-16T10:00:00.000Z",
    "updated_at": "2026-03-16T10:05:30.000Z",
    "completed_at": null,
    "delivered_at": null
  }
}
```

**Status values**:
- `PENDING` - Aguardando processamento
- `PROCESSING` - Em processamento no Airflow
- `COMPLETED` - Processado com sucesso (check `resultado`)
- `FAILED` - Erro durante processamento (check `error_message`)
- `CANCELLED` - Cancelado pelo usuário

**cURL Example**:
```bash
curl http://localhost:3000/api/reports/a1b2c3d4-e5f6-7890-abcd-ef1234567890/status
```

**JavaScript Polling Example**:
```javascript
async function pollStatus(requestId, maxAttempts = 120, interval = 5000) {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const response = await fetch(`/api/reports/${requestId}/status`);
    const result = await response.json();

    console.log(`Status: ${result.data.status}`);

    if (result.data.status === 'COMPLETED' || result.data.status === 'FAILED') {
      return result.data;
    }

    await new Promise(r => setTimeout(r, interval));
    attempts++;
  }

  throw new Error('Timeout waiting for report');
}
```

---

### 3. GET /api/reports/pending
Listar relatórios aguardando processamento (para Airflow)

**Response**: `200 OK`

**Query Parameters**:
- `limit` (optional, default=10) - Máximo de registros

**Success Response**:
```json
{
  "status": true,
  "count": 3,
  "data": [
    {
      "id": "uuid-1",
      "status": "PENDING",
      "cliente_cnpj": "12345678000190",
      "created_at": "2026-03-16T10:00:00.000Z",
      "payload": {...}
    },
    {
      "id": "uuid-2",
      "status": "PENDING",
      "cliente_cnpj": "98765432000111",
      "created_at": "2026-03-16T10:05:00.000Z",
      "payload": {...}
    }
  ]
}
```

**cURL Example**:
```bash
curl "http://localhost:3000/api/reports/pending?limit=20"
```

---

### 4. PATCH /api/reports/:id/status
Atualizar status do relatório (callback Airflow)

**Response**: `200 OK`

**Parameters**:
- `id` (path) - UUID do relatório

**Body** (application/json):
```json
{
  "status": "COMPLETED",
  "airflow_dag_run_id": "dag_run_20260316_100000_xxxxx",
  "resultado": {
    "pdf_url": "https://cdn.vertti.com/reports/uuid/relatorio.pdf",
    "xml_url": "https://cdn.vertti.com/reports/uuid/relatorio.xml",
    "gerado_em": "2026-03-16T10:15:00Z",
    "total_registros": 1523
  },
  "error_message": null
}
```

**Ou em caso de erro**:
```json
{
  "status": "FAILED",
  "airflow_dag_run_id": "dag_run_20260316_100000_xxxxx",
  "error_message": "Falha na extração Oracle"
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
    "resultado": {...},
    "completed_at": "2026-03-16T10:15:00.000Z",
    "updated_at": "2026-03-16T10:15:00.000Z"
  }
}
```

**cURL Example**:
```bash
curl -X PATCH http://localhost:3000/api/reports/uuid-xxx/status \
  -H "Content-Type: application/json" \
  -d '{
    "status": "COMPLETED",
    "resultado": {
      "pdf_url": "https://cdn.vertti.com/reports/uuid/relatorio.pdf"
    }
  }'
```

---

### 5. PATCH /api/reports/:id/delivered
Marcar como entregue

**Response**: `200 OK`

**cURL Example**:
```bash
curl -X PATCH http://localhost:3000/api/reports/uuid-xxx/delivered
```

---

## Status Transitions

```
┌────────┐
│PENDING │──→ PROCESSING ──→ ┌─────────┐
└────────┘                   │COMPLETED│
                             └─────────┘
                                  ↓
                            DELIVERED (eventual)

              Ou erro:
              ──→ FAILED

              (Pode ser CANCELLED manualmente)
```

## Error Handling

### Validation Errors (400)
- Missing required fields
- Invalid periodo format
- Missing cliente_cnpj

### Not Found (404)
- Report ID doesn't exist

### Server Errors (500)
- Database errors
- Airflow connection issues

**All errors follow this format**:
```json
{
  "status": false,
  "message": "Error description",
  "statusCode": 400
}
```

## Autenticação

Atualmente **sem autenticação** (open endpoints). Future:
- Add JWT validation
- Add rate limiting
- Add request signing (HMAC)

## Rate Limits

None configured. Future:
- 10 requests/min per cliente_cnpj
- 100 concurrent reports max

## Timeouts

- NestJS API response: 30s
- Airflow trigger call: 10s
- Default request timeout: 30s

## Content Types

- **Request**: `application/json`
- **Response**: `application/json` (always)

## CORS

Enabled for all origins (*)

## Database Fields Reference

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | UUID | NO | Primary key |
| request_id | UUID | NO | Client-facing ID |
| status | ENUM | NO | PENDING,PROCESSING,COMPLETED,FAILED,CANCELLED |
| payload | JSON | NO | Original request body |
| cliente_cnpj | VARCHAR | NO | Client identifier |
| usuario_email | VARCHAR | YES | Email for notification |
| usuario_id | INT | YES | User ID |
| filtros | JSON | YES | Applied filters |
| periodo_ini | VARCHAR | YES | Period start date |
| periodo_fim | VARCHAR | YES | Period end date |
| airflow_dag_run_id | VARCHAR | YES | Airflow DAG execution ID |
| error_message | TEXT | YES | Error desc if FAILED |
| resultado | JSON | YES | PDF/XML URLs + metadata |
| created_at | TIMESTAMP | NO | Creation time |
| updated_at | TIMESTAMP | NO | Last update |
| completed_at | TIMESTAMP | YES | Completion time |
| delivered_at | TIMESTAMP | YES | Delivery time |

---

**Last Updated**: 2026-03-16
**API Version**: 1.0
**Maintenance**: Update when endpoints change
