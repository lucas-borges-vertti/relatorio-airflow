"""
Oracle Database Connector para Airflow
Abstrai a conexão com Oracle DB, replicando o comportamento do conn::query PHP.
"""
import os
import json
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

import oracledb

logger = logging.getLogger(__name__)


def _load_client_schema_map() -> Dict[str, Dict[str, str]]:
    """
    Carrega o mapa cliente -> schema Oracle.
    """
    mapping_path = os.environ.get(
        'AIRFLOW_CLIENT_SCHEMA_MAP_PATH',
        '/opt/airflow/config/client_schema_map.json',
    )
    try:
        with open(mapping_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except FileNotFoundError:
        logger.warning('Arquivo de mapeamento nao encontrado: %s', mapping_path)
    except json.JSONDecodeError as err:
        logger.error('JSON invalido em %s: %s', mapping_path, err)
    except Exception as err:
        logger.error('Falha ao carregar mapeamento de clientes: %s', err)
    return {}


def resolve_schema_by_cliente(cliente: Optional[str]) -> str:
    """
    Resolve o schema Oracle (dbUser) a partir do cliente.
    Quando cliente estiver ausente ou nao mapeado, usa ORACLE_USER como fallback.
    """
    default_schema = os.environ.get('ORACLE_USER', '')
    if not cliente:
        return default_schema

    mapping = _load_client_schema_map()
    client_info = mapping.get(cliente)
    if not client_info:
        logger.warning('Cliente %s nao mapeado, usando ORACLE_USER fallback', cliente)
        return default_schema

    schema = client_info.get('dbUser') or default_schema
    return schema


def _get_connection_params() -> Dict[str, str]:
    """
    Lê credenciais Oracle das variáveis de ambiente.
    Aceita ORACLE_DSN diretamente ou constrói a partir de
    ORACLE_HOST / ORACLE_PORT / ORACLE_SERVICE_NAME.
    """
    user = os.environ['ORACLE_USER']
    password = os.environ['ORACLE_PASSWORD']

    dsn = os.environ.get('ORACLE_DSN')
    if not dsn:
        host = os.environ['ORACLE_HOST']
        port = os.environ.get('ORACLE_PORT', '1521')
        service = os.environ['ORACLE_SERVICE_NAME']
        dsn = f'{host}:{port}/{service}'

    return {'user': user, 'password': password, 'dsn': dsn}


@contextmanager
def get_oracle_connection():
    """
    Context manager que entrega uma conexão Oracle pronta,
    com NLS_DATE_FORMAT configurado conforme o PHP (db.php).
    """
    params = _get_connection_params()
    conn = oracledb.connect(
        user=params['user'],
        password=params['password'],
        dsn=params['dsn'],
    )
    try:
        with conn.cursor() as cur:
            cur.execute("ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD'")
        yield conn
    finally:
        conn.close()


def query(
    sql: str,
    params: Optional[Dict[str, Any]] = None,
    conn=None,
    cliente: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Executa uma query Oracle e retorna lista de dicts (keys uppercase),
    replicando o comportamento de conn::query do PHP.

    Args:
        sql: SQL com bind variables nomeadas (:PARAM_NAME)
        params: dict {PARAM_NAME: valor}
        conn: conexão existente (opcional); se None, abre uma nova
        cliente: chave de cliente para resolver schema (apenas para logs e fallback)

    Returns:
        list[dict] com todas as linhas; lista vazia se sem resultados
    """
    params = params or {}

    def _execute(connection):
        with connection.cursor() as cur:
            cur.execute(sql, params)
            columns = [col[0].upper() for col in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    if conn is not None:
        return _execute(conn)

    schema = resolve_schema_by_cliente(cliente)
    if schema:
        logger.info('Executando query Oracle para cliente=%s schema=%s', cliente, schema)

    with get_oracle_connection() as connection:
        return _execute(connection)


def query_one(
    sql: str,
    params: Optional[Dict[str, Any]] = None,
    conn=None,
    cliente: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Retorna apenas a primeira linha ou None."""
    rows = query(sql, params, conn, cliente)
    return rows[0] if rows else None


def build_in_clause(param_prefix: str, values: List[Any], params: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Constrói cláusula IN parametrizada.
    Retorna (sql_fragment, atualização_de_params).

    Exemplo:
        sql_in, new_params = build_in_clause('CNPJ_UND', ['12345', '67890'], params)
        # sql_in = ':CNPJ_UND_0, :CNPJ_UND_1'
        # new_params = {'CNPJ_UND_0': '12345', 'CNPJ_UND_1': '67890'}
    """
    placeholders = []
    new_params = {}
    for i, val in enumerate(values):
        key = f"{param_prefix}_{i}"
        placeholders.append(f":{key}")
        new_params[key] = val
    return ", ".join(placeholders), new_params
