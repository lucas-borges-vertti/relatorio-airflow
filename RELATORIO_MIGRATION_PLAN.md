# Plano de Migração — Agendamento de Relatório

> **Projeto origem:** `/home/lucas/projetos/relatorio/nestjs`
> **Projeto destino:** `/home/lucas/projetos/velog-monorepo/api_nestjs`
> **Airflow permanece em:** `/home/lucas/projetos/relatorio/airflow/`
> **Data do plano:** 02/04/2026

---

## MVP — Regras de Negócio

```
Tem acesso a relatório agendado? (Perfil via SIS_USRCFG)
│
├── SIM → Período máximo de 1 ano (365 dias)
│   ├── Período > 1 mês (30 dias) → AGENDAMENTO
│   │   ├── Tem cota disponível?
│   │   │   ├── NÃO → Alertar usuário (QuotaExceededException)
│   │   │   └── SIM → Agendar + consumir cota + disparar Airflow
│   └── Período ≤ 1 mês → Realiza consulta em tela
│
└── NÃO → Período máximo de 1 mês (30 dias)
    └── Período ≤ 1 mês → Realiza consulta em tela
```

### Regras de Cota

| Tipo | TP_LOTE | Limite por período |
|------|---------|--------------------|
| Diária | `1` | 3 agendamentos/dia (padrão) |
| Semanal | `2` | 10 agendamentos/semana (padrão) |
| Mensal | `3` | Conforme `QT_LOTE` em `SIS_USRCFG` |

> Os limites padrão são usados quando não há registro em `SIS_USRCFG`. Se houver, `QT_LOTE` prevalece.

### Validação de Duplicata

- Hash SHA-256 gerado de: `TP_ORIGEM + JSON.stringify(ordenado(DS_FILTRO))`
- Armazenado no campo `CD_HASH` da tabela `GED_AGDREL`
- Bloqueia novo agendamento se já existir hash com `CD_STS = 1` (AGENDADO)

---

## Estrutura de Banco de Dados

### GED_AGDREL — Agendamento de Relatório

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `ID_UOCC` | NUMBER (PK) | ID gerado via Oracle Sequence |
| `TP_ORIGEM` | VARCHAR2(50) | Tipo de Origem (ex: CONTROLADORIA, OPERACIONAL) |
| `ID_CDT` | NUMBER | ID do usuário que criou (FK → SIS_USR) |
| `DT_CDT` | DATE | Data de criação |
| `ID_OPR` | NUMBER | ID do operador responsável |
| `DT_OPR` | DATE | Data de operação |
| `CD_STS` | NUMBER | Status: `1` AGENDADO, `-1` EXECUTADO, `-3` CANCELADO |
| `DT_ENT` | DATE | Data prevista de entrega |
| `CD_HASH` | VARCHAR2(255) | SHA-256 de (ORIGEM + FILTRO) — anti-duplicata |
| `DS_FILTRO` | CLOB | JSON com os filtros aplicados |

### SIS_USRCFG — Configuração de Usuário

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `ID_USR` | NUMBER (FK) | Referência ao usuário (SIS_USR) |
| `TP_CONFIG` | NUMBER | Tipo: `1` = Agendamento de Relatório |
| `TP_LOTE` | NUMBER | `1` Diário, `2` Semanal, `3` Mensal |
| `QT_LOTE` | NUMBER | Quantidade de cotas disponíveis no período |
| `DT_VLD` | DATE | Data de validade da configuração |
| `CD_STS` | NUMBER | Status da configuração |

---

## Análise Comparativa dos Projetos

| Aspecto | `relatorio/nestjs` (origem) | `api_nestjs` (destino) |
|---------|----------------------------|------------------------|
| **Banco** | PostgreSQL + TypeORM | Oracle DB + SQL cru |
| **Migrations** | Sim (TypeORM) | **Não existem** — DBA cria no Oracle |
| **HTTP Server** | Express | Fastify |
| **Auth** | Sem auth implementado | JWT + sessão Redis |
| **IDs** | UUID auto-gerado | `getNextIdUocc()` via Oracle Sequence |
| **Services** | 1 service monolítico | 1 arquivo = 1 use-case |
| **Repositórios** | Injeção direta TypeORM | Interface + token string |
| **Linter** | ESLint + Prettier | Biome (4 tabs, 100 chars) |
| **Package Manager** | npm | Yarn 4 |
| **Response Wrap** | Não | Global `{ data, message, statusCode, timestamp }` |
| **Airflow** | Integrado no service | API dispara Airflow via HTTP externo |

---

## Padrões do Projeto api_nestjs

### Nomenclatura
- Arquivos: `kebab-case`
- Classes: `PascalCase`
- Métodos/variáveis: `camelCase`
- Constantes: `SCREAMING_SNAKE_CASE`

### Arquitetura Limpa
```
Controller → Service (1 por use-case) → Repository → OracleService
```

### Injeção de Dependência com Token
```typescript
// interface.ts
export const REPORT_SCHEDULING_REPOSITORY_INTERFACE = "REPORT_SCHEDULING_REPOSITORY_INTERFACE";
export interface ReportSchedulingRepositoryInterface { ... }

// module.ts
providers: [
  { provide: REPORT_SCHEDULING_REPOSITORY_INTERFACE, useClass: ReportSchedulingRepository },
]

// service.ts
constructor(
  @Inject(REPORT_SCHEDULING_REPOSITORY_INTERFACE)
  private readonly repository: ReportSchedulingRepositoryInterface,
) {}
```

### Padrão de Exceções
```typescript
export class QuotaExceededException extends HttpException {
  constructor(batchType: string) {
    super({
      statusCode: HttpStatus.UNPROCESSABLE_ENTITY,
      message: `Cota ${batchType} esgotada`,
      error: "QuotaExceeded",
      details: { batchType },
    }, HttpStatus.UNPROCESSABLE_ENTITY);
  }
}
```

### Repository (5 métodos obrigatórios + extras específicos)
```typescript
find(id: number, schema: string): Promise<GedAgdRelRow | null>
findAll(filters: ListFilters, schema: string): Promise<GedAgdRelRow[]>
insert(data: InsertData, schema: string): Promise<number>
update(id: number, data: UpdateData, schema: string): Promise<void>
delete(id: number, schema: string): Promise<void>  // Soft delete: CD_STS = -3

// Extras:
findByHash(hash: string, schema: string): Promise<GedAgdRelRow | null>
countByPeriod(userId: number, batchType: number, schema: string): Promise<number>
```

### OracleService — API do banco
```typescript
// SELECT múltiplas linhas
this.oracleService.queryWithContext<T>(sql, [param1, param2])

// SELECT uma linha
this.oracleService.queryOneWithContext<T>(sql, [param1])

// DML (INSERT/UPDATE/DELETE)
this.oracleService.executeWithContext(sql, [param1])

// Geração de ID (obrigatório para INSERT)
getNextIdUocc(this.oracleService, TableNames.GED_AGDREL)
```

---

## Estrutura de Diretórios (a criar)

```
src/modules/report-scheduling/
├── report-scheduling.module.ts
├── constants/
│   └── report-scheduling.constants.ts
├── controllers/
│   └── report-scheduling.controller.ts
├── dtos/
│   ├── create-report-scheduling.dto.ts
│   ├── list-report-schedulings-query.dto.ts
│   ├── report-scheduling-output.dto.ts
│   └── dashboard-output.dto.ts
├── errors/
│   └── report-scheduling.exception.ts
├── guards/
│   └── report-scheduling-access.guard.ts
├── interfaces/
│   ├── report-scheduling.interface.ts
│   └── user-config.interface.ts
├── repositories/
│   ├── report-scheduling.repository.ts
│   └── user-config.repository.ts
├── services/
│   ├── create-report-scheduling.service.ts
│   ├── cancel-report-scheduling.service.ts
│   ├── get-report-scheduling.service.ts
│   ├── list-report-schedulings.service.ts
│   ├── validate-quota.service.ts
│   ├── validate-period.service.ts
│   ├── get-dashboard.service.ts
│   └── generate-hash.service.ts
└── types/
    └── report-scheduling.types.ts
```

**Arquivos a alterar em shared/:**
```
src/shared/enums/tables-names.enum.ts        ← adicionar GED_AGDREL, SIS_USRCFG
src/shared/enums/report-scheduling.enum.ts   ← criar: ReportSchedulingStatus, BatchType
src/config/env-config.ts                     ← adicionar: airflow config
src/config/env-config.types.ts               ← adicionar: AirflowConfig interface
src/app.module.ts                            ← registrar: ReportSchedulingModule
```

---

## Endpoints da API

Todos os endpoints requerem `@UseGuards(JwtAuthGuard, SchemaGuard)`.

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/report-scheduling` | Cria agendamento (valida período, cota, duplicata) |
| `GET` | `/report-scheduling` | Lista agendamentos do usuário logado |
| `GET` | `/report-scheduling/dashboard` | Painel de controle: consumo + lista |
| `GET` | `/report-scheduling/:id` | Busca agendamento por ID |
| `DELETE` | `/report-scheduling/:id` | Cancela agendamento (`CD_STS = -3`) |

### POST /report-scheduling — Body

```json
{
  "tpOrigem": "CONTROLADORIA",
  "dtInicio": "2026-01-01",
  "dtFim": "2026-12-31",
  "dsFiltro": { "idRv": "123", "modal": "RODOVIARIO" }
}
```

### GET /report-scheduling/dashboard — Response

```json
{
  "data": {
    "consumo": {
      "diario": { "utilizado": 1, "limite": 3 },
      "semanal": { "utilizado": 3, "limite": 10 },
      "mensal": { "utilizado": 5, "limite": null }
    },
    "relatorios": [
      {
        "id": 1001,
        "tpOrigem": "CONTROLADORIA",
        "cdSts": 1,
        "dtCdt": "2026-04-01T10:00:00",
        "dtEnt": "2026-04-02",
        "dsFiltro": { "idRv": "123" },
        "cancelavel": true
      }
    ]
  }
}
```

---

## Checklist de Tarefas

### Fase 1 — Infraestrutura do Módulo

- [x] Criar `src/modules/report-scheduling/types/report-scheduling.types.ts`
- [x] Criar `src/modules/report-scheduling/constants/report-scheduling.constants.ts`
- [x] Criar `src/shared/enums/report-scheduling.enum.ts` (ReportSchedulingStatus, BatchType)
- [x] Adicionar `GED_AGDREL` e `SIS_USRCFG` em `src/shared/enums/tables-names.enum.ts`
- [x] Criar `src/modules/report-scheduling/errors/report-scheduling.exception.ts`

### Fase 2 — Repository Layer

- [x] Criar `src/modules/report-scheduling/interfaces/report-scheduling.interface.ts`
- [x] Criar `src/modules/report-scheduling/interfaces/user-config.interface.ts`
- [x] Criar `src/modules/report-scheduling/repositories/report-scheduling.repository.ts`
- [x] Criar `src/modules/report-scheduling/repositories/user-config.repository.ts`

### Fase 3 — Services

- [x] Criar `generate-hash.service.ts` — SHA-256 de origem+filtro
- [x] Criar `validate-period.service.ts` — limite 30/365 dias conforme perfil
- [x] Criar `validate-quota.service.ts` — diária: 3, semanal: 10, mensal: QT_LOTE
- [x] Criar `create-report-scheduling.service.ts` — orquestra criação + Airflow
- [x] Criar `cancel-report-scheduling.service.ts` — cancela se CD_STS = 1
- [x] Criar `get-report-scheduling.service.ts` — busca por ID
- [x] Criar `list-report-schedulings.service.ts` — lista com filtros
- [x] Criar `get-dashboard.service.ts` — agrega consumo + lista

### Fase 4 — Guard + DTOs + Controller

- [x] Criar `guards/report-scheduling-access.guard.ts`
- [x] Criar `dtos/create-report-scheduling.dto.ts`
- [x] Criar `dtos/list-report-schedulings-query.dto.ts`
- [x] Criar `dtos/report-scheduling-output.dto.ts`
- [x] Criar `dtos/dashboard-output.dto.ts`
- [x] Criar `controllers/report-scheduling.controller.ts`

### Fase 5 — Module + Registro

- [x] Criar `report-scheduling.module.ts`
- [x] Registrar `ReportSchedulingModule` em `src/app.module.ts`
- [x] Adicionar variáveis Airflow em `src/config/env-config.ts` e `env-config.types.ts`

### Fase 6 — Testes Unitários

- [ ] Criar `test/modules/report-scheduling/mocks/report-scheduling.mocks.ts`
- [ ] Criar `test/modules/report-scheduling/mocks/report-scheduling-factories.ts`
- [ ] Criar spec do controller
- [ ] Criar spec do `create-report-scheduling.service.ts`
- [ ] Criar spec do `validate-quota.service.ts`
- [ ] Criar spec do `report-scheduling.repository.ts`

### Fase 7 — Frontend (`web`) — fase 2

- [ ] Componente de seleção de período com guard visual de acesso
- [ ] Modal/página de agendamento com formulário
- [ ] Página de dashboard do painel de controle
- [ ] Integração de cancelamento de agendamento

---

## Critérios de Verificação

1. `yarn check` no api_nestjs sem erros Biome
2. `yarn test` com todos os specs passando
3. `POST /report-scheduling` com período > 1 mês cria agendamento com `CD_STS = 1`
4. `POST /report-scheduling` na 4ª solicitação diária retorna `422 QuotaExceeded`
5. `POST /report-scheduling` com mesmo payload retorna `409 DuplicateReport`
6. `POST /report-scheduling` com período > 365 dias retorna `422 PeriodExceeded`
7. `GET /report-scheduling/dashboard` retorna `{ consumo, relatorios }`
8. `DELETE /report-scheduling/:id` com `CD_STS = -1` (executado) retorna erro
9. `DELETE /report-scheduling/:id` com `CD_STS = 1` atualiza para `-3`

---

## Referências de Código

| Propósito | Caminho |
|-----------|---------|
| Padrão de módulo complexo | `src/modules/quotas/` |
| Padrão de guard JWT | `src/modules/auth/guards/jwt-auth.guard.ts` |
| Geração de ID Oracle | `src/shared/providers/get-last-id-uocc.provider.ts` |
| API do banco Oracle | `src/infrastructure/database/services/oracle.service.ts` |
| Lógica Airflow (origem) | `relatorio/nestjs/src/modules/reports/reports.service.ts` |
| Configuração de env vars | `src/config/env-config.ts` |
| Enum de tabelas | `src/shared/enums/tables-names.enum.ts` |
| Decorator @LoggedUser | `src/modules/auth/decorators/logged-user.decorator.ts` |
| Padrão de exceções | `src/modules/quotas/errors/quotas.exception.ts` |
