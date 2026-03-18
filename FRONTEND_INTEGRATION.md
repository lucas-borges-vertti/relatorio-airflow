// Atualizar o asyncReport.service.js existente para usar nova API NestJS

// ❌ ANTES (apontava para Airflow direto):
// const API_URL = process.env.REACT_APP_AIRFLOW_URL;
// POST para ${API_URL}/api/reports/async

// ✅ DEPOIS (aponta para NestJS que gerencia Airflow):
// const API_URL = process.env.REACT_APP_NESTJS_URL || 'http://localhost:3000';
// POST para ${API_URL}/api/reports/async

/**
 * MUDANÇAS NECESSÁRIAS:
 *
 * 1. Atualizar .env do React:
 *    REACT_APP_NESTJS_URL=http://localhost:3000  (dev)
 *    ou
 *    REACT_APP_NESTJS_URL=http://relatorios.vertti.com.br  (prod)
 *
 * 2. Remover REACT_APP_AIRFLOW_URL (não precisa mais)
 *
 * 3. Payload MANTÉM o mesmo formato (sem mudanças necessárias!)
 *    - action: "portalCliente::getAnalitic"
 *    - periodos: [{ini, fim}]
 *    - filtros + cliente + cliente_cnpj + usuario_email + etc
 *
 * 4. Response format MUDOU:
 *    ❌ ANTES:
 *       {status: true, workflow_id, created_at, ...}
 *    ✅ DEPOIS:
 *       {status: true, requestId, message, data: {id, status: PENDING, ...}}
 *
 * 5. Status polling():
 *    GET /api/reports/{requestId}/status
 *    Retorna: {status: true, data: {status: PENDING|PROCESSING|COMPLETED|FAILED, ...}}
 */

// Exemplo do novo código:

export const submitAsyncReportRequest = async (payload, App) => {
  const API_URL = process.env.REACT_APP_NESTJS_URL || 'http://localhost:3000';

  try {
    const response = await fetch(`${API_URL}/api/reports/async`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...payload,
        hmac: token,  // mantém autenticação
        token: sessionStorage.getItem('token'),
        version: App?.pj?.version,
      })
    });

    if (!response.ok) {
      if (response.status === 408) {
        throw new Error('Requisição expirou');
      }
      throw new Error(`HTTP ${response.status}`);
    }

    return await response.json();
    // Esperado: {status: true, requestId, message, data: {...}}

  } catch (error) {
    // Tratamento de erro igual
    return {
      status: false,
      message: error.message,
      requestId: null,
    };
  }
};

// Polling para verificar status:

export const getReportStatus = async (requestId) => {
  const API_URL = process.env.REACT_APP_NESTJS_URL || 'http://localhost:3000';

  try {
    const response = await fetch(`${API_URL}/api/reports/${requestId}/status`);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const result = await response.json();
    // result.data = {
    //   id, request_id, status(PENDING|PROCESSING|COMPLETED|FAILED),
    //   payload, resultado, error_message, created_at, updated_at, delivered_at
    // }
    return result;

  } catch (error) {
    return {
      status: false,
      message: error.message,
    };
  }
};
