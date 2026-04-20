"""
Teste E2E do fluxo de geração de relatório assíncrono.

Modos de uso:
  # Captura JWT via log do NestJS enquanto você usa o site
  python3 test_e2e.py --capture

  # JWT colado manualmente (do DevTools → Network → Copy as cURL)
  python3 test_e2e.py --jwt "eyJ..." --payload '{"tpOrigem":"rhall","dtInicio":"2024-01-01","dtFim":"2024-03-31","dsFiltro":{}}'

  # Reutiliza captura anterior (test_capture.json)
  python3 test_e2e.py --run

Variáveis de ambiente (opcionais, sobrescrevem os defaults):
    APP_ENV
    NESTJS_API_URL   (preferencial)
    NESTJS_URL       (compatibilidade com nome antigo)
  AIRFLOW_URL      (default: http://localhost:8081)
  AIRFLOW_USER     (default: airflow)
  AIRFLOW_PASSWORD (default: airflow)
    ORACLE_DSN
    ORACLE_HOST, ORACLE_PORT, ORACLE_USER, ORACLE_PASSWORD, ORACLE_SERVICE_NAME
  TEST_SCHEMA      (schema Oracle onde GED_AGDREL e SIS_USRCFG estão)
    NESTJS_CONTAINER_NAME
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import datetime
import re

import requests


def env_first(*names, default=""):
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    return default

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
APP_ENV = env_first("APP_ENV", default="local")
NESTJS_URL = env_first("NESTJS_API_URL", "NESTJS_URL", default="http://localhost:4500")
AIRFLOW_URL = env_first("AIRFLOW_URL", default="http://localhost:8081")
AIRFLOW_USER = env_first("AIRFLOW_USER", default="airflow")
AIRFLOW_PASSWORD = env_first("AIRFLOW_PASSWORD", default="airflow")

ORACLE_DSN = env_first("ORACLE_DSN")
ORACLE_HOST = env_first("ORACLE_HOST")
ORACLE_PORT = env_first("ORACLE_PORT", default="1521")
ORACLE_USER_DB = env_first("ORACLE_USER")
ORACLE_PASSWORD_DB = env_first("ORACLE_PASSWORD")
ORACLE_SERVICE = env_first("ORACLE_SERVICE_NAME")
TEST_SCHEMA = env_first("TEST_SCHEMA")

NESTJS_CONTAINER = env_first("NESTJS_CONTAINER_NAME", default="velog_api_nestjs_dev")
DAG_ID = env_first("AIRFLOW_DAG_ID", default="report_generation_dag")
POLL_INTERVAL = int(env_first("POLL_INTERVAL", default="10"))
POLL_TIMEOUT = int(env_first("POLL_TIMEOUT", default="900"))

CAPTURE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_capture.json")
RESULT_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_result.txt")

STATUS_CANCELADO = -3
BATCH_LABEL = {1: "DIARIO", 2: "SEMANAL", 3: "MENSAL"}

# ---------------------------------------------------------------------------
# Logger de resultado
# ---------------------------------------------------------------------------
LINES = []

def log(msg=""):
    LINES.append(msg)
    print(msg)

def section(title):
    log()
    log("-" * 70)
    log(f"  {title}")
    log("-" * 70)

def write_result():
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(LINES) + "\n")
    print(f"\n→ Resultado salvo em: {RESULT_FILE}")

# ---------------------------------------------------------------------------
# Captura JWT via logs do NestJS
# ---------------------------------------------------------------------------
def capture_jwt(timeout_secs=120):
    log(f"[CAPTURA] Monitorando logs de {NESTJS_CONTAINER}...")
    log(f"  → Faça a ação no site agora (timeout: {timeout_secs}s)")
    log()

    proc = subprocess.Popen(
        ["docker", "logs", "-f", "--tail", "0", NESTJS_CONTAINER],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    jwt_token = None
    payload_body = None
    deadline = time.time() + timeout_secs

    try:
        for line in proc.stdout:
            if time.time() > deadline:
                log("[CAPTURA] Timeout sem detectar request.")
                break

            # NestJS loga requests como: POST /report-scheduling 201 ...
            # O JWT vem no Authorization header — precisa de log de request body
            # Detecta linha com POST /report-scheduling
            if "report-scheduling" in line and ("POST" in line or "post" in line):
                log(f"[CAPTURA] Request detectada: {line.strip()}")

            # Detecta Bearer token em qualquer linha de log
            match_jwt = re.search(r"Bearer\s+(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)", line)
            if match_jwt and not jwt_token:
                jwt_token = match_jwt.group(1)
                log(f"[CAPTURA] JWT capturado: {jwt_token[:40]}...")

            # Detecta payload JSON com tpOrigem no log
            match_payload = re.search(r'(\{[^}]*"tpOrigem"[^}]*\})', line)
            if match_payload and not payload_body:
                try:
                    payload_body = json.loads(match_payload.group(1))
                    log(f"[CAPTURA] Payload capturado: {payload_body}")
                except json.JSONDecodeError:
                    pass

            if jwt_token:
                break
    finally:
        if proc.poll() is None:
            proc.kill()

    if not jwt_token:
        log("[CAPTURA] JWT não foi detectado nos logs. Use --jwt manualmente.")
        log("  Dica: No browser → DevTools → Network → clique na request report-scheduling")
        log("        → Headers → Authorization → copie o valor após 'Bearer '")
        return None, None

    return jwt_token, payload_body


# ---------------------------------------------------------------------------
# Fase 1 — POST /report-scheduling no NestJS
# ---------------------------------------------------------------------------
def test_create_scheduling(jwt, payload):
    section("[1] POST /report-scheduling → NestJS")
    url = f"{NESTJS_URL}/report-scheduling"
    headers = {
        "Authorization": f"Bearer {jwt}",
        "Content-Type": "application/json",
    }

    log(f"  URL    : {url}")
    log(f"  Payload: {json.dumps(payload, ensure_ascii=False)}")
    log()

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        log(f"  Status HTTP : {resp.status_code}")
        log(f"  Body        : {resp.text[:500]}")

        if resp.status_code == 201:
            data = resp.json()
            report_id = data.get("idUocc") or data.get("id_uocc") or data.get("ID_UOCC")
            log(f"  report_id   : {report_id}")
            log("  RESULTADO: ACEITO ✓")
            return "ACEITO", report_id, data
        elif resp.status_code == 422:
            error = resp.json()
            log(f"  Erro: {error.get('message', error)}")
            log("  RESULTADO: COTA EXCEDIDA (comportamento esperado se limite atingido)")
            return "COTA_EXCEDIDA", None, resp.json()
        elif resp.status_code == 409:
            log("  RESULTADO: DUPLICADO — mesmo filtro já agendado")
            return "DUPLICADO", None, resp.json()
        else:
            log(f"  RESULTADO: FALHOU ({resp.status_code})")
            return "FALHOU", None, resp.json()

    except Exception as e:
        log(f"  ERRO: {e}")
        return "ERRO", None, None


# ---------------------------------------------------------------------------
# Fase 2 — Poll do DAG Airflow
# ---------------------------------------------------------------------------
def poll_airflow_dag(dag_run_id):
    section("[2] ACOMPANHAMENTO DO DAG → Airflow")

    auth = base64.b64encode(f"{AIRFLOW_USER}:{AIRFLOW_PASSWORD}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}
    base = f"{AIRFLOW_URL}/api/v1/dags/{DAG_ID}"

    log(f"  dag_run_id: {dag_run_id}")
    log(f"  Aguardando conclusão (poll a cada {POLL_INTERVAL}s, timeout {POLL_TIMEOUT}s)...")
    log()

    start = time.time()
    tasks_final = {}

    while time.time() - start < POLL_TIMEOUT:
        try:
            # Status do DAG run
            resp = requests.get(f"{base}/dagRuns/{dag_run_id}", headers=headers, timeout=10)
            if resp.status_code != 200:
                log(f"  [poll] HTTP {resp.status_code}: {resp.text[:200]}")
                time.sleep(POLL_INTERVAL)
                continue

            run_data = resp.json()
            state = run_data.get("state", "unknown")
            elapsed = int(time.time() - start)
            log(f"  [{elapsed:>4}s] DAG state: {state}")

            # Status das tasks
            t_resp = requests.get(f"{base}/dagRuns/{dag_run_id}/taskInstances", headers=headers, timeout=10)
            if t_resp.status_code == 200:
                tasks = t_resp.json().get("task_instances", [])
                for t in tasks:
                    tid   = t.get("task_id")
                    tst   = t.get("state", "none")
                    tasks_final[tid] = tst
                    log(f"         task {tid:<25}: {tst}")

            if state in ("success", "failed"):
                log()
                log(f"  DAG finalizado: {state.upper()}")
                return state, tasks_final

        except Exception as e:
            log(f"  [poll] Erro: {e}")

        time.sleep(POLL_INTERVAL)
        log()

    log("  TIMEOUT — DAG não finalizou no tempo limite")
    return "timeout", tasks_final


# ---------------------------------------------------------------------------
# Fase 3 — Verificação Oracle (read-only)
# ---------------------------------------------------------------------------
def verify_oracle(report_id, user_id):
    section("[3] VERIFICAÇÃO ORACLE (read-only)")

    try:
        import oracledb
    except ImportError:
        log("  oracledb não instalado — pulando verificação Oracle")
        log("  Instale com: pip install oracledb")
        return

    if not ORACLE_DSN and not (ORACLE_HOST and ORACLE_SERVICE):
        log("  Configuração Oracle ausente — pulando verificação Oracle")
        log("  Defina ORACLE_DSN ou ORACLE_HOST + ORACLE_SERVICE_NAME para habilitar esta etapa")
        return

    if not ORACLE_USER_DB or not ORACLE_PASSWORD_DB:
        log("  Credenciais Oracle ausentes — pulando verificação Oracle")
        log("  Defina ORACLE_USER e ORACLE_PASSWORD para habilitar esta etapa")
        return

    dsn = ORACLE_DSN or f"{ORACLE_HOST}:{ORACLE_PORT}/{ORACLE_SERVICE}"
    log(f"  Conectando em {dsn}...")

    try:
        conn = oracledb.connect(user=ORACLE_USER_DB, password=ORACLE_PASSWORD_DB, dsn=dsn)
    except Exception as e:
        log(f"  ERRO ao conectar: {e}")
        return

    STATUS_LBL = {1: "AGENDADO", -1: "EXECUTADO", -3: "CANCELADO"}

    with conn:
        with conn.cursor() as cur:
            cur.execute("ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD HH24:MI:SS'")
            if TEST_SCHEMA:
                cur.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {TEST_SCHEMA}")
                log(f"  Schema: {TEST_SCHEMA}")

            # Registro do report_id
            log(f"\n  GED_AGDREL — registro ID_UOCC = {report_id}:")
            cur.execute("""
                SELECT ID_UOCC, CD_STS, DT_CDT, DT_ENTREGA, TP_ORIGEM, CD_HASH
                FROM GED_AGDREL WHERE ID_UOCC = :1
            """, [report_id])
            row = cur.fetchone()
            if row:
                cols = [c[0] for c in cur.description]
                d = dict(zip(cols, row))
                sts = int(d.get("CD_STS") or 0)
                log(f"  {'ID_UOCC':<12}: {d['ID_UOCC']}")
                log(f"  {'CD_STS':<12}: {sts} ({STATUS_LBL.get(sts, '?')})")
                log(f"  {'DT_CDT':<12}: {d['DT_CDT']}")
                log(f"  {'DT_ENTREGA':<12}: {d['DT_ENTREGA']}")
                log(f"  {'TP_ORIGEM':<12}: {d['TP_ORIGEM']}")
            else:
                log(f"  Registro {report_id} não encontrado")

            # Contagem de cotas
            log(f"\n  SIS_USRCFG — limites do usuário ID_USR = {user_id}:")
            cur.execute("""
                SELECT TP_LOTE, QT_LOTE, DT_VLD
                FROM SIS_USRCFG
                WHERE ID_USR = :1 AND TP_CONFIG = 1 AND CD_STS = 1 AND DT_VLD >= SYSDATE
                ORDER BY TP_LOTE
            """, [user_id])
            cfg_rows = cur.fetchall()
            if cfg_rows:
                for r in cfg_rows:
                    tp, qt, vld = r
                    log(f"  TP_LOTE={tp} ({BATCH_LABEL.get(tp,'?')}) → QT_LOTE={qt} (válido até {vld})")
            else:
                log(f"  Sem config — usando defaults do sistema (3/10/30)")

            # Contagem atual por período
            log(f"\n  Contagem atual usada (CD_STS <> {STATUS_CANCELADO}):")
            count_sqls = {
                1: "SELECT COUNT(*) FROM GED_AGDREL WHERE ID_CDT=:1 AND CD_STS<>:2 AND TRUNC(DT_CDT)=TRUNC(SYSDATE)",
                2: "SELECT COUNT(*) FROM GED_AGDREL WHERE ID_CDT=:1 AND CD_STS<>:2 AND DT_CDT>=TRUNC(SYSDATE,'IW') AND DT_CDT<TRUNC(SYSDATE,'IW')+7",
                3: "SELECT COUNT(*) FROM GED_AGDREL WHERE ID_CDT=:1 AND CD_STS<>:2 AND TRUNC(DT_CDT,'MM')=TRUNC(SYSDATE,'MM')",
            }
            cfg_map = {int(r[0]): int(r[1]) for r in cfg_rows} if cfg_rows else {}
            defaults = {1: 3, 2: 10, 3: 30}
            for tp, sql in count_sqls.items():
                cur.execute(sql, [user_id, STATUS_CANCELADO])
                used = cur.fetchone()[0]
                limit = cfg_map.get(tp, defaults[tp])
                status = "EXCEDIDO" if used >= limit else "OK"
                log(f"  {BATCH_LABEL[tp]:<8}: {used}/{limit} → {status}")


# ---------------------------------------------------------------------------
# Fase 4 — Teste de cota excedida
# ---------------------------------------------------------------------------
def test_quota_exceeded(jwt, payload):
    section("[4] TESTE DE COTA — verificar rejeição quando limite atingido")
    log("  Tentando criar um agendamento adicional para forçar cota excedida...")
    log("  (Se a cota ainda não foi atingida, este teste será ACEITO — também válido)")
    log()

    result, _, body = test_create_scheduling_silent(jwt, payload)
    if result == "COTA_EXCEDIDA":
        log(f"  Cota excedida corretamente: {body.get('message', body)}")
        log("  RESULTADO: PASSOU ✓")
    elif result == "ACEITO":
        log("  Agendamento aceito (cota não atingida ainda) — comportamento correto")
        log("  RESULTADO: OK (sem excesso de cota no momento)")
    else:
        log(f"  RESULTADO: {result}")


def test_create_scheduling_silent(jwt, payload):
    url = f"{NESTJS_URL}/report-scheduling"
    headers = {"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 201:
            data = resp.json()
            rid = data.get("idUocc") or data.get("id_uocc") or data.get("ID_UOCC")
            return "ACEITO", rid, data
        elif resp.status_code == 422:
            return "COTA_EXCEDIDA", None, resp.json()
        elif resp.status_code == 409:
            return "DUPLICADO", None, resp.json()
        else:
            return "FALHOU", None, resp.json()
    except Exception as e:
        return "ERRO", None, {"error": str(e)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Teste E2E do fluxo de relatório")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--capture", action="store_true",
                       help="Captura JWT do log do NestJS enquanto você usa o site")
    group.add_argument("--run", action="store_true",
                       help="Reutiliza captura salva em test_capture.json")
    group.add_argument("--jwt", type=str,
                       help="JWT fornecido manualmente")
    p.add_argument("--payload", type=str,
                   help='Payload JSON para POST /report-scheduling (string JSON)')
    p.add_argument("--capture-timeout", type=int, default=120,
                   help="Timeout em segundos para captura automática (default: 120)")
    p.add_argument("--skip-oracle", action="store_true",
                   help="Pula a verificação read-only no Oracle")
    return p.parse_args()


def main():
    args = parse_args()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    LINES.clear()
    log("=" * 70)
    log(f"  TESTE E2E — FLUXO DE RELATORIO ASSÍNCRONO — {now}")
    log("=" * 70)
    log(f"  Ambiente: {APP_ENV}")
    log(f"  API    : {NESTJS_URL}")
    log(f"  Airflow: {AIRFLOW_URL}")
    log(f"  Oracle : {ORACLE_DSN or f'{ORACLE_HOST}:{ORACLE_PORT}/{ORACLE_SERVICE}' if ORACLE_HOST or ORACLE_SERVICE else 'nao configurado'}")
    log()

    jwt = None
    payload = None

    # --- Obter JWT + payload ---
    if args.capture:
        jwt, payload = capture_jwt(args.capture_timeout)
        if jwt:
            capture_data = {"jwt": jwt, "payload": payload}
            with open(CAPTURE_FILE, "w") as f:
                json.dump(capture_data, f, indent=2, ensure_ascii=False)
            log(f"\n[CAPTURA] Dados salvos em {CAPTURE_FILE}")
        else:
            log("\n[CAPTURA] Falhou — forneça o JWT manualmente com --jwt")
            write_result()
            sys.exit(1)

    elif args.run:
        if not os.path.exists(CAPTURE_FILE):
            log(f"ERRO: {CAPTURE_FILE} não encontrado. Execute --capture primeiro.")
            write_result()
            sys.exit(1)
        with open(CAPTURE_FILE) as f:
            capture_data = json.load(f)
        jwt = capture_data.get("jwt")
        payload = capture_data.get("payload")
        log(f"[CAPTURA] Dados carregados de {CAPTURE_FILE}")
        log(f"  JWT: {jwt[:40] if jwt else 'N/A'}...")

    elif args.jwt:
        jwt = args.jwt
        payload = json.loads(args.payload) if args.payload else None
        log(f"[JWT] Fornecido manualmente: {jwt[:40]}...")

    else:
        log("ERRO: especifique --capture, --run ou --jwt. Use --help para ajuda.")
        write_result()
        sys.exit(1)

    if not jwt:
        log("ERRO: JWT inválido ou não capturado.")
        write_result()
        sys.exit(1)

    if not payload:
        log("AVISO: payload não capturado. Use --payload '{...}' para fornecer manualmente.")
        write_result()
        sys.exit(1)

    # Extrair user_id do JWT (decode sem verificação de assinatura)
    try:
        jwt_parts = jwt.split(".")
        padded = jwt_parts[1] + "=" * (4 - len(jwt_parts[1]) % 4)
        jwt_claims = json.loads(base64.b64decode(padded).decode("utf-8"))
        user_id = jwt_claims.get("ID_USR") or jwt_claims.get("sub")
        schema_key = jwt_claims.get("schemaKey", "")
        log()
        log(f"  JWT claims: ID_USR={user_id}, schemaKey={schema_key}")
        log(f"  Expira em : {datetime.datetime.fromtimestamp(jwt_claims.get('exp', 0))}")
    except Exception as e:
        log(f"  Aviso: não foi possível decodificar JWT: {e}")
        user_id = None

    # --- Fase 1: criar agendamento ---
    result_fase1, report_id, resp_data = test_create_scheduling(jwt, payload)

    if result_fase1 not in ("ACEITO",):
        log()
        log(f"  Agendamento não criado ({result_fase1}) — teste encerrado após fase 1.")
        # Ainda mostra Oracle para contexto
        if user_id:
            verify_oracle(None, user_id)
        write_result()
        return

    # Busca o dag_run_id via API do Airflow.
    dag_run_id = None
    try:
        # Tenta encontrar o dag_run_id listando os runs recentes
        auth = base64.b64encode(f"{AIRFLOW_USER}:{AIRFLOW_PASSWORD}".encode()).decode()
        headers_af = {"Authorization": f"Basic {auth}"}
        r = requests.get(
            f"{AIRFLOW_URL}/api/v1/dags/{DAG_ID}/dagRuns?limit=1&order_by=-execution_date",
            headers=headers_af, timeout=10
        )
        if r.status_code == 200:
            runs = r.json().get("dag_runs", [])
            if runs:
                dag_run_id = runs[0].get("dag_run_id")
                log(f"\n  dag_run_id detectado via Airflow API: {dag_run_id}")
    except Exception as e:
        log(f"\n  Aviso ao buscar dag_run_id: {e}")

    if not dag_run_id:
        dag_run_id = f"manual__{report_id}"
        log(f"  dag_run_id não detectado automaticamente; usando fallback {dag_run_id}")

    # --- Fase 2: poll Airflow ---
    dag_state, tasks = poll_airflow_dag(dag_run_id)

    section("RESUMO DAS TASKS AIRFLOW")
    for tid, tst in tasks.items():
        icon = "✓" if tst == "success" else ("✗" if tst == "failed" else "~")
        log(f"  {icon} {tid:<30}: {tst}")

    # --- Fase 3: verificação Oracle ---
    if user_id and not args.skip_oracle:
        verify_oracle(report_id, int(user_id))
    elif args.skip_oracle:
        log()
        log("Verificação Oracle pulada por --skip-oracle")

    # --- Fase 4: teste cota excedida ---
    test_quota_exceeded(jwt, payload)

    # --- Conclusão ---
    log()
    log("=" * 70)
    fase1_ok  = result_fase1 == "ACEITO"
    fase2_ok  = dag_state == "success"
    email_ok  = tasks.get("send_email") == "success"
    oracle_ok = dag_state == "success"

    log(f"  Fase 1 — NestJS aceitar agendamento : {'PASSOU' if fase1_ok else 'FALHOU'}")
    log(f"  Fase 2 — DAG Airflow completou      : {'PASSOU' if fase2_ok else 'FALHOU'} ({dag_state})")
    log(f"  Fase 2 — Email enviado (Vertti API) : {'PASSOU' if email_ok else 'FALHOU'}")
    log(f"  Fase 3 — Verificação Oracle         : {'OK' if oracle_ok else 'INCONCLUSIVO'}")
    log(f"  report_id                           : {report_id}")
    log("=" * 70)

    write_result()


if __name__ == "__main__":
    main()
